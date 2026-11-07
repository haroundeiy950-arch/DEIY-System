/* ==========================================================================
   DEIY utilities: gradebook, assignments, helpdesk and support tickets.
   ========================================================================== */
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  /* ----------------------------------------------------------------- gradebook */
  pages.gradebook = {
    app: true,
    title: "Gradebook",
    render: async function (ctx) {
      const isStudent = ctx.user.role === "student";
      let studentId = isStudent ? null : ctx.query.get("student_id");
      let students = [];
      if (ctx.user.role === "admin") {
        try {
          const data = await api.adminUsers({ role: "student" });
          students = data.users || [];
        } catch (_) { students = []; }
      }
      if (!isStudent && !studentId) {
        return (
          ui.pageHead("Gradebook", "Academic insights, exam scores and attendance.") +
          '<div class="panel stack" style="max-width:620px"><h3>Choose a student</h3>' +
          '<p class="small muted">Enter the student ID or academic ID to open their gradebook.</p>' +
          '<form id="gradebook-picker" class="stack">' +
          '<div class="field"><label for="student-id">Student ID</label>' +
          '<input class="input mono" id="student-id" name="student_id" list="student-list" ' +
          'placeholder="Paste the student ID" required />' +
          (students.length ? '<datalist id="student-list">' + students.map(function (student) {
            return '<option value="' + ui.esc(student.id) + '">' + ui.esc(student.full_name) + " · " +
              ui.esc(student.academic_id || "") + "</option>";
          }).join("") + "</datalist>" : "") +
          '<span class="hint">Students can copy their ID from the profile page.</span></div>' +
          '<button class="btn btn-primary" type="submit">Open gradebook</button></form></div>'
        );
      }

      let data;
      try {
        data = await api.gradebook(studentId, true);
      } catch (error) {
        return ui.pageHead("Gradebook", "") + ui.errorPanel(error, "Back") +
          '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost" href="#/app/gradebook">← Gradebook</a></div>';
      }
      const insights = data.ai_insights || {};
      const exams = data.exams || [];
      const assignments = data.assignments || [];
      return (
        ui.pageHead("Gradebook", isStudent
          ? "Your exam scores, assignments, attendance and AI insights."
          : "Student performance and AI insights.",
          isStudent ? "" : '<a class="btn btn-ghost btn-sm" href="#/app/gradebook">← Another student</a>') +
        '<div class="grid-4" style="margin-bottom:1rem">' +
        '<div class="stat-card accent"><span class="stat-label">Average score</span><span class="stat-value">' +
        ui.esc(Number(data.average_score || 0).toFixed(1)) + '%</span><span class="stat-note">Graded exams</span></div>' +
        '<div class="stat-card"><span class="stat-label">Attendance</span><span class="stat-value">' +
        ui.esc(Number(data.attendance_rate || 0).toFixed(1)) + '%</span><span class="stat-note">' +
        ((data.attendance && data.attendance.present) || 0) + " of " +
        ((data.attendance && data.attendance.records) || 0) + " sessions</span></div>" +
        '<div class="stat-card"><span class="stat-label">Exams</span><span class="stat-value">' +
        exams.length + '</span><span class="stat-note">Attempts recorded</span></div>' +
        '<div class="stat-card"><span class="stat-label">Assignments</span><span class="stat-value">' +
        assignments.length + '</span><span class="stat-note">Graded submissions</span></div></div>' +
        '<div class="grid-2" style="align-items:start">' +
        '<div class="stack">' +
        '<div class="panel"><div class="panel-head"><h3>Exam history</h3>' +
        ui.badge(exams.length + " attempts", "outline") + "</div>" +
        (exams.length
          ? '<div class="table-wrap"><table><thead><tr><th>Exam</th><th>Status</th><th>Score</th>' +
            "<th>Submitted</th></tr></thead><tbody>" + exams.map(function (exam) {
              return "<tr><td>" + ui.esc(exam.title) + "</td><td>" +
                ui.badge(exam.status, ui.statusTone(exam.status)) + "</td><td>" +
                (exam.score === null || exam.score === undefined ? "—" : ui.esc(Number(exam.score).toFixed(2))) +
                "</td><td>" + ui.esc(ui.fmtDate(exam.submitted_at, true)) + "</td></tr>";
            }).join("") + "</tbody></table></div>"
          : '<p class="small muted">No exam attempts yet.</p>') + "</div>" +
        '<div class="panel"><div class="panel-head"><h3>Assignments</h3></div>' +
        (assignments.length
          ? '<div class="list">' + assignments.map(function (item) {
              return '<div class="list-row"><span class="list-icon">' + ui.icon("file") + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(item.title) + "</strong><span>" +
                (item.grade === null || item.grade === undefined ? "Not graded yet" :
                  "Grade " + ui.esc(item.grade) + "/100") +
                (item.feedback ? " · " + ui.esc(item.feedback) : "") + "</span></div></div>";
            }).join("") + "</div>"
          : '<p class="small muted">No graded assignments yet.</p>') + "</div></div>" +
        '<div class="stack">' +
        '<div class="panel stack"><div class="panel-head"><h3>AI academic insight</h3>' +
        '<span class="badge badge-teal">' + ui.icon("spark") + " " + ui.esc(insights.provider || "AI") +
        "</span></div>" +
        (insights.summary
          ? '<p class="small">' + ui.esc(insights.summary) + "</p>" +
            ((insights.strengths || []).length ? "<h4 style=\"font-size:0.85rem\">Strengths</h4><ul class=\"small\">" +
              insights.strengths.map(function (item) { return "<li>" + ui.esc(item) + "</li>"; }).join("") +
              "</ul>" : "") +
            ((insights.risks || []).length ? "<h4 style=\"font-size:0.85rem\">Watch out for</h4><ul class=\"small\">" +
              insights.risks.map(function (item) { return "<li>" + ui.esc(item) + "</li>"; }).join("") +
              "</ul>" : "") +
            ((insights.next_steps || []).length ? "<h4 style=\"font-size:0.85rem\">Next steps</h4><ul class=\"small\">" +
              insights.next_steps.map(function (item) { return "<li>" + ui.esc(item) + "</li>"; }).join("") +
              "</ul>" : "")
          : '<p class="small muted">Insights appear once there is some graded work.</p>') +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How can I improve my grades?">' +
        ui.icon("spark") + " Ask for study advice</button></div>" +
        '<div class="panel stack"><h3>Attendance details</h3>' +
        '<div class="info-list"><div class="info-item"><span>Recorded sessions</span><strong>' +
        ((data.attendance && data.attendance.records) || 0) + "</strong></div>" +
        '<div class="info-item"><span>Present</span><strong>' +
        ((data.attendance && data.attendance.present) || 0) + "</strong></div>" +
        '<div class="info-item"><span>Rate</span><strong>' +
        ui.esc(Number(data.attendance_rate || 0).toFixed(1)) + "%</strong></div></div></div></div></div>"
      );
    },
    after: function (root) {
      const picker = root.querySelector("#gradebook-picker");
      if (picker) {
        picker.addEventListener("submit", function (event) {
          event.preventDefault();
          const id = picker.elements.namedItem("student_id").value.trim();
          if (id) DEIY.go("#/app/gradebook?student_id=" + encodeURIComponent(id));
        });
      }
    }
  };

  /* ---------------------------------------------------------------- assignments */
  pages.assignments = {
    app: true,
    title: "Assignments",
    render: async function (ctx) {
      let data;
      try {
        data = await api.assignments({});
      } catch (error) {
        return ui.pageHead("Assignments", "") + ui.errorPanel(error, "Try again");
      }
      const list = data.assignments || [];
      const isStudent = ctx.user.role === "student";
      const isStaff = ctx.user.role === "teacher" || ctx.user.role === "admin";
      return (
        ui.pageHead("Assignments", "Submit your work and receive grades with feedback.",
          isStaff ? '<button class="btn btn-primary btn-sm" type="button" id="new-assignment">' +
            ui.icon("plus") + " New assignment</button>" : "") +
        (list.length
          ? '<div class="stack">' + list.map(function (item) {
              const due = ui.parseDate(item.due_at);
              const overdue = due && due.getTime() < Date.now();
              return '<div class="panel"><div class="row-between"><div><h3>' + ui.esc(item.title) + "</h3>" +
                '<p class="small muted">Due ' + ui.esc(ui.fmtDate(item.due_at, true)) + " · " +
                ui.esc(ui.fmtRelative(item.due_at)) + "</p></div>" +
                '<div class="row">' + ui.badge(overdue ? "overdue" : "due", overdue ? "danger" : "teal") +
                (isStudent
                  ? '<button class="btn btn-sm btn-primary" type="button" data-submit="' + ui.esc(item.id) +
                    '" data-title="' + ui.esc(item.title) + '">Submit work</button>'
                  : '<button class="btn btn-sm btn-ghost" type="button" data-submissions="' + ui.esc(item.id) +
                    '" data-title="' + ui.esc(item.title) + '">Submissions</button>') +
                "</div></div>" +
                (item.description ? '<p class="small" style="margin-top:0.5rem">' + ui.esc(item.description) +
                  "</p>" : "") + "</div>";
            }).join("") + "</div>"
          : ui.emptyState({
              icon: "file",
              title: "No assignments yet",
              text: isStaff ? "Create an assignment for your students." : "When a teacher publishes an assignment it will appear here.",
              action: isStaff ? '<button class="btn btn-primary" type="button" data-new-assignment>Create assignment</button>' : ""
            })) +
        '<div class="panel stack" style="margin-top:1.2rem"><div class="row">' + ui.icon("spark") +
        '<div class="grow"><strong>Need help interpreting the brief?</strong>' +
        '<p class="small muted">Ask the AI guide for a structure, then write the work yourself.</p></div>' +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How should I structure my assignment?">' +
        "Ask the guide</button></div></div>"
      );
    },
    after: function (root, ctx) {
      const isStaff = ctx.user.role === "teacher" || ctx.user.role === "admin";

      function openSubmit(id, title) {
        ui.openModal({
          title: "Submit: " + title,
          subtitle: "Your submission is recorded against your account.",
          body:
            '<form id="submit-form" class="stack"><div class="field"><label for="submission-content">' +
            'Your answer</label><textarea class="textarea" id="submission-content" name="content" required ' +
            'placeholder="Type or paste your work…"></textarea></div>' +
            '<div id="submit-error" hidden></div>' +
            '<button class="btn btn-primary" type="submit">Submit assignment</button></form>',
          onMount: function (modal, close) {
            modal.querySelector("#submit-form").addEventListener("submit", async function (event) {
              event.preventDefault();
              const form = event.currentTarget;
              const errorBox = modal.querySelector("#submit-error");
              const button = form.querySelector('button[type="submit"]');
              button.disabled = true;
              try {
                await api.submitAssignment(id, form.elements.namedItem("content").value);
                ui.toast("Assignment submitted successfully.", "success");
                close();
              } catch (error) {
                errorBox.hidden = false;
                errorBox.innerHTML = ui.alert(error.message || "Could not submit the assignment.", "error");
                button.disabled = false;
              }
            });
          }
        });
      }

      function openSubmissions(id, title) {
        ui.openModal({
          title: "Submissions: " + title,
          wide: true,
          body: '<div id="submissions-body">' + ui.loading("Loading submissions…") + "</div>",
          onMount: async function (modal) {
            const body = modal.querySelector("#submissions-body");
            try {
              const data = await api.assignmentSubmissions(id);
              const rows = data.submissions || [];
              body.innerHTML = rows.length
                ? '<div class="stack">' + rows.map(function (row) {
                    return '<div class="panel stack" data-submission="' + ui.esc(row.id) + '">' +
                      '<div class="row-between"><strong class="mono small">' + ui.esc(row.student_id) +
                      "</strong>" + (row.grade === null || row.grade === undefined
                        ? ui.badge("ungraded", "amber") : ui.badge("grade " + row.grade, "success")) + "</div>" +
                      '<p class="small" style="white-space:pre-wrap">' + ui.esc(row.content) + "</p>" +
                      '<form class="grid-2" data-grade-form data-student="' + ui.esc(row.student_id) + '">' +
                      '<div class="field"><label>Grade (0-100)</label>' +
                      '<input class="input" name="grade" type="number" min="0" max="100" required value="' +
                      (row.grade === null || row.grade === undefined ? "" : ui.esc(row.grade)) + '" /></div>' +
                      '<div class="field"><label>Feedback</label>' +
                      '<input class="input" name="feedback" value="' + ui.esc(row.feedback || "") +
                      '" placeholder="Optional feedback" /></div>' +
                      '<div class="span-2"><button class="btn btn-sm btn-primary" type="submit">Save grade</button></div>' +
                      "</form></div>";
                  }).join("") + "</div>"
                : ui.emptyState({ icon: "file", title: "No submissions", text: "Students have not submitted this assignment yet." });

              body.querySelectorAll("[data-grade-form]").forEach(function (form) {
                form.addEventListener("submit", async function (event) {
                  event.preventDefault();
                  const button = form.querySelector('button[type="submit"]');
                  button.disabled = true;
                  try {
                    await api.gradeSubmission(id, {
                      student_id: form.getAttribute("data-student"),
                      grade: Number(form.elements.namedItem("grade").value),
                      feedback: form.elements.namedItem("feedback").value || null
                    });
                    ui.toast("Grade saved.", "success");
                    button.textContent = "Saved";
                  } catch (error) {
                    ui.toast(error.message || "Could not save the grade.", "error");
                    button.disabled = false;
                  }
                });
              });
            } catch (error) {
              body.innerHTML = ui.alert(error.message || "Could not load submissions.", "error");
            }
          }
        });
      }

      root.querySelectorAll("[data-submit]").forEach(function (button) {
        button.addEventListener("click", function () {
          openSubmit(button.getAttribute("data-submit"), button.getAttribute("data-title"));
        });
      });
      root.querySelectorAll("[data-submissions]").forEach(function (button) {
        button.addEventListener("click", function () {
          openSubmissions(button.getAttribute("data-submissions"), button.getAttribute("data-title"));
        });
      });

      const newAssignment = root.querySelector("#new-assignment");
      if (newAssignment) {
        newAssignment.addEventListener("click", function () {
          ui.openModal({
            title: "Create an assignment",
            body:
              '<form id="assignment-form" class="stack"><div class="field"><label>Title</label>' +
              '<input class="input" name="title" required placeholder="Essay: causes of the civil war" /></div>' +
              '<div class="field"><label>Description</label>' +
              '<textarea class="textarea" name="description" placeholder="What should students do?"></textarea></div>' +
              '<div class="field"><label>Due date and time</label>' +
              '<input class="input" name="due_at" type="datetime-local" required /></div>' +
              '<div id="assignment-error" hidden></div>' +
              '<button class="btn btn-primary" type="submit">Create assignment</button></form>',
            onMount: function (modal, close) {
              modal.querySelector("#assignment-form").addEventListener("submit", async function (event) {
                event.preventDefault();
                const form = event.currentTarget;
                const errorBox = modal.querySelector("#assignment-error");
                const button = form.querySelector('button[type="submit"]');
                const due = form.elements.namedItem("due_at").value;
                button.disabled = true;
                try {
                  await api.createAssignment({
                    title: form.elements.namedItem("title").value.trim(),
                    description: form.elements.namedItem("description").value || null,
                    due_at: new Date(due).toISOString()
                  });
                  ui.toast("Assignment created.", "success");
                  close();
                  DEIY.rerender();
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not create the assignment.", "error");
                  button.disabled = false;
                }
              });
            }
          });
        });
      }
      root.querySelectorAll("[data-new-assignment]").forEach(function (button) {
        button.addEventListener("click", function () { if (newAssignment) newAssignment.click(); });
      });
    }
  };

  /* ------------------------------------------------------------------- helpdesk */
  pages.help = {
    app: true,
    title: "Helpdesk",
    render: async function (ctx) {
      const guide = DEIY.state.guide || {};
      const prompts = (guide.assistant_prompts || [
        "How do I apply step by step?",
        "My camera is not working",
        "I cannot see my exam",
        "How do room summaries work?"
      ]).slice(0, 5);
      let tickets = [];
      try {
        const data = await api.tickets({});
        tickets = data.tickets || [];
      } catch (_) {
        tickets = [];
      }
      return (
        ui.pageHead("Helpdesk", "The AI assistant can answer most questions. Escalate to a human when needed.",
          '<button class="btn btn-ghost btn-sm" type="button" id="new-ticket">' + ui.icon("plus") +
          " New ticket</button>") +
        '<div class="grid-2" style="grid-template-columns:minmax(0,1.25fr) minmax(300px,0.75fr);align-items:start">' +
        '<div class="panel chat-panel"><div class="panel-head"><h3>AI assistant</h3>' +
        '<span class="badge badge-teal">' + ui.icon("spark") + " Online</span></div>" +
        '<div class="chat-log" id="help-log" role="log" aria-live="polite">' +
        '<div class="chat-msg bot">Hi ' + ui.esc((ctx.user.full_name || "").split(" ")[0] || "there") +
        "! Ask me about exams, the library, study rooms, cameras, grades or your account. " +
        "If I cannot solve it, I will open a support ticket for you.</div></div>" +
        '<div class="chat-suggestions" id="help-prompts">' + prompts.map(function (prompt) {
          return '<button class="chip" type="button" data-prompt="' + ui.esc(prompt) + '">' +
            ui.esc(prompt) + "</button>";
        }).join("") + "</div>" +
        '<form class="chat-compose" id="help-form">' +
        '<textarea class="textarea" name="question" rows="1" placeholder="Describe what you need help with…" ' +
        'aria-label="Your question"></textarea>' +
        '<button class="btn btn-primary" type="submit" aria-label="Send">' + ui.icon("arrow") + "</button></form>" +
        '<p class="tiny muted">AI answers can be imperfect. Never share your password or academic ID.</p></div>' +
        '<div class="panel"><div class="panel-head"><h3>Your tickets</h3>' +
        '<span class="badge badge-outline">' + tickets.length + "</span></div>" +
        (tickets.length
          ? '<div class="list">' + tickets.map(function (ticket) {
              return '<div class="list-row"><span class="list-icon">' + ui.icon("ticket") + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(ticket.subject) + "</strong><span>" +
                ui.badge(ticket.status, ticket.status === "resolved" ? "success" : "amber") + " · " +
                ui.esc(ui.fmtDate(ticket.created_at, true)) + "</span></div>" +
                '<button class="btn btn-xs btn-ghost" type="button" data-ticket="' + ui.esc(ticket.id) +
                '">Open</button></div>';
            }).join("") + "</div>"
          : '<p class="small muted">No tickets yet. If the AI cannot solve a problem it can open one for you.</p>') +
        "</div></div>"
      );
    },
    after: function (root, ctx) {
      const log = root.querySelector("#help-log");
      const form = root.querySelector("#help-form");
      const promptsBox = root.querySelector("#help-prompts");
      const textarea = form.elements.namedItem("question");

      function add(kind, text, extra) {
        const node = document.createElement("div");
        node.className = "chat-msg " + kind;
        node.textContent = text;
        if (extra) {
          const meta = document.createElement("span");
          meta.className = "tiny muted";
          meta.style.display = "block";
          meta.style.marginTop = "0.35rem";
          meta.textContent = extra;
          node.appendChild(meta);
        }
        log.appendChild(node);
        log.scrollTop = log.scrollHeight;
        return node;
      }

      async function ask(question) {
        const trimmed = (question || "").trim();
        if (!trimmed) return;
        add("user", trimmed);
        const typing = document.createElement("div");
        typing.className = "chat-msg bot";
        typing.textContent = "Thinking…";
        log.appendChild(typing);
        log.scrollTop = log.scrollHeight;
        try {
          const data = await api.helpdesk(trimmed);
          typing.remove();
          const meta = [data.provider ? "AI · " + data.provider : null,
            typeof data.confidence === "number" ? Math.round(data.confidence * 100) + "% confidence" : null]
            .filter(Boolean).join(" · ");
          add("bot", data.answer || "I do not have an answer for that yet.", meta);
          if (data.escalated) {
            const node = add("system",
              data.ticket_id
                ? "I opened support ticket " + data.ticket_id + " so a human can follow up."
                : "This needs a human. Open a support ticket and include what you tried.");
            if (data.ticket_id) {
              const button = document.createElement("button");
              button.className = "btn btn-xs btn-primary";
              button.type = "button";
              button.textContent = "Open ticket";
              button.style.marginTop = "0.4rem";
              button.addEventListener("click", function () { openTicket(data.ticket_id); });
              node.appendChild(document.createElement("br"));
              node.appendChild(button);
            }
          }
          refreshTickets();
        } catch (error) {
          typing.remove();
          add("system", error.message || "The assistant is unavailable right now. Try opening a ticket.");
        }
      }

      async function refreshTickets() {
        try {
          const data = await api.tickets({});
          const tickets = data.tickets || [];
          const panel = root.querySelector(".panel .list") || null;
          const container = root.querySelectorAll(".panel")[1];
          if (!container) return;
          const head = container.querySelector(".panel-head .badge");
          if (head) head.textContent = String(tickets.length);
          const list = container.querySelector(".list");
          const html = tickets.map(function (ticket) {
            return '<div class="list-row"><span class="list-icon">' + ui.icon("ticket") + "</span>" +
              '<div class="list-body"><strong>' + ui.esc(ticket.subject) + "</strong><span>" +
              ui.badge(ticket.status, ticket.status === "resolved" ? "success" : "amber") + " · " +
              ui.esc(ui.fmtDate(ticket.created_at, true)) + "</span></div>" +
              '<button class="btn btn-xs btn-ghost" type="button" data-ticket="' + ui.esc(ticket.id) +
              '">Open</button></div>';
          }).join("");
          if (list) {
            list.innerHTML = html;
            bindTicketButtons();
          }
        } catch (_) { /* ignore */ }
      }

      function openTicket(id) {
        ui.openModal({
          title: "Support ticket",
          wide: true,
          body: '<div id="ticket-body">' + ui.loading("Loading ticket…") + "</div>",
          onMount: async function (modal) {
            const body = modal.querySelector("#ticket-body");
            try {
              const ticket = await api.ticket(id);
              body.innerHTML =
                '<div class="row-between"><div><h3>' + ui.esc(ticket.subject) + "</h3>" +
                '<p class="small muted">Opened ' + ui.esc(ui.fmtDate(ticket.created_at, true)) + "</p></div>" +
                ui.badge(ticket.status, ticket.status === "resolved" ? "success" : "amber") + "</div>" +
                '<div class="chat-log" style="margin-top:1rem;max-height:360px">' +
                (ticket.messages || []).map(function (message) {
                  return '<div class="chat-msg ' + (message.role === "user" ? "user" : "bot") + '">' +
                    ui.esc(message.body) + '<span class="tiny muted" style="display:block;margin-top:0.3rem">' +
                    ui.esc(message.role) + " · " + ui.esc(ui.fmtDate(message.created_at, true)) + "</span></div>";
                }).join("") + "</div>" +
                '<form id="ticket-reply" class="chat-compose" style="margin-top:0.8rem">' +
                '<textarea class="textarea" name="body" rows="2" placeholder="Add a reply…" required></textarea>' +
                '<button class="btn btn-primary" type="submit">Send</button></form>';
              modal.querySelector("#ticket-reply").addEventListener("submit", async function (event) {
                event.preventDefault();
                const form = event.currentTarget;
                const button = form.querySelector('button[type="submit"]');
                button.disabled = true;
                const reply = form.elements.namedItem("body").value.trim();
                if (!reply) { button.disabled = false; return; }
                try {
                  await api.replyTicket(id, reply);
                  ui.toast("Reply sent.", "success");
                  const data = await api.ticket(id);
                  const log = body.querySelector(".chat-log");
                  if (log) {
                    log.innerHTML = (data.messages || []).map(function (message) {
                      return '<div class="chat-msg ' + (message.role === "user" ? "user" : "bot") + '">' +
                        ui.esc(message.body) + '<span class="tiny muted" style="display:block;margin-top:0.3rem">' +
                        ui.esc(message.role) + " · " + ui.esc(ui.fmtDate(message.created_at, true)) +
                        "</span></div>";
                    }).join("");
                    log.scrollTop = log.scrollHeight;
                  }
                  form.reset();
                  button.disabled = false;
                } catch (error) {
                  ui.toast(error.message || "Could not send the reply.", "error");
                  button.disabled = false;
                }
              });
            } catch (error) {
              body.innerHTML = ui.alert(error.message || "Could not load the ticket.", "error");
            }
          }
        });
      }

      function bindTicketButtons() {
        root.querySelectorAll("[data-ticket]").forEach(function (button) {
          button.onclick = function () { openTicket(button.getAttribute("data-ticket")); };
        });
      }

      form.addEventListener("submit", function (event) {
        event.preventDefault();
        const value = textarea.value;
        textarea.value = "";
        ask(value);
      });
      textarea.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          form.requestSubmit();
        }
      });
      root.querySelectorAll("[data-prompt]").forEach(function (button) {
        button.addEventListener("click", function () {
          ask(button.getAttribute("data-prompt"));
        });
      });
      bindTicketButtons();

      const newTicket = root.querySelector("#new-ticket");
      if (newTicket) {
        newTicket.addEventListener("click", function () {
          ui.openModal({
            title: "Open a support ticket",
            body:
              '<form id="ticket-form" class="stack"><div class="field"><label>Subject</label>' +
              '<input class="input" name="subject" required placeholder="Short summary" /></div>' +
              '<div class="field"><label>What happened?</label>' +
              '<textarea class="textarea" name="body" required placeholder="Include what you tried and any error message."></textarea></div>' +
              '<div id="ticket-error" hidden></div>' +
              '<button class="btn btn-primary" type="submit">Open ticket</button></form>',
            onMount: function (modal, close) {
              modal.querySelector("#ticket-form").addEventListener("submit", async function (event) {
                event.preventDefault();
                const form = event.currentTarget;
                const errorBox = modal.querySelector("#ticket-error");
                const button = form.querySelector('button[type="submit"]');
                button.disabled = true;
                try {
                  const data = await api.createTicket(
                    form.elements.namedItem("subject").value.trim(),
                    form.elements.namedItem("body").value.trim()
                  );
                  ui.toast("Support ticket opened.", "success");
                  close();
                  openTicket(data.ticket.id);
                  refreshTickets();
                } catch (error) {
                  errorBox.hidden = false;
                  errorBox.innerHTML = ui.alert(error.message || "Could not open the ticket.", "error");
                  button.disabled = false;
                }
              });
            }
          });
        });
      }
    }
  };
})();
