(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  DEIY.pages = DEIY.pages || {};
  DEIY.state = DEIY.state || {};

  const api = DEIY.api;
  const ui = DEIY.ui;
  const app = document.getElementById("app");

  if (!api || !ui || !app) {
    console.error("DEIY bootstrap failed: required dependencies are missing.");
    return;
  }

  const state = DEIY.state;
  state.user = state.user || api.store.user();
  state.guide = state.guide || null;
  state.cameraStream = state.cameraStream || null;
  state.roomLearning = state.roomLearning || null;

  let activePage = null;
  let activeHash = null;
  let renderVersion = 0;
  let authPromise = null;

  const ROUTES = {
    "/": "landing",
    "/admissions": "admissions",
    "/apply": "apply",
    "/verify": "verify",
    "/login": "login",
    "/guide": "guide",
    "/app/dashboard": "dashboard",
    "/app/calendar": "calendar",
    "/app/notifications": "notifications",
    "/app/profile": "profile",
    "/app/exams": "exams",
    "/app/library": "library",
    "/app/rooms": "rooms",
    "/app/gradebook": "gradebook",
    "/app/assignments": "assignments",
    "/app/help": "help",
    "/app/manage": "manage",
    "/app/admin": "admin"
  };

  const NAVIGATION = [
    { label: "Overview", items: [
      { title: "Dashboard", route: "#/app/dashboard", icon: "home" }
    ]},
    { label: "Learning", items: [
      { title: "Library", route: "#/app/library", icon: "library" },
      { title: "Exams", route: "#/app/exams", icon: "exam" },
      { title: "Study rooms", route: "#/app/rooms", icon: "users" },
      { title: "Assignments", route: "#/app/assignments", icon: "file" },
      { title: "Gradebook", route: "#/app/gradebook", icon: "chart" },
      { title: "Calendar", route: "#/app/calendar", icon: "calendar" }
    ]},
    { label: "Account", items: [
      { title: "Notifications", route: "#/app/notifications", icon: "bell" },
      { title: "Profile", route: "#/app/profile", icon: "user" },
      { title: "Help & AI", route: "#/app/help", icon: "sparkles" }
    ]},
    { label: "Management", items: [
      { title: "Content management", route: "#/app/manage", icon: "settings", roles: ["teacher", "admin"] },
      { title: "Administration", route: "#/app/admin", icon: "shield", roles: ["admin"] }
    ]}
  ];

  function escape(value) {
    return ui.esc(value == null ? "" : String(value));
  }

  function accountLink() {
    return state.user
      ? '<a href="#/app/dashboard">Dashboard</a>'
      : '<a href="#/login">Sign in</a>';
  }

  function publicHeader() {
    return '<header class="public-header"><div class="container">' +
      '<a class="brand" href="#/">' +
        '<span class="brand-mark">D</span>' +
        '<span>DEIY<small>Learning platform</small></span>' +
      '</a>' +
      '<button class="nav-toggle icon-btn" type="button" data-public-nav-toggle ' +
        'aria-label="Open menu" aria-expanded="false">' + ui.icon("menu") + '</button>' +
      '<nav class="public-nav" aria-label="Public navigation">' +
        '<a href="#/">Home</a>' +
        '<a href="#/admissions">Admissions</a>' +
        '<a href="#/guide">Guide</a>' +
        '<a href="#/apply">Apply</a>' +
        accountLink() +
        '<a class="btn btn-amber btn-sm" href="#/apply">Apply now</a>' +
      '</nav>' +
    '</div></header>';
  }

  function publicFooter() {
    return '<footer class="public-footer"><div class="container">' +
      '<span>&copy; ' + new Date().getFullYear() + ' DEIY &middot; Learn without limits</span>' +
      '<div class="row">' +
        '<a href="#/admissions">Admissions</a>' +
        '<a href="#/guide">Application guide</a>' +
        '<a href="#/apply">Apply</a>' +
        accountLink() +
      '</div>' +
    '</div></footer>';
  }

  function bindPublicChrome() {
    const toggle = document.querySelector("[data-public-nav-toggle]");
    const nav = document.querySelector(".public-nav");
    if (!toggle || !nav) return;

    function setOpen(open) {
      nav.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }

    toggle.addEventListener("click", function () {
      setOpen(!nav.classList.contains("open"));
    });
    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { setOpen(false); });
    });
  }

  function parseRoute() {
    const hash = location.hash || "#/";
    const value = hash.replace(/^#/, "") || "/";
    const question = value.indexOf("?");
    const path = question >= 0 ? value.slice(0, question) : value;
    const queryString = question >= 0 ? value.slice(question + 1) : "";
    const query = new URLSearchParams(queryString);
    let name = ROUTES[path];
    const params = {};

    if (!name) {
      let match = path.match(/^\/app\/exams\/attempt\/([^/]+)\/?$/);
      if (match) {
        name = "attempt";
        params.id = decodeURIComponent(match[1]);
      } else {
        match = path.match(/^\/app\/exams\/([^/]+)\/?$/);
        if (match) {
          name = "exam";
          params.id = decodeURIComponent(match[1]);
        } else {
          match = path.match(/^\/app\/library\/([^/]+)\/?$/);
          if (match) {
            name = "resource";
            params.id = decodeURIComponent(match[1]);
          } else {
            match = path.match(/^\/app\/rooms\/([^/]+)\/?$/);
            if (match) {
              name = "room";
              params.id = decodeURIComponent(match[1]);
            }
          }
        }
      }
    }

    return { hash, path, query, params, name: name || null };
  }

  DEIY.go = function (destination) {
    if (!destination) return;
    const target = String(destination);
    if (location.hash === target) {
      DEIY.rerender();
    } else {
      location.hash = target;
    }
  };

  function cleanupPage() {
    if (activePage && typeof activePage.destroy === "function") {
      try {
        activePage.destroy();
      } catch (error) {
        console.error("Page cleanup failed:", error);
      }
    }

    if (typeof DEIY.attemptCleanup === "function") {
      DEIY.attemptCleanup();
      DEIY.attemptCleanup = null;
    }

    if (typeof DEIY.roomCleanup === "function") {
      DEIY.roomCleanup();
      DEIY.roomCleanup = null;
    }

    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach(function (track) {
        track.stop();
      });
      state.cameraStream = null;
    }

    activePage = null;
  }

  async function authenticatedUser() {
    if (!api.store.token()) {
      state.user = null;
      return null;
    }

    if (state.user) return state.user;

    if (!authPromise) {
      authPromise = api.me()
        .then(function (user) {
          state.user = user;
          return user;
        })
        .finally(function () {
          authPromise = null;
        });
    }

    return authPromise;
  }

  function navigationMarkup(user, currentPath) {
    return NAVIGATION.map(function (section) {
      const items = section.items.filter(function (item) {
        return !item.roles || item.roles.includes(user.role);
      });

      if (!items.length) return "";

      return '<div class="side-section">' +
        '<div class="side-label">' + escape(section.label) + '</div>' +
        items.map(function (item) {
          const path = item.route.split("?")[0].replace(/^#/, "");
          const active = currentPath === path ||
            (path !== "/app/dashboard" && currentPath.indexOf(path + "/") === 0);

          return '<a class="side-link' + (active ? " active" : "") +
            '" href="' + escape(item.route) + '">' +
            ui.icon(item.icon) +
            '<span>' + escape(item.title) + '</span></a>';
        }).join("") +
        '</div>';
    }).join("");
  }

  function applicationShell(user, page, route) {
    const displayName = user.full_name || user.name ||
      user.email || "DEIY User";
    const role = user.role || "student";
    const initials = ui.initials(displayName);

    return '<div class="app-layout">' +
      '<div class="sidebar-scrim" data-sidebar-close></div>' +
      '<aside class="sidebar" id="app-sidebar">' +
        '<a class="brand" href="#/app/dashboard">' +
          '<span class="brand-mark">D</span>' +
          '<span>DEIY</span>' +
        '</a>' +
        '<div class="side-user">' +
          '<div class="avatar">' + escape(initials) + '</div>' +
          '<div class="side-user-info">' +
            '<strong>' + escape(displayName) + '</strong>' +
            '<span>' + escape(role) + '</span>' +
          '</div>' +
        '</div>' +
        '<nav class="side-nav" aria-label="Main navigation">' +
          navigationMarkup(user, route.path) +
        '</nav>' +
        '<div class="side-footer">' +
          '<a class="side-help" href="#/app/help">' +
            ui.icon("help-circle") + '<span>Need help?</span>' +
          '</a>' +
          '<button class="side-link" type="button" data-logout>' +
            ui.icon("log-out") + '<span>Sign out</span>' +
          '</button>' +
        '</div>' +
      '</aside>' +
      '<div class="app-body">' +
        '<header class="app-topbar">' +
          '<button class="menu-btn" type="button" data-sidebar-toggle aria-label="Open menu">' +
            ui.icon("menu") +
          '</button>' +
          '<h1>' + escape(page.title || "DEIY") + '</h1>' +
          '<div class="topbar-actions">' +
            '<a href="#/app/notifications" aria-label="Notifications">' +
              ui.icon("bell") +
            '</a>' +
          '</div>' +
        '</header>' +
        '<main class="app-main" id="page-content" tabindex="-1">' +
          '<div class="boot-screen">' +
            '<p>Loading ' + escape(page.title || "page") + '...</p>' +
          '</div>' +
        '</main>' +
      '</div>' +
    '</div>';
  }

  function bindShell() {
    const sidebar = document.getElementById("app-sidebar");
    const closeButtons = document.querySelectorAll("[data-sidebar-close]");
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const logout = document.querySelector("[data-logout]");

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove("open");
      const scrim = document.querySelector(".sidebar-scrim");
      if (scrim) scrim.classList.remove("open");
    }

    if (toggle) {
      toggle.addEventListener("click", function () {
        if (!sidebar) return;
        sidebar.classList.toggle("open");
        const scrim = document.querySelector(".sidebar-scrim");
        if (scrim) scrim.classList.toggle("open");
      });
    }

    closeButtons.forEach(function (button) {
      button.addEventListener("click", closeSidebar);
    });

    document.querySelectorAll(".side-nav a").forEach(function (link) {
      link.addEventListener("click", closeSidebar);
    });

    if (logout) {
      logout.addEventListener("click", function () {
        api.logout();
        state.user = null;
        window.dispatchEvent(new CustomEvent("deiy:session-changed"));
        ui.toast("Signed out.", "success");
        DEIY.go("#/");
      });
    }
  }

  function showError(container, error) {
    const message = error && error.message
      ? error.message
      : "Something went wrong while loading this page.";

    container.innerHTML = ui.errorPanel
      ? ui.errorPanel(message, "Please try again.")
      : '<div class="alert alert-error">' + escape(message) + '</div>';

    if (ui.bindRetry) {
      ui.bindRetry(container, function () {
        DEIY.rerender();
      });
    }
  }

  async function render() {
    const version = ++renderVersion;
    const route = parseRoute();

    if (!route.name) {
      cleanupPage();
      activeHash = route.hash;
      app.innerHTML = '<main class="app-main">' +
        '<div class="empty-state"><h2>Page not found</h2>' +
        '<p>The requested page does not exist.</p>' +
        '<a href="#/">Return home</a></div></main>';
      return;
    }

    const page = DEIY.pages[route.name];

    if (!page || typeof page.render !== "function") {
      console.error("DEIY page module is missing:", route.name);
      app.innerHTML = '<main class="app-main"><h2>Page unavailable</h2>' +
        '<p>This page could not be loaded. Check the JavaScript modules.</p></main>';
      return;
    }

    if (activeHash !== route.hash) {
      cleanupPage();
      activeHash = route.hash;
    }

    let user = null;

    if (page.app) {
      try {
        user = await authenticatedUser();
      } catch (error) {
        if (version !== renderVersion) return;
        state.user = null;
        api.store.clear();
        DEIY.go("#/login?redirect=" + encodeURIComponent(route.hash));
        return;
      }

      if (version !== renderVersion) return;

      if (!user) {
        DEIY.go("#/login?redirect=" + encodeURIComponent(route.hash));
        return;
      }
    }

    const ctx = {
      user: user,
      params: route.params,
      query: route.query,
      guide: state.guide
    };

    try {
      let container;

      if (page.app) {
        app.innerHTML = applicationShell(user, page, route);
        bindShell();
        container = document.getElementById("page-content");
      } else if (page.chrome) {
        app.innerHTML = '<div class="public-shell">' + publicHeader() +
          '<div id="public-page"></div>' + publicFooter() + '</div>';
        bindPublicChrome();
        container = document.getElementById("public-page");
      } else {
        app.innerHTML = '<div id="public-page"></div>';
        container = document.getElementById("public-page");
      }

      if (!container) return;

      const html = await page.render(ctx);
      if (version !== renderVersion) return;

      container.innerHTML = html == null ? "" : String(html);
      activePage = page;

      if (typeof page.after === "function") {
        await page.after(container, ctx);
      }

      if (DEIY.i18n && typeof DEIY.i18n.translateTree === "function") {
        DEIY.i18n.translateTree(app);
      }

      document.title = (page.title || "DEIY") + " · DEIY";

      if (page.app) {
        container.focus({ preventScroll: true });
      }
    } catch (error) {
      if (version !== renderVersion) return;
      console.error("Page rendering failed:", error);
      showError(
        document.getElementById(page.app ? "page-content" : "public-page") || app,
        error
      );
    }
  }

  DEIY.rerender = render;

  let booting = true;

  window.addEventListener("hashchange", function () {
    if (!booting) render();
  });

  window.addEventListener("deiy:session-changed", function () {
    state.user = api.store.user();
    render();
  });

  window.addEventListener("deiy:language-changed", function () {
    render();
  });

  window.addEventListener("deiy:unauthorized", function () {
    state.user = null;
    api.store.clear();

    const current = location.hash || "#/";
    if (current.indexOf("#/login") !== 0) {
      DEIY.go("#/login?redirect=" + encodeURIComponent(current));
    } else {
      render();
    }
  });

  async function boot() {
    const localHost = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);

    if (!api.store.token() && localHost) {
      try {
        const data = await api.devAdminSession();
        state.user = data.user;

        const current = location.hash || "#/";
        if (current === "#/" || current === "#/login" || current.indexOf("#/login?") === 0) {
          booting = false;
          location.hash = "#/app/admin";
          return;
        }
      } catch (error) {
        console.warn("Local development Admin session unavailable:", error.message);
      }
    }

    booting = false;
    render();
  }

  boot();
})();
