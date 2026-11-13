

(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});

  const ICONS = {
    home: '<path d="m3 10.8 9-7.8 9 7.8"/><path d="M5 9.6V21h14V9.6"/><path d="M9.5 21v-6h5v6"/>',
    library: '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22.5Z"/><path d="M4 4.5v18M8 7h8M8 11h6"/>',
    exam: '<path d="M9 3h6l1 2h3v16H5V5h3l1-2Z"/><path d="m8.5 12 2.2 2.2 4.8-4.7"/><path d="M8.5 17h7"/>',
    room: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    calendar: '<rect x="3" y="4.5" width="18" height="17" rx="2"/><path d="M8 2.5v4M16 2.5v4M3 10h18"/>',
    chart: '<path d="M3 3v18h18"/><path d="m7 15 3-4 3 3 5-7"/>',
    bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4 2c-1 .7-1.6 1.3-1.6 2.5"/><path d="M12 17h.01"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-1a7 7 0 0 1 7-7h2a7 7 0 0 1 7 7v1"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
    alert: '<path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 21h16"/>',
    play: '<path d="M8 5v14l11-7Z"/>',
    video: '<rect x="2" y="6" width="13" height="12" rx="2"/><path d="m15 10 5-3v10l-5-3"/>',
    book: '<path d="M4 5a2 2 0 0 1 2-2h13v18H6a2 2 0 0 0-2 2Z"/><path d="M4 19.5V5"/>',
    audio: '<path d="M9 18V6l10-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="19" cy="16" r="3"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m4 18 5-5 3 3 3-3 5 5"/>',
    file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    shield: '<path d="m12 3 8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6Z"/><path d="m9 12 2 2 4-4"/>',
    lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    spark: '<path d="M12 3v3M12 18v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M3 12h3M18 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/><circle cx="12" cy="12" r="3.2"/>',
    ticket: '<path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4Z"/><path d="M13 6v2M13 11v2M13 16v2"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    upload: '<path d="M12 17V5"/><path d="m7 10 5-5 5 5"/><path d="M4 21h16"/>',
    camera: '<path d="M14.5 5 13 3h-2L9.5 5H5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="4"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>'
  };

  function icon(name, className) {
    const body = ICONS[name] || ICONS.info;
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"' +
      (className ? ' class="' + className + '"' : "") +
      ">" +
      body +
      "</svg>"
    );
  }

  function esc(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function parseDate(value) {
    if (!value) return null;
    if (value instanceof Date) return value;
    const text = String(value);
    const normalised = /[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : text + "Z";
    const date = new Date(normalised);
    return isNaN(date.getTime()) ? null : date;
  }

  function fmtDate(value, withTime) {
    const date = parseDate(value);
    if (!date) return "—";
    const opts = { year: "numeric", month: "short", day: "numeric" };
    if (withTime) {
      opts.hour = "2-digit";
      opts.minute = "2-digit";
    }
    return date.toLocaleString(undefined, opts);
  }

  function fmtTime(value) {
    const date = parseDate(value);
    if (!date) return "—";
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  function fmtRelative(value) {
    const date = parseDate(value);
    if (!date) return "—";
    const diff = date.getTime() - Date.now();
    const abs = Math.abs(diff);
    const minute = 60000;
    const hour = 60 * minute;
    const day = 24 * hour;
    let text;
    if (abs < minute) text = "just now";
    else if (abs < hour) text = Math.round(abs / minute) + " min";
    else if (abs < day) text = Math.round(abs / hour) + " h";
    else text = Math.round(abs / day) + " d";
    if (text === "just now") return text;
    return diff >= 0 ? "in " + text : text + " ago";
  }

  function fmtDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return h + "h " + String(m).padStart(2, "0") + "m";
    if (m > 0) return m + "m " + String(s).padStart(2, "0") + "s";
    return s + "s";
  }

  function fmtClock(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function fmtBytes(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return value + " B";
    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + " KB";
    if (value < 1024 * 1024 * 1024) return (value / (1024 * 1024)).toFixed(1) + " MB";
    return (value / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  function initials(name) {
    return String(name || "?")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("");
  }

  function titleCase(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function avatar(user, size) {
    const name = (user && user.full_name) || "Guest";
    const style = size ? ' style="width:' + size + "px;height:" + size + "px\"" : "";
    if (user && user.photo_url) {
      return (
        '<span class="avatar"' + style + '><img src="' + esc(user.photo_url) +
        '" alt="" onerror="this.remove()" /></span>'
      );
    }
    return '<span class="avatar"' + style + ">" + esc(initials(name)) + "</span>";
  }

  function badge(text, tone) {
    const cls = tone ? " badge-" + tone : "";
    return '<span class="badge' + cls + '">' + esc(titleCase(text)) + "</span>";
  }

  function statusTone(status) {
    const map = {
      active: "success",
      ready: "success",
      submitted: "success",
      present: "success",
      approved: "success",
      pending_approval: "amber",
      pending_email: "amber",
      pending: "amber",
      queued: "amber",
      scheduled: "teal",
      open: "teal",
      in_progress: "teal",
      rejected: "danger",
      terminated: "danger",
      failed: "danger",
      closed: "outline",
      draft: "outline"
    };
    return map[status] || "outline";
  }

  function toast(message, type) {
    const root = document.getElementById("toast-root");
    if (!root) return;
    const node = document.createElement("div");
    node.className = "toast " + (type || "info");
    const iconName = type === "success" ? "check" : type === "error" ? "alert" : "info";
    node.innerHTML =
      icon(iconName) +
      '<span class="grow">' + esc(message) + "</span>" +
      '<button class="toast-close" type="button" aria-label="Dismiss">×</button>';
    node.querySelector(".toast-close").addEventListener("click", () => node.remove());
    root.appendChild(node);
    setTimeout(() => node.remove(), type === "error" ? 7000 : 4500);
  }

  function openModal(options) {
    const root = document.getElementById("modal-root");
    if (!root) return null;
    const opts = options || {};
    root.hidden = false;
    root.innerHTML =
      '<div class="modal-backdrop" data-close="1"></div>' +
      '<div class="modal-card' + (opts.wide ? " wide" : "") + '" role="dialog" aria-modal="true">' +
      '<div class="modal-head"><div><h2>' + esc(opts.title || "") + "</h2>" +
      (opts.subtitle ? '<p class="small muted">' + esc(opts.subtitle) + "</p>" : "") +
      '</div><button class="modal-close" type="button" aria-label="Close">' +
      icon("close") +
      "</button></div>" +
      '<div class="modal-body">' + (opts.body || "") + "</div>" +
      (opts.footer ? '<div class="modal-foot">' + opts.footer + "</div>" : "") +
      "</div>";

    const close = () => {
      root.hidden = true;
      root.innerHTML = "";
      document.removeEventListener("keydown", onKey);
    };
    const onKey = (event) => {
      if (event.key === "Escape") close();
    };
    root.querySelector(".modal-close").addEventListener("click", close);
    root.querySelector("[data-close]").addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    if (opts.onMount) opts.onMount(root, close);
    return { root, close };
  }

  function confirmDialog(message, options) {
    const opts = options || {};
    return new Promise((resolve) => {
      const modal = openModal({
        title: opts.title || "Please confirm",
        body: '<p class="small">' + esc(message) + "</p>",
        footer:
          '<div class="row" style="justify-content:flex-end">' +
          '<button class="btn btn-ghost" data-act="cancel" type="button">Cancel</button>' +
          '<button class="btn ' + (opts.danger ? "btn-danger" : "btn-primary") +
          '" data-act="ok" type="button">' + esc(opts.confirmLabel || "Confirm") + "</button></div>"
      });
      if (!modal) return resolve(false);
      modal.root.querySelector('[data-act="cancel"]').addEventListener("click", () => {
        modal.close();
        resolve(false);
      });
      modal.root.querySelector('[data-act="ok"]').addEventListener("click", () => {
        modal.close();
        resolve(true);
      });
    });
  }

  function emptyState(options) {
    const opts = options || {};
    return (
      '<div class="empty-state">' +
      icon(opts.icon || "info") +
      "<h3>" + esc(opts.title || "Nothing here yet") + "</h3>" +
      "<p>" + esc(opts.text || "") + "</p>" +
      (opts.action
        ? '<div class="row" style="justify-content:center;margin-top:1rem">' + opts.action + "</div>"
        : "") +
      "</div>"
    );
  }

  function pageHead(title, subtitle, actions) {
    return (
      '<div class="page-head"><div><h2>' + esc(title) + "</h2>" +
      (subtitle ? "<p>" + esc(subtitle) + "</p>" : "") +
      "</div>" +
      (actions ? '<div class="row">' + actions + "</div>" : "") +
      "</div>"
    );
  }

  function alert(message, tone) {
    const iconName = tone === "error" ? "alert" : tone === "warn" ? "alert" : tone === "success" ? "check" : "info";
    return (
      '<div class="alert alert-' + (tone || "info") + '">' +
      icon(iconName) +
      '<div class="grow">' + esc(message) + "</div></div>"
    );
  }

  function loading(text) {
    return (
      '<div class="stack" aria-busy="true">' +
      '<div class="skeleton" style="min-height:34px"></div>' +
      '<div class="skeleton"></div>' +
      '<div class="skeleton" style="min-height:160px"></div>' +
      '<p class="small muted center">' + esc(text || "Loading…") + "</p></div>"
    );
  }

  function errorPanel(error, retryLabel) {
    const message = (error && error.message) || "Something went wrong.";
    return (
      '<div class="panel stack">' +
      alert(message, "error") +
      (retryLabel
        ? '<div class="row"><button class="btn btn-ghost" type="button" data-retry="1">' +
          esc(retryLabel) + "</button></div>"
        : "") +
      "</div>"
    );
  }

  function bindRetry(root, handler) {
    const button = root.querySelector("[data-retry]");
    if (button) button.addEventListener("click", handler);
  }

  function methodBadge(method) {
    return '<span class="badge badge-outline mono">' + esc(method) + "</span>";
  }

  DEIY.ui = {
    ICONS,
    icon,
    esc,
    parseDate,
    fmtDate,
    fmtTime,
    fmtRelative,
    fmtDuration,
    fmtClock,
    fmtBytes,
    initials,
    titleCase,
    avatar,
    badge,
    statusTone,
    toast,
    openModal,
    confirmDialog,
    emptyState,
    pageHead,
    alert,
    loading,
    errorPanel,
    bindRetry,
    methodBadge
  };
})();
