(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  function roleLabel(role) {
    return { admin: "Administrator", teacher: "Teacher", student: "Student", proctor: "Proctor" }[role] || role;
  }

  function providerLabel(provider) {
    return {
      email: "Email and password",
      google: "Google",
      facebook: "Facebook",
      other: "Other provider"
    }[provider || "email"] || provider;
  }

  function languageLabel(code) {
    return { en: "English", so: "Somali", ar: "Arabic" }[code || "en"] || code;
  }

  const FALLBACK_PROGRAMS = [
    "Computer Science", "Information Technology", "Software Engineering",
    "Business Administration", "Accounting and Finance", "Nursing", "Public Health",
    "Education", "Civil Engineering", "Electrical Engineering", "Law", "Agriculture",
    "Economics", "Social Work", "General Studies"
  ];

  function stat(label, value, note, accent) {
    return (
      '<div class="stat-card' + (accent ? " accent" : "") + '"><span class="stat-label">' + ui.esc(label) +
      '</span><span class="stat-value">' + ui.esc(value) + '</span><span class="stat-note">' +
      ui.esc(note || "") + "</span></div>"
    );
  }

  function eventIcon(type) {
    return { exam: "exam", assignment: "file", live_session: "video" }[type] || "calendar";
  }

  function upcomingRows(events, limit) {
    return (events || []).slice(0, limit || 5).map(function (event) {
      return (
        '<div class="list-row"><span class="list-icon">' + ui.icon(eventIcon(event.type)) + "</span>" +
        '<div class="list-body"><strong>' + ui.esc(event.title) + "</strong><span>" +
        ui.esc(ui.titleCase(event.type)) + " · " +
        ui.esc(ui.fmtDate(event.ends_at || event.starts_at, true)) + "</span></div>" +
        '<span class="badge badge-outline">' + ui.esc(ui.fmtRelative(event.ends_at || event.starts_at)) +
        "</span></div>"
      );
    }).join("");
  }


  pages.dashboard = {
    app: true,
    title: "Dashboard",
    render: async function (ctx) {
      const user = ctx.user;
      const isAdmin = user.role === "admin";
      const isStudent = user.role === "student";
      const tasks = [
        api.calendar().catch(() => null),
        api.notifications(true).catch(() => null),
        api.exams().catch(() => null),
        api.rooms().catch(() => null)
      ];
      if (isStudent) tasks.push(api.gradebook(null, false).catch(() => null));
      if (isAdmin) {
        tasks.push(api.metrics().catch(() => null));
        tasks.push(api.adminApplications().catch(() => null));
      }
      if (user.role === "teacher" || user.role === "admin") tasks.push(api.courses().catch(() => null));

      const results = await Promise.allSettled(tasks);
      const calendar = results[0].status === "fulfilled" ? results[0].value : null;
      const notifications = results[1].status === "fulfilled" ? results[1].value : null;
      const exams = results[2].status === "fulfilled" ? results[2].value : null;
      const rooms = results[3].status === "fulfilled" ? results[3].value : null;
      let gradebook = null;
      let metrics = null;
      let applications = null;
      let courses = null;
      let index = 4;
      if (isStudent) {
        gradebook = results[index] && results[index].status === "fulfilled" ? results[index].value : null;
        index += 1;
      }
      if (isAdmin) {
        metrics = results[index] && results[index].status === "fulfilled" ? results[index].value : null;
        applications = results[index + 1] && results[index + 1].status === "fulfilled"
          ? results[index + 1].value : null;
        index += 2;
      }
      if (user.role === "teacher" || user.role === "admin") {
        courses = results[index] && results[index].status === "fulfilled" ? results[index].value : null;
      }

      const events = (calendar && calendar.events) || [];
      const unread = (notifications && notifications.notifications) || [];
      const examList = (exams && exams.exams) || [];
      const openExams = examList.filter(function (exam) {
        return exam.status === "scheduled" || exam.status === "open";
      });
      const roomList = (rooms && rooms.rooms) || [];
      const openRooms = roomList.filter(function (room) { return room.status === "open"; });
      const pendingCount = applications ? applications.count : null;

      let cards = "";
      if (isStudent) {
        cards =
          stat("Average score", gradebook ? Number(gradebook.average_score || 0).toFixed(1) + "%" : "—",
            "Across graded exams", true) +
          stat("Open exams", openExams.length, "Available in your window") +
          stat("Study rooms", openRooms.length, "Open right now") +
          stat("Unread notices", unread.length, "Messages from your teachers");
      } else if (user.role === "teacher") {
        cards =
          stat("Courses", courses ? courses.count : "—", "You publish to", true) +
          stat("Exams", examList.length, openExams.length + " open now") +
          stat("Study rooms", openRooms.length, "Open right now") +
          stat("Unread notices", unread.length, "Recent platform messages");
      } else if (isAdmin) {
        cards =
          stat("Pending applications", pendingCount === null ? "—" : pendingCount,
            "Waiting for your review", true) +
          stat("Users", metrics ? metrics.users : "—", "All roles") +
          stat("Resources", metrics ? metrics.resources : "—", "Library items") +
          stat("AI spend", metrics ? "$" + Number(metrics.ai_cost_usd || 0).toFixed(4) : "—",
            "Recorded usage");
      } else {
        cards =
          stat("Exams", examList.length, "Platform exams", true) +
          stat("Open rooms", openRooms.length, "Study sessions") +
          stat("Upcoming", events.length, "Calendar events") +
          stat("Unread notices", unread.length, "Messages");
      }

      const actions = isStudent
        ? '<a class="btn btn-primary btn-sm" href="#/app/library">Browse library</a>' +
          '<a class="btn btn-ghost btn-sm" href="#/app/exams">Open exams</a>' +
          '<a class="btn btn-ghost btn-sm" href="#/app/rooms">Study rooms</a>'
        : isAdmin
          ? '<a class="btn btn-primary btn-sm" href="#/app/admin">Review applications</a>' +
            '<a class="btn btn-ghost btn-sm" href="#/app/manage">Author content</a>' +
            '<a class="btn btn-ghost btn-sm" href="#/app/library">Library</a>'
          : '<a class="btn btn-primary btn-sm" href="#/app/manage">Author content</a>' +
            '<a class="btn btn-ghost btn-sm" href="#/app/library">Library</a>' +
            '<a class="btn btn-ghost btn-sm" href="#/app/exams">Exams</a>';

      const welcome =
        '<div class="welcome-panel"><div>' +
        '<span class="eyebrow">' + ui.esc(roleLabel(user.role)) + " workspace</span>" +
        "<h2>Hello, " + ui.esc((user.full_name || "").split(" ")[0] || "there") + ".</h2>" +
        "<p>" + (isStudent
          ? "Your application is approved. Use the library, sit exams and join study rooms from here."
          : isAdmin
            ? "Review applications, tune platform policy and keep an eye on AI cost from one dashboard."
            : "Publish resources, author assessments and follow learner progress from here.") + "</p>" +
        '<div class="hero-actions" style="margin-top:1rem">' + actions + "</div></div>" +
        '<div class="id-card"><div class="id-label">Academic ID</div><div class="id-value">' +
        ui.esc(user.academic_id || "Issued after approval") + "</div>" +
        '<div class="id-label">Account status</div><div class="row" style="margin-top:0.3rem">' +
        ui.badge(user.status, ui.statusTone(user.status)) +
        (user.email_verified ? ui.badge("email verified", "teal") : ui.badge("email unverified", "amber")) +
        "</div></div></div>";

      const gradebookPanel = isStudent && gradebook
        ? '<div class="panel"><div class="panel-head"><h3>Progress snapshot</h3>' +
          '<a class="small strong" href="#/app/gradebook">Full gradebook →</a></div>' +
          '<div class="info-list"><div class="info-item"><span>Average exam score</span><strong>' +
          ui.esc(Number(gradebook.average_score || 0).toFixed(2)) + "%</strong></div>" +
          '<div class="info-item"><span>Attendance</span><strong>' +
          ui.esc(Number(gradebook.attendance_rate || 0).toFixed(1)) + "%</strong></div>" +
          '<div class="info-item"><span>Graded assignments</span><strong>' +
          ui.esc((gradebook.assignments || []).length) + "</strong></div></div>" +
          (gradebook.ai_insights && gradebook.ai_insights.summary
            ? '<div class="room-summary" style="margin-top:0.8rem"><h4>' + ui.icon("spark") +
              " AI insight</h4><p>" + ui.esc(gradebook.ai_insights.summary) + "</p></div>"
            : "") +
          "</div>"
        : "";

      const adminPanel = isAdmin && applications
        ? '<div class="panel"><div class="panel-head"><h3>Applications waiting</h3>' +
          '<a class="small strong" href="#/app/admin">Review all →</a></div>' +
          (applications.applications && applications.applications.length
            ? '<div class="list">' + applications.applications.slice(0, 4).map(function (item) {
                return '<div class="list-row">' + ui.avatar(item, 36) +
                  '<div class="list-body"><strong>' + ui.esc(item.full_name) + "</strong><span>" +
                  ui.esc(item.email) + " · " + ui.esc(item.country || "") + "</span></div>" +
                  '<a class="btn btn-sm btn-primary" href="#/app/admin?tab=applications">Review</a></div>';
              }).join("") + "</div>"
            : '<p class="small muted">No applications are waiting. Nice work.</p>') +
          "</div>"
        : "";

      return (
        ui.pageHead("Dashboard", "A quick view of what needs your attention.") +
        welcome +
        '<div class="grid-4" style="margin:1rem 0">' + cards + "</div>" +
        '<div class="grid-2" style="align-items:start">' +
        '<div class="panel"><div class="panel-head"><h3>Upcoming</h3>' +
        '<a class="small strong" href="#/app/calendar">Open calendar →</a></div>' +
        (events.length ? '<div class="list">' + upcomingRows(events, 6) + "</div>"
          : ui.emptyState({ icon: "calendar", title: "Nothing scheduled", text: "Exams, live sessions and assignment deadlines will appear here." })) +
        "</div>" +
        '<div class="stack">' +
        '<div class="panel"><div class="panel-head"><h3>Unread notices</h3>' +
        '<a class="small strong" href="#/app/notifications">See all →</a></div>' +
        (unread.length
          ? '<div class="list">' + unread.slice(0, 4).map(function (item) {
              return '<div class="list-row"><span class="list-icon">' + ui.icon("bell") + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(item.title) + "</strong><span>" +
                ui.esc(item.body).slice(0, 90) + " · " + ui.esc(ui.fmtRelative(item.created_at)) +
                "</span></div></div>";
            }).join("") + "</div>"
          : '<p class="small muted">You are all caught up.</p>') +
        "</div>" + gradebookPanel + adminPanel +
        "</div></div>"
      );
    }
  };

  pages.calendar = {
    app: true,
    title: "Calendar",
    render: async function () {
      let data;
      try {
        data = await api.calendar();
      } catch (error) {
        return ui.pageHead("Calendar", "Exams, live sessions and assignment deadlines.") +
          ui.errorPanel(error, "Try again");
      }
      const events = data.events || [];
      const groups = {};
      events.forEach(function (event) {
        const date = event.starts_at || event.ends_at;
        const key = date ? String(date).slice(0, 10) : "Unscheduled";
        (groups[key] = groups[key] || []).push(event);
      });
      const body = Object.keys(groups).length
        ? Object.keys(groups).map(function (key) {
            return '<div class="panel" style="margin-bottom:0.9rem"><div class="panel-head"><h3>' +
              ui.esc(key === "Unscheduled" ? "Unscheduled" : ui.fmtDate(key)) + "</h3>" +
              '<span class="badge badge-outline">' + groups[key].length + " events</span></div>" +
              '<div class="list">' + groups[key].map(function (event) {
                const target = event.type === "exam" ? "#/app/exams/" + encodeURIComponent(event.id)
                  : event.type === "live_session" ? "#/app/library" : "#/app/assignments";
                return '<div class="list-row"><span class="list-icon">' + ui.icon(eventIcon(event.type)) +
                  "</span><div class=\"list-body\"><strong>" + ui.esc(event.title) + "</strong><span>" +
                  ui.esc(ui.titleCase(event.type)) +
                  (event.starts_at ? " · starts " + ui.esc(ui.fmtDate(event.starts_at, true)) : "") +
                  (event.ends_at ? " · due/ends " + ui.esc(ui.fmtDate(event.ends_at, true)) : "") +
                  '</span></div><a class="btn btn-sm btn-ghost" href="' + target + '">Open</a></div>';
              }).join("") + "</div></div>";
            }).join("")
        : ui.emptyState({
            icon: "calendar",
            title: "No upcoming events",
            text: "When a teacher schedules an exam, live session or assignment, it will appear here."
          });
      return (
        ui.pageHead("Calendar", "Every deadline and session in one place.") +
        '<div class="row" style="margin-bottom:1rem"><a class="btn btn-ghost btn-sm" href="#/app/dashboard">← Dashboard</a>' +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="Where can I see my exam dates?">' +
        ui.icon("spark") + " Ask about deadlines</button></div>" + body
      );
    }
  };

 
  pages.notifications = {
    app: true,
    title: "Notifications",
    render: async function () {
      let data;
      try {
        data = await api.notifications(false);
      } catch (error) {
        return ui.pageHead("Notifications", "") + ui.errorPanel(error, "Try again");
      }
      const rows = data.notifications || [];
      return (
        ui.pageHead("Notifications", "Messages, approvals and platform updates.",
          rows.length ? '<button class="btn btn-ghost btn-sm" id="mark-all" type="button">Mark all read</button>' : "") +
        '<div class="panel">' +
        (rows.length
          ? '<div class="list">' + rows.map(function (item) {
              return '<div class="list-row" data-notification="' + ui.esc(item.id) + '">' +
                '<span class="list-icon" style="' + (item.read ? "" : "background:var(--amber-soft);color:var(--amber)") +
                '">' + ui.icon("bell") + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(item.title) + "</strong><span>" +
                ui.esc(item.body) + "</span><span>" + ui.esc(ui.fmtDate(item.created_at, true)) +
                " · " + ui.esc(item.channel || "in-app") + "</span></div>" +
                (item.read ? ui.badge("read", "outline") :
                  '<button class="btn btn-xs btn-ghost" type="button" data-read="' + ui.esc(item.id) +
                  '">Mark read</button>') +
                '<button class="btn btn-xs btn-danger" type="button" data-delete-notification="' +
                ui.esc(item.id) + '">Delete</button>' + "</div>";
            }).join("") + "</div>"
          : ui.emptyState({ icon: "bell", title: "No notifications", text: "Approval, exam and room summaries will arrive here." })) +
        "</div>"
      );
    },
    after: function (root) {
      const markAll = root.querySelector("#mark-all");
      if (markAll) {
        markAll.addEventListener("click", async function () {
          markAll.disabled = true;
          try {
            await api.markAllNotificationsRead();
            ui.toast("All notifications marked as read.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not update notifications.", "error");
            markAll.disabled = false;
          }
        });
      }
      root.querySelectorAll("[data-read]").forEach(function (button) {
        button.addEventListener("click", async function () {
          button.disabled = true;
          try {
            await api.markNotificationRead(button.getAttribute("data-read"));
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not mark as read.", "error");
            button.disabled = false;
          }
        });
      });
      root.querySelectorAll("[data-delete-notification]").forEach(function (button) {
        button.addEventListener("click", async function () {
          button.disabled = true;
          try {
            await api.deleteNotification(button.getAttribute("data-delete-notification"));
            ui.toast("Notification deleted.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not delete the notification.", "error");
            button.disabled = false;
          }
        });
      });
    }
  };

 
  pages.profile = {
    app: true,
    title: "Profile",
    render: async function (ctx) {
      const user = ctx.user;
      return (
        ui.pageHead("Your profile", "Account details and the identifiers used across the platform.") +
        '<div class="grid-2" style="align-items:start">' +
        '<div class="panel stack"><div class="row">' + ui.avatar(user, 64) +
        '<div><h3>' + ui.esc(user.full_name) + "</h3><p class=\"small muted\">" +
        ui.esc(user.email) + "</p></div></div>" +
        '<div class="info-list">' +
        '<div class="info-item"><span>Role</span><strong>' + ui.esc(roleLabel(user.role)) + "</strong></div>" +
        '<div class="info-item"><span>Status</span><strong>' + ui.badge(user.status, ui.statusTone(user.status)) +
        "</strong></div>" +
        '<div class="info-item"><span>Academic ID</span><strong class="mono">' +
        ui.esc(user.academic_id || "Not issued yet") + "</strong></div>" +
        '<div class="info-item"><span>Registration number</span><strong class="mono">' +
        ui.esc(user.registration_number || "—") + "</strong></div>" +
        '<div class="info-item"><span>Program</span><strong>' + ui.esc(user.program || "—") + "</strong></div>" +
        '<div class="info-item"><span>Nationality</span><strong>' + ui.esc(user.nationality || "—") +
        "</strong></div>" +
        '<div class="info-item"><span>Phone number</span><strong>' + ui.esc(user.phone_number || "—") +
        "</strong></div>" +
        '<div class="info-item"><span>Father\'s phone number</span><strong>' +
        ui.esc(user.father_phone_number || "—") + "</strong></div>" +
        '<div class="info-item"><span>Sign-in provider</span><strong>' +
        ui.esc(providerLabel(user.auth_provider)) + "</strong></div>" +
        '<div class="info-item"><span>Preferred language</span><strong>' +
        ui.esc(languageLabel(user.language)) + "</strong></div>" +
        '<div class="info-item"><span>Email verified</span><strong>' +
        (user.email_verified ? "Yes" : "No") + "</strong></div>" +
        '<div class="info-item"><span>Country</span><strong>' + ui.esc(user.country || "—") + "</strong></div>" +
        '<div class="info-item"><span>Date of birth</span><strong>' + ui.esc(ui.fmtDate(user.date_of_birth)) +
        "</strong></div>" +
        '<div class="info-item"><span>Member since</span><strong>' + ui.esc(ui.fmtDate(user.created_at)) +
        "</strong></div></div>" +
        '<div class="row"><button class="btn btn-primary btn-sm" type="button" id="edit-profile">' +
        ui.icon("settings") + " Edit profile</button>" +
        '<button class="btn btn-ghost btn-sm" type="button" id="change-password">Change password</button>' +
        '<button class="btn btn-ghost btn-sm" type="button" id="sign-out">' +
        ui.icon("logout") + " Sign out</button></div></div>" +
        '<div class="stack"><div class="panel stack"><h3>What your academic ID is for</h3>' +
        '<p class="small muted">Your academic ID is the unique student identifier generated after approval. ' +
        "You need it to join study rooms, and it appears in the watermark on library downloads.</p>" +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="What is an academic ID?">' +
        ui.icon("spark") + " Ask the AI guide</button></div>" +
        '<div class="panel stack"><h3>Keep your account safe</h3>' +
        '<p class="small muted">Never share your password or academic ID. If you think someone else has access, ' +
        "contact an administrator or open a support ticket from the helpdesk.</p>" +
        '<a class="btn btn-ghost btn-sm" href="#/app/help">Open helpdesk</a></div></div></div>'
      );
    },
    after: function (root, ctx) {
      const user = ctx.user;

      const editProfile = root.querySelector("#edit-profile");
      if (editProfile) {
        editProfile.addEventListener("click", async function () {
          let options = DEIY.state.options;
          if (!options) {
            try {
              options = await api.options();
              DEIY.state.options = options;
            } catch (_) {
              options = null;
            }
          }
          const programs = ((options && options.programs) || [])
            .map(function (program) { return typeof program === "string" ? program : program.name; });
          if (!programs.length) FALLBACK_PROGRAMS.forEach(function (name) { programs.push(name); });
          if (user.program && programs.indexOf(user.program) === -1) programs.push(user.program);
          const programOptions = '<option value="">— Not set —</option>' +
            programs.map(function (name) {
              return '<option value="' + ui.esc(name) + '"' +
                (user.program === name ? " selected" : "") + ">" + ui.esc(name) + "</option>";
            }).join("");
          const languages = (options && options.languages) || [
            { code: "en", name: "English" }, { code: "so", name: "Somali" }, { code: "ar", name: "Arabic" }
          ];
          const languageOptions = languages.map(function (item) {
            return '<option value="' + ui.esc(item.code) + '"' +
              ((user.language || "en") === item.code ? " selected" : "") + ">" +
              ui.esc(item.name) + "</option>";
          }).join("");

          ui.openModal({
            title: "Edit your profile",
            subtitle: "Your registration number and academic ID are issued by the platform and cannot be edited.",
            wide: true,
            body:
              '<form id="profile-form" class="stack">' +
              '<div class="grid-2">' +
              '<div class="field"><label for="profile-name">Full name</label>' +
              '<input class="input" id="profile-name" name="full_name" required value="' +
              ui.esc(user.full_name || "") + '" />' +
              '<span class="hint">Four parts: first, second, third and family name.</span></div>' +
              '<div class="field"><label for="profile-program">Program</label>' +
              '<select class="select" id="profile-program" name="program">' + programOptions + "</select></div>" +
              '<div class="field"><label for="profile-nationality">Nationality</label>' +
              '<input class="input" id="profile-nationality" name="nationality" value="' +
              ui.esc(user.nationality || "") + '" /></div>' +
              '<div class="field"><label for="profile-phone">Phone number</label>' +
              '<input class="input" id="profile-phone" name="phone_number" type="tel" value="' +
              ui.esc(user.phone_number || "") + '" /></div>' +
              '<div class="field"><label for="profile-father-phone">Father\'s phone number</label>' +
              '<input class="input" id="profile-father-phone" name="father_phone_number" type="tel" value="' +
              ui.esc(user.father_phone_number || "") + '" /></div>' +
              '<div class="field"><label for="profile-language">Preferred language</label>' +
              '<select class="select" id="profile-language" name="language">' + languageOptions + "</select></div>" +
              "</div>" +
              '<div class="field"><label for="profile-photo">Photo URL (optional)</label>' +
              '<input class="input" id="profile-photo" name="photo" type="url" ' +
              'placeholder="https://example.com/photo.jpg" /></div>' +
              '<div id="profile-error" hidden></div>' +
              '<div class="row"><button class="btn btn-primary" type="submit">Save profile</button>' +
              '<button class="btn btn-ghost" type="button" data-close-profile>Cancel</button></div></form>',
            onMount: function (modal, close) {
              const form = modal.querySelector("#profile-form");
              const errorBox = modal.querySelector("#profile-error");
              form.querySelector("[data-close-profile]").addEventListener("click", close);
              form.addEventListener("submit", async function (event) {
                event.preventDefault();
                const submit = form.querySelector('button[type="submit"]');
                const payload = {
                  full_name: form.elements.namedItem("full_name").value.trim(),
                  program: form.elements.namedItem("program").value,
                  nationality: form.elements.namedItem("nationality").value.trim(),
                  phone_number: form.elements.namedItem("phone_number").value.trim(),
                  father_phone_number: form.elements.namedItem("father_phone_number").value.trim(),
                  language: form.elements.namedItem("language").value
                };
                const photo = form.elements.namedItem("photo").value.trim();
                if (photo) payload.photo = photo;
                Object.keys(payload).forEach(function (key) {
                  if (payload[key] === "") delete payload[key];
                });
                submit.disabled = true;
                try {
                  const result = await api.updateProfile(payload);
                  DEIY.state.user = result.user;
                  ui.toast("Profile updated.", "success");
                  close();
                  const language = result.user && result.user.language;
                  if (language && DEIY.i18n && language !== DEIY.i18n.getLanguage()) {
                    DEIY.i18n.setLanguage(language);
                  } else {
                    DEIY.rerender();
                  }
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not update your profile.", "error");
                  submit.disabled = false;
                }
              });
            }
          });
        });
      }

      const changePassword = root.querySelector("#change-password");
      if (changePassword) {
        changePassword.addEventListener("click", function () {
          ui.openModal({
            title: "Change password",
            subtitle: "Use at least 8 characters with upper case, lower case and a number.",
            body:
              '<form id="password-form" class="stack">' +
              '<div class="field"><label for="current-password">Current password</label>' +
              '<input class="input" id="current-password" name="current_password" type="password" ' +
              'autocomplete="current-password" required /></div>' +
              '<div class="field"><label for="new-password">New password</label>' +
              '<input class="input" id="new-password" name="new_password" type="password" ' +
              'autocomplete="new-password" required minlength="8" /></div>' +
              '<div class="field"><label for="confirm-new-password">Confirm new password</label>' +
              '<input class="input" id="confirm-new-password" name="confirm_password" type="password" ' +
              'autocomplete="new-password" required minlength="8" /></div>' +
              '<div id="password-error" hidden></div>' +
              '<button class="btn btn-primary" type="submit">Update password</button></form>',
            onMount: function (modal, close) {
              const form = modal.querySelector("#password-form");
              const errorBox = modal.querySelector("#password-error");
              form.addEventListener("submit", async function (event) {
                event.preventDefault();
                const submit = form.querySelector('button[type="submit"]');
                const current = form.elements.namedItem("current_password").value;
                const next = form.elements.namedItem("new_password").value;
                const confirm = form.elements.namedItem("confirm_password").value;
                const fail = function (message) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(message, "error");
                  submit.disabled = false;
                };
                if (next !== confirm) return fail("The two new passwords do not match.");
                if (next.length < 8 || !/[A-Z]/.test(next) || !/[a-z]/.test(next) || !/\d/.test(next)) {
                  return fail("Use at least 8 characters with one upper-case letter, one lower-case letter and a number.");
                }
                submit.disabled = true;
                try {
                  await api.changePassword(current, next);
                  ui.toast("Password updated. Use it the next time you sign in.", "success");
                  close();
                } catch (error) {
                  fail(error.message || "Could not change your password.");
                }
              });
            }
          });
        });
      }

      const signOut = root.querySelector("#sign-out");
      if (signOut) {
        signOut.addEventListener("click", async function () {
          const ok = await ui.confirmDialog("Sign out of DEIY on this device?", {
            confirmLabel: "Sign out"
          });
          if (!ok) return;
          api.logout();
          DEIY.state.user = null;
          window.dispatchEvent(new CustomEvent("deiy:session-changed"));
          ui.toast("Signed out.", "success");
          DEIY.go("#/");
        });
      }
    }
  };
})();
