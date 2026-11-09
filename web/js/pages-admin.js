/* ==========================================================================
   DEIY admin console: applications, users & roles, runtime configuration,
   AI usage/cost, audit trail and platform metrics.
   ========================================================================== */
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  const TABS = [
    { id: "overview", label: "Overview" },
    { id: "applications", label: "Applications" },
    { id: "users", label: "Users & roles" },
    { id: "config", label: "Configuration" },
    { id: "ai", label: "AI usage" },
    { id: "audit", label: "Audit log" }
  ];

  const FALLBACK_PROGRAMS = [
    "Computer Science", "Information Technology", "Software Engineering",
    "Business Administration", "Accounting and Finance", "Nursing", "Public Health",
    "Education", "Civil Engineering", "Electrical Engineering", "Law", "Agriculture",
    "Economics", "Social Work", "General Studies"
  ];

  const FALLBACK_LANGUAGES = [
    { code: "en", name: "English" },
    { code: "so", name: "Somali" },
    { code: "ar", name: "Arabic" }
  ];

  function programNames(options) {
    const list = (options && options.programs) || [];
    if (!list.length) return FALLBACK_PROGRAMS.slice();
    return list.map(function (program) {
      return typeof program === "string" ? program : program.name;
    });
  }

  function languageList(options) {
    const list = (options && options.languages) || [];
    return list.length ? list : FALLBACK_LANGUAGES;
  }

  function roleLabel(role) {
    return { admin: "Administrator", teacher: "Teacher", student: "Student", proctor: "Proctor" }[role] || role;
  }

  function tabsBar(active) {
    return (
      '<div class="admin-tabs" role="tablist">' +
      TABS.map(function (tab) {
        return '<button class="admin-tab' + (tab.id === active ? " active" : "") +
          '" type="button" role="tab" aria-selected="' + (tab.id === active) +
          '" data-admin-tab="' + tab.id + '">' + ui.esc(tab.label) + "</button>";
      }).join("") +
      "</div>"
    );
  }

  function reviewBadge(review) {
    if (!review || review.recommendation === undefined) return ui.badge("no ai review", "outline");
    const tone = review.recommendation === "approve" ? "success"
      : review.recommendation === "reject" ? "danger" : "amber";
    return ui.badge(review.recommendation || "review", tone) +
      '<span class="tiny muted">risk ' + ui.esc(Number(review.risk_score || 0).toFixed(0)) + "/100</span>";
  }

  /* ------------------------------------------------------------------ overview */
  async function overviewPanel() {
    let metrics = null;
    let usage = null;
    let applications = null;
    try {
      const results = await Promise.all([
        api.metrics(),
        api.aiUsage().catch(() => null),
        api.adminApplications().catch(() => null)
      ]);
      metrics = results[0];
      usage = results[1];
      applications = results[2];
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }

    const jobs = metrics.jobs || {};
    const cards =
      '<div class="stat-card accent"><span class="stat-label">Users</span><span class="stat-value">' +
      ui.esc(metrics.users) + '</span><span class="stat-note">All roles</span></div>' +
      '<div class="stat-card"><span class="stat-label">Pending approval</span><span class="stat-value">' +
      ui.esc(metrics.pending_approvals) + '</span><span class="stat-note">Students waiting</span></div>' +
      '<div class="stat-card"><span class="stat-label">Resources</span><span class="stat-value">' +
      ui.esc(metrics.resources) + '</span><span class="stat-note">Library items</span></div>' +
      '<div class="stat-card"><span class="stat-label">AI cost</span><span class="stat-value">$' +
      ui.esc(Number(metrics.ai_cost_usd || 0).toFixed(4)) + '</span><span class="stat-note">Recorded spend</span></div>';

    const health = metrics.ai || {};
    const providerBadges = Object.keys(health || {}).map(function (key) {
      const value = health[key];
      const text = value === true ? "live" : value === false ? "off" : String(value);
      const tone = value === true ? "success" : value === false ? "outline" : "teal";
      return '<span class="badge badge-' + tone + '">' + ui.esc(key) + ": " + ui.esc(text) + "</span>";
    }).join(" ");

    return (
      '<div class="grid-4" style="margin-bottom:1rem">' + cards + "</div>" +
      '<div class="grid-2" style="align-items:start">' +
      '<div class="panel stack"><div class="panel-head"><h3>Platform activity</h3></div>' +
      '<div class="info-list">' +
      '<div class="info-item"><span>Exams</span><strong>' + ui.esc(metrics.exams) + "</strong></div>" +
      '<div class="info-item"><span>Study rooms</span><strong>' + ui.esc(metrics.study_rooms) + "</strong></div>" +
      '<div class="info-item"><span>Room summaries ready</span><strong>' +
      ui.esc(metrics.room_summaries_ready) + "</strong></div>" +
      '<div class="info-item"><span>Queue: queued</span><strong>' + ui.esc(jobs.queued || 0) + "</strong></div>" +
      '<div class="info-item"><span>Queue: failed</span><strong>' + ui.esc(jobs.failed || 0) + "</strong></div>" +
      "</div></div>" +
      '<div class="stack">' +
      '<div class="panel stack"><div class="panel-head"><h3>AI providers</h3></div>' +
      '<div class="row">' + (providerBadges || '<span class="small muted">No provider information.</span>') + "</div>" +
      (usage
        ? '<div class="info-list"><div class="info-item"><span>Total AI cost</span><strong>$' +
          ui.esc(Number(usage.total_cost_usd || 0).toFixed(6)) + "</strong></div>" +
          '<div class="info-item"><span>Task types</span><strong>' +
          ui.esc((usage.breakdown || []).length) + "</strong></div></div>"
        : "") +
      "</div>" +
      '<div class="panel stack"><div class="panel-head"><h3>Approvals waiting</h3></div>' +
      (applications && applications.applications && applications.applications.length
        ? '<p class="small muted">' + applications.count + " student application" +
          (applications.count === 1 ? " is" : "s are") + " waiting for review.</p>" +
          '<button class="btn btn-primary btn-sm" type="button" data-admin-tab="applications">Open applications</button>'
        : '<p class="small muted">No applications are waiting. The queue is clear.</p>') +
      "</div></div></div>"
    );
  }

  /* -------------------------------------------------------------- applications */
  function applicationCard(user) {
    const review = user.ai_review || {};
    const flags = review.flags || [];
    return (
      '<div class="panel stack" data-application="' + ui.esc(user.id) + '">' +
      '<div class="row-between"><div class="row">' + ui.avatar(user, 46) +
      '<div><h3 style="margin:0">' + ui.esc(user.full_name) + "</h3>" +
      '<p class="small muted">' + ui.esc(user.email) + " · " + ui.esc(user.country || "—") + "</p></div></div>" +
      '<div class="row">' + ui.badge(user.status, ui.statusTone(user.status)) +
      (user.email_verified ? ui.badge("email verified", "teal") : ui.badge("unverified", "amber")) + "</div></div>" +
      '<div class="config-grid" style="margin-top:0.35rem">' +
      '<div class="config-row"><label>Registration number</label><span class="small mono">' +
      ui.esc(user.registration_number || "—") + "</span></div>" +
      '<div class="config-row"><label>Program</label><span class="small">' +
      ui.esc(user.program || "—") + "</span></div>" +
      '<div class="config-row"><label>Nationality</label><span class="small">' +
      ui.esc(user.nationality || user.country || "—") + "</span></div>" +
      '<div class="config-row"><label>Phone number</label><span class="small">' +
      ui.esc(user.phone_number || "—") + "</span></div>" +
      '<div class="config-row"><label>Father\'s phone</label><span class="small">' +
      ui.esc(user.father_phone_number || "—") + "</span></div>" +
      '<div class="config-row"><label>Sign-in provider</label><span class="small">' +
      ui.esc(user.auth_provider || "email") + "</span></div>" +
      '<div class="config-row"><label>Date of birth</label><span class="small">' +
      ui.esc(ui.fmtDate(user.date_of_birth)) + "</span></div>" +
      '<div class="config-row"><label>Applied</label><span class="small">' +
      ui.esc(ui.fmtDate(user.created_at, true)) + "</span></div></div>" +
      '<div class="panel-flat" style="padding:0.8rem;border:1px solid var(--line);border-radius:10px">' +
      '<div class="row" style="margin-bottom:0.4rem"><strong class="small">AI onboarding review</strong>' +
      '<span class="grow"></span>' + reviewBadge(user.ai_review) + "</div>" +
      '<p class="small muted">' + ui.esc(review.rationale || "No rationale was recorded.") + "</p>" +
      (flags.length ? '<div class="resource-tags">' + flags.map(function (flag) {
        return '<span class="tag">' + ui.esc(flag) + "</span>";
      }).join("") + "</div>" : "") + "</div>" +
      '<div class="row" style="justify-content:flex-end">' +
      '<button class="btn btn-ghost btn-sm" type="button" data-reject="' + ui.esc(user.id) +
      '" data-name="' + ui.esc(user.full_name) + '">Reject</button>' +
      '<button class="btn btn-primary btn-sm" type="button" data-approve="' + ui.esc(user.id) +
      '" data-name="' + ui.esc(user.full_name) + '">Approve &amp; issue academic ID</button>' +
      "</div></div>"
    );
  }

  async function applicationsPanel() {
    let data;
    try {
      data = await api.adminApplications();
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }
    const rows = data.applications || [];
    return (
      ui.alert("Approving an application generates the student's unique academic ID and emails it to them. " +
        "The AI review is advisory — you make the final decision.", "info") +
      '<div class="row-between" style="margin:1rem 0 0.8rem"><p class="small muted">' + rows.length +
      " application" + (rows.length === 1 ? "" : "s") + " pending</p>" +
      '<button class="btn btn-ghost btn-sm" type="button" id="refresh-applications">Refresh</button></div>' +
      (rows.length
        ? '<div class="stack">' + rows.map(applicationCard).join("") + "</div>"
        : ui.emptyState({
            icon: "check",
            title: "No applications waiting",
            text: "New student applications will appear here after they verify their email."
          }))
    );
  }

  /* -------------------------------------------------------------- users & roles */
  async function usersPanel(query) {
    const role = query.get("role") || "";
    const status = query.get("status") || "";
    let data;
    try {
      const results = await Promise.all([
        api.adminUsers({ role: role || undefined, status: status || undefined }),
        api.options().catch(function () { return null; })
      ]);
      data = results[0];
      DEIY.state.options = results[1] || DEIY.state.options || null;
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }
    const users = data.users || [];
    const roles = ["", "student", "teacher", "proctor", "admin"];
    const statuses = ["", "active", "pending_email", "pending_approval", "rejected", "suspended", "deleted"];
    const roleOptions = roles.map(function (value) {
      return '<option value="' + value + '"' + (role === value ? " selected" : "") + ">" +
        (value ? roleLabel(value) : "All roles") + "</option>";
    }).join("");
    const statusOptions = statuses.map(function (value) {
      return '<option value="' + value + '"' + (status === value ? " selected" : "") + ">" +
        (value ? ui.titleCase(value) : "All statuses") + "</option>";
    }).join("");

    return (
      '<div class="panel" style="margin-bottom:1rem"><div class="row" style="align-items:flex-end">' +
      '<div class="field" style="min-width:180px"><label for="filter-role">Role</label>' +
      '<select class="select" id="filter-role">' + roleOptions + "</select></div>" +
      '<div class="field" style="min-width:180px"><label for="filter-status">Status</label>' +
      '<select class="select" id="filter-status">' + statusOptions + "</select></div>" +
      '<button class="btn btn-ghost btn-sm" type="button" id="apply-user-filter">Apply filters</button>' +
      '<span class="grow"></span><button class="btn btn-primary btn-sm" type="button" id="add-staff">' +
      ui.icon("plus") + " Create staff account</button></div></div>" +
      '<div class="row-between" style="margin-bottom:0.7rem"><p class="small muted">' + users.length +
      " user" + (users.length === 1 ? "" : "s") + "</p></div>" +
      '<div class="table-wrap"><table><thead><tr><th>User</th><th>Program</th><th>Role</th><th>Status</th>' +
      "<th>Academic ID</th><th>Joined</th><th>Actions</th></tr></thead><tbody>" +
      users.map(function (user) {
        const roleSelect = ["student", "teacher", "proctor", "admin"].map(function (value) {
          return '<option value="' + value + '"' + (user.role === value ? " selected" : "") + ">" +
            roleLabel(value) + "</option>";
        }).join("");
        return "<tr data-user=\"" + ui.esc(user.id) + "\">" +
          "<td><div class=\"row\">" + ui.avatar(user, 34) + "<div><strong>" + ui.esc(user.full_name) +
          "</strong><div class=\"tiny muted\">" + ui.esc(user.email) + "</div>" +
          '<div class="tiny mono muted">' + ui.esc(user.registration_number || "—") + "</div></div></div></td>" +
          '<td class="small">' + ui.esc(user.program || "—") + "</td>" +
          '<td><select class="select" data-role-select="' + ui.esc(user.id) + '" aria-label="Role">' +
          roleSelect + "</select></td>" +
          "<td>" + ui.badge(user.status, ui.statusTone(user.status)) + "</td>" +
          '<td class="mono small">' + ui.esc(user.academic_id || "—") + "</td>" +
          "<td>" + ui.esc(ui.fmtDate(user.created_at)) + "</td>" +
          '<td><div class="list-actions">' +
          (user.status === "pending_approval"
            ? '<button class="btn btn-xs btn-primary" type="button" data-approve="' + ui.esc(user.id) +
              '" data-name="' + ui.esc(user.full_name) + '">Approve</button>' +
              '<button class="btn btn-xs btn-ghost" type="button" data-reject="' + ui.esc(user.id) +
              '" data-name="' + ui.esc(user.full_name) + '">Reject</button>'
            : "") +
          '<button class="btn btn-xs btn-ghost" type="button" data-user-details="' + ui.esc(user.id) +
          '">Details</button>' +
          '<button class="btn btn-xs btn-ghost" type="button" data-user-edit="' + ui.esc(user.id) +
          '">Edit</button>' +
          '<button class="btn btn-xs btn-danger" type="button" data-user-delete="' + ui.esc(user.id) +
          '" data-name="' + ui.esc(user.full_name) + '">Delete</button></div></td></tr>';
      }).join("") +
      "</tbody></table></div>" +
      (users.length ? "" : ui.emptyState({ icon: "user", title: "No users found", text: "Adjust the filters and try again." }))
    );
  }

  /* --------------------------------------------------------------- configuration */
  function valueFor(spec, value) {
    const type = String(spec.type || "").toLowerCase();
    if (type === "bool") {
      return '<label class="toggle"><input type="checkbox" data-config-boolean="' + ui.esc(value.key) + '"' +
        (value.value ? " checked" : "") + " /> Enabled</label>";
    }
    const inputType = type === "int" ? "number" : "text";
    return '<input class="input" type="' + inputType + '" data-config-input="' + ui.esc(value.key) + '" ' +
      (spec.minimum !== undefined ? 'min="' + ui.esc(spec.minimum) + '" ' : "") +
      (spec.maximum !== undefined ? 'max="' + ui.esc(spec.maximum) + '" ' : "") +
      'value="' + ui.esc(value.value) + '" />';
  }

  async function configPanel() {
    let data;
    try {
      data = await api.adminConfig();
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }
    const config = data.config || {};
    const values = config.values || {};
    const allowed = config.allowed || {};
    const overrides = config.overrides || [];
    const keys = Object.keys(allowed);
    return (
      ui.alert("Changes are validated, stored in the database and written to the audit log. " +
        "Some settings (such as token lifetimes) take effect on the next request.", "info") +
      '<form id="config-form" class="stack" style="margin-top:1rem">' +
      '<div class="config-grid">' +
      keys.map(function (key) {
        const spec = allowed[key] || {};
        const overridden = overrides.indexOf(key) !== -1;
        return '<div class="config-row"><label for="cfg-' + ui.esc(key) + '">' + ui.esc(key) +
          (overridden ? ' <span class="badge badge-teal">override</span>' : "") + "</label>" +
          valueFor(spec, { key: key, value: values[key] }) +
          '<span class="hint">' + ui.esc(spec.description || "") +
          (spec.minimum !== undefined ? " · min " + spec.minimum : "") +
          (spec.maximum !== undefined ? " · max " + spec.maximum : "") + "</span></div>";
      }).join("") +
      "</div>" +
      '<div id="config-error" hidden></div>' +
      '<div class="row"><button class="btn btn-primary" type="submit">Save configuration</button>' +
      '<button class="btn btn-ghost" type="reset">Reset changes</button></div></form>'
    );
  }

  /* -------------------------------------------------------------------- AI usage */
  async function aiPanel() {
    let data;
    try {
      data = await api.aiUsage();
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }
    const rows = data.breakdown || [];
    const health = data.health || {};
    return (
      '<div class="stat-card accent" style="max-width:320px;margin-bottom:1rem">' +
      '<span class="stat-label">Total recorded AI cost</span><span class="stat-value">$' +
      ui.esc(Number(data.total_cost_usd || 0).toFixed(6)) + "</span>" +
      '<span class="stat-note">Across every task</span></div>' +
      '<div class="panel stack" style="margin-bottom:1rem"><div class="panel-head"><h3>Provider health</h3></div>' +
      '<div class="row">' + Object.keys(health).map(function (key) {
        const value = health[key];
        return '<span class="badge badge-outline">' + ui.esc(key) + ": " + ui.esc(String(value)) + "</span>";
      }).join(" ") + "</div></div>" +
      '<div class="table-wrap"><table><thead><tr><th>Task</th><th>Provider</th><th>Calls</th>' +
      "<th>Units</th><th>Cost (USD)</th></tr></thead><tbody>" +
      (rows.length
        ? rows.map(function (row) {
            return "<tr><td><strong>" + ui.esc(row.task) + "</strong></td><td>" +
              ui.esc(row.provider) + "</td><td>" + ui.esc(row.calls) + "</td><td>" +
              ui.esc(Number(row.units || 0).toFixed(4)) + "</td><td class=\"mono\">$" +
              ui.esc(Number(row.cost_usd || 0).toFixed(6)) + "</td></tr>";
          }).join("")
        : '<tr><td colspan="5"><p class="small muted">No AI usage has been recorded yet. ' +
          "Calls run in offline mock mode until provider keys are configured.</p></td></tr>") +
      "</tbody></table></div>"
    );
  }

  /* ------------------------------------------------------------------- audit log */
  async function auditPanel() {
    let data;
    try {
      data = await api.auditLogs(200);
    } catch (error) {
      return ui.errorPanel(error, "Try again");
    }
    const logs = data.logs || [];
    return (
      '<div class="row-between" style="margin-bottom:0.7rem"><p class="small muted">' + logs.length +
      " most recent entries</p>" +
      '<button class="btn btn-ghost btn-sm" type="button" id="refresh-audit">Refresh</button></div>' +
      '<div class="table-wrap"><table><thead><tr><th>When</th><th>Actor</th><th>Action</th>' +
      "<th>Target</th><th>Details</th></tr></thead><tbody>" +
      (logs.length
        ? logs.map(function (log) {
            const meta = log.meta && Object.keys(log.meta).length
              ? JSON.stringify(log.meta) : "—";
            return "<tr><td class=\"small\">" + ui.esc(ui.fmtDate(log.created_at, true)) + "</td>" +
              '<td class="mono tiny">' + ui.esc(log.actor_id || "system") + "</td>" +
              "<td><strong>" + ui.esc(log.action) + "</strong></td>" +
              '<td class="small">' + ui.esc(log.target || "—") + "</td>" +
              '<td class="tiny mono" style="max-width:320px;overflow-wrap:anywhere">' +
              ui.esc(meta).slice(0, 240) + "</td></tr>";
          }).join("")
        : '<tr><td colspan="5"><p class="small muted">No audit entries yet.</p></td></tr>') +
      "</tbody></table></div>"
    );
  }

  /* ----------------------------------------------------------------------- page */
  pages.admin = {
    app: true,
    title: "Administration",
    render: async function (ctx) {
      if (ctx.user.role !== "admin") {
        return ui.pageHead("Administration", "") +
          ui.alert("This area is restricted to administrators.", "error");
      }
      const tab = ctx.query.get("tab") || "overview";
      let body;
      if (tab === "applications") body = await applicationsPanel();
      else if (tab === "users") body = await usersPanel(ctx.query);
      else if (tab === "config") body = await configPanel();
      else if (tab === "ai") body = await aiPanel();
      else if (tab === "audit") body = await auditPanel();
      else body = await overviewPanel();

      return (
        ui.pageHead("Administration", "Approve students, manage roles, tune policy and watch AI cost.",
          '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How do I approve a student application?">' +
          ui.icon("spark") + " Ask the assistant</button>") +
        tabsBar(tab) +
        '<div id="admin-body">' + body + "</div>"
      );
    },
    after: function (root, ctx) {
      function switchTab(tab) {
        const query = new URLSearchParams();
        query.set("tab", tab);
        const role = ctx.query.get("role");
        const status = ctx.query.get("status");
        if (tab === "users" && role) query.set("role", role);
        if (tab === "users" && status) query.set("status", status);
        DEIY.go("#/app/admin?" + query.toString());
      }

      root.querySelectorAll("[data-admin-tab]").forEach(function (button) {
        button.addEventListener("click", function () {
          switchTab(button.getAttribute("data-admin-tab"));
        });
      });

      const refresh = root.querySelector("#refresh-applications");
      if (refresh) refresh.addEventListener("click", function () { DEIY.rerender(); });
      const refreshAudit = root.querySelector("#refresh-audit");
      if (refreshAudit) refreshAudit.addEventListener("click", function () { DEIY.rerender(); });

      root.querySelectorAll("[data-approve]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-approve");
          const name = button.getAttribute("data-name") || "this applicant";
          const ok = await ui.confirmDialog(
            "Approve " + name + "? An academic ID will be generated and emailed to them.",
            { title: "Approve application", confirmLabel: "Approve" }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            const result = await api.approveUser(id);
            ui.toast("Approved. Academic ID: " + (result.user.academic_id || "issued"), "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not approve the application.", "error");
            button.disabled = false;
          }
        });
      });

      root.querySelectorAll("[data-reject]").forEach(function (button) {
        button.addEventListener("click", function () {
          const id = button.getAttribute("data-reject");
          const name = button.getAttribute("data-name") || "this applicant";
          ui.openModal({
            title: "Reject application",
            subtitle: name,
            body:
              '<form id="reject-form" class="stack">' +
              '<div class="field"><label for="reject-reason">Reason (shown to the applicant)</label>' +
              '<textarea class="textarea" id="reject-reason" name="reason" required minlength="3" ' +
              'maxlength="500" placeholder="Explain what needs to be corrected."></textarea></div>' +
              '<div id="reject-error" hidden></div>' +
              '<button class="btn btn-danger" type="submit">Reject application</button></form>',
            onMount: function (modal, close) {
              modal.querySelector("#reject-form").addEventListener("submit", async function (event) {
                event.preventDefault();
                const form = event.currentTarget;
                const errorBox = modal.querySelector("#reject-error");
                const submit = form.querySelector('button[type="submit"]');
                submit.disabled = true;
                try {
                  await api.rejectUser(id, form.elements.namedItem("reason").value.trim());
                  ui.toast("Application rejected. The applicant has been notified.", "success");
                  close();
                  DEIY.rerender();
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not reject the application.", "error");
                  submit.disabled = false;
                }
              });
            }
          });
        });
      });

      root.querySelectorAll("[data-role-select]").forEach(function (select) {
        select.addEventListener("change", async function () {
          const id = select.getAttribute("data-role-select");
          const role = select.value;
          select.disabled = true;
          try {
            await api.setUserRole(id, role);
            ui.toast("Role updated to " + roleLabel(role) + ".", "success");
          } catch (error) {
            ui.toast(error.message || "Could not update the role.", "error");
            DEIY.rerender();
          } finally {
            select.disabled = false;
          }
        });
      });

      root.querySelectorAll("[data-user-details]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-user-details");
          ui.openModal({
            title: "User details",
            body: '<div id="user-detail-body">' + ui.loading("Loading user…") + "</div>",
            onMount: async function (modal) {
              const body = modal.querySelector("#user-detail-body");
              try {
                const data = await api.adminUser(id);
                const user = data.user;
                const review = user.ai_review || {};
                body.innerHTML =
                  '<div class="row">' + ui.avatar(user, 56) + "<div><h3 style=\"margin:0\">" +
                  ui.esc(user.full_name) + "</h3><p class=\"small muted\">" + ui.esc(user.email) +
                  "</p></div></div>" +
                  '<div class="info-list" style="margin-top:1rem">' +
                  '<div class="info-item"><span>Role</span><strong>' + roleLabel(user.role) + "</strong></div>" +
                  '<div class="info-item"><span>Status</span><strong>' + ui.badge(user.status, ui.statusTone(user.status)) +
                  "</strong></div>" +
                  '<div class="info-item"><span>Academic ID</span><strong class="mono">' +
                  ui.esc(user.academic_id || "Not issued") + "</strong></div>" +
                  '<div class="info-item"><span>Country</span><strong>' + ui.esc(user.country || "—") +
                  "</strong></div>" +
                  '<div class="info-item"><span>Date of birth</span><strong>' +
                  ui.esc(ui.fmtDate(user.date_of_birth)) + "</strong></div>" +
                  '<div class="info-item"><span>Joined</span><strong>' +
                  ui.esc(ui.fmtDate(user.created_at, true)) + "</strong></div></div>" +
                  (review.recommendation
                    ? '<div class="panel-flat stack" style="margin-top:0.8rem;border:1px solid var(--line);padding:0.8rem;border-radius:10px">' +
                      "<strong>AI review</strong>" + reviewBadge(user.ai_review) +
                      '<p class="small muted">' + ui.esc(review.rationale || "") + "</p></div>"
                    : "") +
                  (user.rejection_reason
                    ? ui.alert("Rejection reason: " + user.rejection_reason, "warn") : "");
              } catch (error) {
                body.innerHTML = ui.alert(error.message || "Could not load the user.", "error");
              }
            }
          });
        });
      });

      root.querySelectorAll("[data-user-edit]").forEach(function (button) {
        button.addEventListener("click", function () {
          const id = button.getAttribute("data-user-edit");
          ui.openModal({
            title: "Edit user",
            subtitle: "Changes are validated against the admission rules and written to the audit log.",
            wide: true,
            body: '<div id="user-edit-body">' + ui.loading("Loading user…") + "</div>",
            onMount: async function (modal, close) {
              const body = modal.querySelector("#user-edit-body");
              let user;
              try {
                const data = await api.adminUser(id);
                user = data.user;
              } catch (error) {
                body.innerHTML = ui.alert(error.message || "Could not load the user.", "error");
                return;
              }

              const options = DEIY.state.options || {};
              const programs = programNames(options);
              if (user.program && programs.indexOf(user.program) === -1) programs.push(user.program);
              const programOptions = '<option value="">— Not set —</option>' +
                programs.map(function (name) {
                  return '<option value="' + ui.esc(name) + '"' +
                    (user.program === name ? " selected" : "") + ">" + ui.esc(name) + "</option>";
                }).join("");
              const roles = ["student", "teacher", "proctor", "admin"];
              const roleOptions = roles.map(function (value) {
                return '<option value="' + value + '"' + (user.role === value ? " selected" : "") +
                  ">" + ui.esc(roleLabel(value)) + "</option>";
              }).join("");
              const statuses = ["pending_email", "pending_approval", "active", "rejected", "suspended"];
              if (user.status && statuses.indexOf(user.status) === -1) statuses.push(user.status);
              const statusOptions = statuses.map(function (value) {
                return '<option value="' + value + '"' + (user.status === value ? " selected" : "") +
                  ">" + ui.esc(ui.titleCase(value)) + "</option>";
              }).join("");
              const languages = languageList(options);
              const languageOptions = languages.map(function (item) {
                return '<option value="' + ui.esc(item.code) + '"' +
                  ((user.language || "en") === item.code ? " selected" : "") + ">" +
                  ui.esc(item.name) + "</option>";
              }).join("");

              body.innerHTML =
                '<form id="user-edit-form" class="stack">' +
                '<div class="grid-2">' +
                '<div class="field"><label for="edit-full-name">Full name</label>' +
                '<input class="input" id="edit-full-name" name="full_name" required value="' +
                ui.esc(user.full_name || "") + '" />' +
                '<span class="hint">Four parts: first, second, third and family name.</span></div>' +
                '<div class="field"><label for="edit-email">Email</label>' +
                '<input class="input" id="edit-email" name="email" type="email" required value="' +
                ui.esc(user.email || "") + '" /></div>' +
                '<div class="field"><label for="edit-program">Program</label>' +
                '<select class="select" id="edit-program" name="program">' + programOptions + "</select></div>" +
                '<div class="field"><label for="edit-nationality">Nationality</label>' +
                '<input class="input" id="edit-nationality" name="nationality" value="' +
                ui.esc(user.nationality || "") + '" /></div>' +
                '<div class="field"><label for="edit-phone">Phone number</label>' +
                '<input class="input" id="edit-phone" name="phone_number" type="tel" value="' +
                ui.esc(user.phone_number || "") + '" /></div>' +
                '<div class="field"><label for="edit-father-phone">Father\'s phone number</label>' +
                '<input class="input" id="edit-father-phone" name="father_phone_number" type="tel" value="' +
                ui.esc(user.father_phone_number || "") + '" /></div>' +
                '<div class="field"><label for="edit-role">Role</label>' +
                '<select class="select" id="edit-role" name="role">' + roleOptions + "</select></div>" +
                '<div class="field"><label for="edit-status">Status</label>' +
                '<select class="select" id="edit-status" name="status">' + statusOptions + "</select>" +
                '<span class="hint">Activating an account requires a verified email and issues an academic ID.</span></div>' +
                '<div class="field"><label for="edit-language">Preferred language</label>' +
                '<select class="select" id="edit-language" name="language">' + languageOptions + "</select></div>" +
                '<div class="field"><label>Registration number</label>' +
                '<input class="input" value="' + ui.esc(user.registration_number || "—") + '" disabled />' +
                '<span class="hint">Issued automatically at application time and cannot be edited.</span></div>' +
                "</div>" +
                '<div id="user-edit-error" hidden></div>' +
                '<div class="row"><button class="btn btn-primary" type="submit">Save changes</button>' +
                '<button class="btn btn-ghost" type="button" data-close-edit>Cancel</button></div></form>';

              const form = modal.querySelector("#user-edit-form");
              const errorBox = modal.querySelector("#user-edit-error");
              form.querySelector("[data-close-edit]").addEventListener("click", close);
              form.addEventListener("submit", async function (event) {
                event.preventDefault();
                const submit = form.querySelector('button[type="submit"]');
                const payload = {
                  full_name: form.elements.namedItem("full_name").value.trim(),
                  email: form.elements.namedItem("email").value.trim().toLowerCase(),
                  role: form.elements.namedItem("role").value,
                  status: form.elements.namedItem("status").value,
                  language: form.elements.namedItem("language").value
                };
                const optional = {
                  program: form.elements.namedItem("program").value,
                  nationality: form.elements.namedItem("nationality").value.trim(),
                  phone_number: form.elements.namedItem("phone_number").value.trim(),
                  father_phone_number: form.elements.namedItem("father_phone_number").value.trim()
                };
                Object.keys(optional).forEach(function (key) {
                  if (optional[key]) payload[key] = optional[key];
                });
                submit.disabled = true;
                try {
                  const result = await api.adminUpdateUser(id, payload);
                  ui.toast("Saved changes to " + (result.user.full_name || "the user") + ".", "success");
                  close();
                  DEIY.rerender();
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not update the user.", "error");
                  submit.disabled = false;
                }
              });
            }
          });
        });
      });

      root.querySelectorAll("[data-user-delete]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-user-delete");
          const name = button.getAttribute("data-name") || "this user";
          const ok = await ui.confirmDialog(
            "Delete " + name + "? The account can no longer sign in and the email address is released. " +
              "Exam and audit history are kept.",
            { title: "Delete user", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.adminDeleteUser(id);
            ui.toast("User deleted. The account can no longer sign in.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not delete the user.", "error");
            button.disabled = false;
          }
        });
      });

      const filterButton = root.querySelector("#apply-user-filter");
      if (filterButton) {
        filterButton.addEventListener("click", function () {
          const query = new URLSearchParams({ tab: "users" });
          const role = root.querySelector("#filter-role").value;
          const status = root.querySelector("#filter-status").value;
          if (role) query.set("role", role);
          if (status) query.set("status", status);
          DEIY.go("#/app/admin?" + query.toString());
        });
      }

      const addStaff = root.querySelector("#add-staff");
      if (addStaff) {
        addStaff.addEventListener("click", function () {
          ui.openModal({
            title: "Create staff account",
            subtitle: "The password must include upper case, lower case and a digit.",
            body:
              '<form id="staff-form" class="stack">' +
              '<div class="field"><label>Full name</label>' +
              '<input class="input" name="full_name" required placeholder="Amina Yusuf Hassan Ali" />' +
              '<span class="hint">Use the same four-part format as students.</span></div>' +
              '<div class="field"><label>Email</label>' +
              '<input class="input" type="email" name="email" required placeholder="staff@example.com" /></div>' +
              '<div class="grid-2"><div class="field"><label>Temporary password</label>' +
              '<input class="input" type="text" name="password" required minlength="8" value="ChangeMe1" /></div>' +
              '<div class="field"><label>Role</label><select class="select" name="role">' +
              '<option value="teacher">Teacher</option><option value="proctor">Proctor</option>' +
              '<option value="admin">Administrator</option></select></div></div>' +
              '<div id="staff-error" hidden></div>' +
              '<button class="btn btn-primary" type="submit">Create account</button></form>',
            onMount: function (modal, close) {
              modal.querySelector("#staff-form").addEventListener("submit", async function (event) {
                event.preventDefault();
                const form = event.currentTarget;
                const errorBox = modal.querySelector("#staff-error");
                const submit = form.querySelector('button[type="submit"]');
                submit.disabled = true;
                try {
                  const result = await api.createStaff({
                    full_name: form.elements.namedItem("full_name").value.trim(),
                    email: form.elements.namedItem("email").value.trim().toLowerCase(),
                    password: form.elements.namedItem("password").value,
                    role: form.elements.namedItem("role").value
                  });
                  ui.toast("Staff account created for " + result.user.email + ".", "success");
                  close();
                  DEIY.rerender();
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not create the account.", "error");
                  submit.disabled = false;
                }
              });
            }
          });
        });
      }

      const configForm = root.querySelector("#config-form");
      if (configForm) {
        configForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const values = {};
          root.querySelectorAll("[data-config-input]").forEach(function (input) {
            const key = input.getAttribute("data-config-input");
            const raw = input.value;
            values[key] = input.type === "number" ? Number(raw) : raw;
          });
          root.querySelectorAll("[data-config-boolean]").forEach(function (input) {
            values[input.getAttribute("data-config-boolean")] = input.checked;
          });
          const errorBox = root.querySelector("#config-error");
          const submit = configForm.querySelector('button[type="submit"]');
          submit.disabled = true;
          try {
            const result = await api.updateAdminConfig(values);
            ui.toast("Configuration saved (" + Object.keys(result.updated || {}).length + " values).", "success");
            DEIY.rerender();
          } catch (error) {
            errorBox.hidden = false;
            errorBox.innerHTML = ui.alert(error.message || "Could not save the configuration.", "error");
            submit.disabled = false;
          }
        });
      }
    }
  };
})();
