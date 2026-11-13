(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  function examWindow(exam) {
    const now = Date.now();
    const start = ui.parseDate(exam.starts_at);
    const end = ui.parseDate(exam.ends_at);
    if (!start || !end) return { open: false, label: "Dates not set" };
    if (now < start.getTime()) return { open: false, label: "Opens " + ui.fmtRelative(exam.starts_at) };
    if (now > end.getTime()) return { open: false, label: "Closed" };
    return { open: true, label: "Open now · closes " + ui.fmtRelative(exam.ends_at) };
  }

  function examCard(exam, canManage) {
    const state = examWindow(exam);
    return (
      '<article class="resource-card"><div class="resource-cover" data-kind="pdf" style="height:88px">' +
      '<span class="kind-label">' + ui.esc(exam.status) + "</span>" + ui.icon("exam") + "</div>" +
      '<div class="resource-body"><div class="row" style="gap:0.4rem">' +
      (state.open ? ui.badge("open now", "success") : ui.badge(exam.status, ui.statusTone(exam.status))) +
      (exam.duration_minutes ? '<span class="resource-meta">' + exam.duration_minutes + " min</span>" : "") +
      "</div><h3>" + ui.esc(exam.title) + "</h3>" +
      '<span class="resource-meta">' + ui.esc(ui.fmtDate(exam.starts_at, true)) + " → " +
      ui.esc(ui.fmtDate(exam.ends_at, true)) + "</span>" +
      '<p class="small muted">' + ui.esc(state.label) + "</p>" +
      '<div class="row" style="gap:0.4rem"><a class="btn btn-sm btn-primary" href="#/app/exams/' +
      encodeURIComponent(exam.id) + '">' +
      (state.open ? ui.icon("play") + " Open exam" : ui.icon("info") + " View details") + "</a>" +
      (canManage
        ? '<button class="btn btn-sm btn-danger" type="button" data-delete-exam="' + ui.esc(exam.id) +
          '" data-name="' + ui.esc(exam.title) + '">Delete</button>'
        : "") +
      "</div></div></article>"
    );
  }


  pages.exams = {
    app: true,
    title: "Exams",
    render: async function (ctx) {
      let data;
      try {
        data = await api.exams();
      } catch (error) {
        return ui.pageHead("Exams", "Proctored assessments.") + ui.errorPanel(error, "Try again");
      }
      const exams = data.exams || [];
      const isStaff = ctx.user.role !== "student";
      return (
        ui.pageHead("Exams", isStaff
          ? "Authoring, attempts and integrity reports."
          : "Camera-verified assessments. Answers save automatically as you work.",
          isStaff ? '<a class="btn btn-primary btn-sm" href="#/app/manage?tab=exam">' + ui.icon("plus") +
            " Create exam</a>" : "") +
        ui.alert(
          isStaff
            ? "Students must pass a camera check before starting. Attempts auto-submit when the deadline is reached."
            : "Before you start: allow camera access, close other apps that use the webcam and keep this tab open. " +
              "Your answers are saved every few seconds.",
          "info"
        ) +
        '<div class="row" style="margin:1rem 0"><span class="badge badge-teal">' +
        ui.icon("shield") + " Proctored</span><span class=\"badge badge-outline\">Autosave on</span>" +
        '<span class="badge badge-outline">Auto-submit on expiry</span></div>' +
        (exams.length
          ? '<div class="resource-grid">' + exams.map(function (exam) {
              return examCard(exam, isStaff);
            }).join("") + "</div>"
          : ui.emptyState({
              icon: "exam",
              title: "No exams yet",
              text: isStaff ? "Create an exam to schedule your first assessment." : "Your teachers have not scheduled an exam yet.",
              action: isStaff ? '<a class="btn btn-primary" href="#/app/manage?tab=exam">Create an exam</a>' : ""
            })) +
        (isStaff ? "" :
          '<div class="panel stack" style="margin-top:1.4rem"><div class="row">' + ui.icon("camera") +
          '<div class="grow"><strong>Camera not working?</strong><p class="small muted">' +
          "Allow the browser permission, close other video apps, then reload. The AI guide has a checklist.</p></div>" +
          '<button class="btn btn-ghost btn-sm" type="button" data-assistant="My camera is not working">' +
          "Camera help</button></div></div>")
      );
    },
    after: function (root, ctx) {
      if (ctx.user.role === "student") return;
      root.querySelectorAll("[data-delete-exam]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-delete-exam");
          const name = button.getAttribute("data-name") || "this exam";
          const ok = await ui.confirmDialog(
            "Delete " + name + "? Questions, attempts, answers and proctor events will also be removed.",
            { title: "Delete exam", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.deleteExam(id);
            ui.toast("Exam deleted.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not delete the exam.", "error");
            button.disabled = false;
          }
        });
      });
    }
  };


  pages.exam = {
    app: true,
    title: "Exam",
    render: async function (ctx) {
      const id = ctx.params.id;
      let data;
      try {
        data = await api.exam(id);
      } catch (error) {
        return ui.pageHead("Exam", "") + ui.errorPanel(error, "Back to exams") +
          '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost" href="#/app/exams">← Exams</a></div>';
      }
      const exam = data.exam;
      const questions = data.questions || [];
      const isStudent = ctx.user.role === "student";
      const state = examWindow(exam);
      const totalPoints = questions.reduce(function (sum, question) { return sum + (question.points || 1); }, 0);

      let attemptsPanel = "";
      if (!isStudent) {
        try {
          const attempts = await api.examAttempts(id);
          const rows = attempts.attempts || [];
          attemptsPanel =
            '<div class="panel" style="margin-top:1rem"><div class="panel-head"><h3>Student attempts</h3>' +
            '<span class="badge badge-outline">' + rows.length + "</span></div>" +
            (rows.length
              ? '<div class="table-wrap"><table><thead><tr><th>Student</th><th>Status</th><th>Score</th>' +
                "<th>Started</th><th></th></tr></thead><tbody>" +
                rows.map(function (attempt) {
                  return "<tr><td class=\"mono small\">" + ui.esc(attempt.student_id) + "</td><td>" +
                    ui.badge(attempt.status, ui.statusTone(attempt.status)) + "</td><td>" +
                    (attempt.score === null || attempt.score === undefined ? "—" : ui.esc(attempt.score)) +
                    "</td><td>" + ui.esc(ui.fmtDate(attempt.started_at, true)) + "</td><td>" +
                    '<a class="btn btn-xs btn-ghost" href="#/app/exams/attempt/' +
                    encodeURIComponent(attempt.id) + '">Report</a></td></tr>';
                }).join("") + "</tbody></table></div>"
              : '<p class="small muted">No student has started this exam.</p>') + "</div>";
        } catch (_) {
          attemptsPanel = "";
        }
      }

      const startPanel = isStudent
        ? '<div class="exam-banner"><span class="eyebrow">Before you begin</span><h2>' + ui.esc(exam.title) + "</h2>" +
          "<p>" + ui.esc(exam.instructions || "Read each question carefully. Your answers save automatically.") + "</p>" +
          '<div class="row"><span class="badge badge-teal">' + exam.duration_minutes + " minutes</span>" +
          '<span class="badge badge-outline">' + questions.length + " questions</span>" +
          '<span class="badge badge-outline">' + totalPoints + " points</span>" +
          '<span class="badge ' + (state.open ? "badge-success" : "badge-amber") + '">' + ui.esc(state.label) +
          "</span></div>" +
          '<div class="grid-2" style="margin-top:1rem;align-items:center">' +
          '<div class="camera-preview" id="camera-preview"><video id="camera-video" autoplay muted playsinline></video>' +
          '<span class="badge badge-outline camera-badge" id="camera-badge">Camera not checked</span></div>' +
          '<div class="stack-sm"><p class="small" style="color:rgba(249, 186, 38, 0.7)">' +
          "We check your camera before the timer starts. If you cannot see a preview, check browser permissions " +
          "and close other apps using the camera.</p>" +
          '<button class="btn btn-amber" type="button" id="check-camera"' + (state.open ? "" : " disabled") + ">" +
          ui.icon("camera") + " Check camera</button>" +
          '<button class="btn btn-light" type="button" id="start-exam" disabled>' +
          ui.icon("play") + " Start / resume exam</button>" +
          '<button class="btn btn-ghost btn-sm" type="button" data-assistant="My camera is not working" ' +
          'style="color:#fff;border-color:rgba(101, 252, 7, 0.25)">Camera help</button></div></div></div>'
        : "";

      return (
        ui.pageHead(exam.title, ui.titleCase(exam.status) + " · " + ui.fmtDate(exam.starts_at, true) +
          " → " + ui.fmtDate(exam.ends_at, true),
          '<div class="row">' +
          (!isStudent
            ? '<button class="btn btn-danger btn-sm" type="button" data-delete-exam="' +
              ui.esc(exam.id) + '" data-name="' + ui.esc(exam.title) + '">Delete exam</button>'
            : "") +
          '<a class="btn btn-ghost btn-sm" href="#/app/exams">← Exams</a></div>') +
        startPanel +
        '<div class="grid-2" style="align-items:start;margin-top:1rem">' +
        '<div class="panel"><div class="panel-head"><h3>Exam details</h3>' +
        ui.badge(state.open ? "open now" : exam.status, state.open ? "success" : ui.statusTone(exam.status)) +
        "</div><div class=\"info-list\">" +
        '<div class="info-item"><span>Duration</span><strong>' + ui.esc(exam.duration_minutes) + " minutes</strong></div>" +
        '<div class="info-item"><span>Questions</span><strong>' + questions.length + "</strong></div>" +
        '<div class="info-item"><span>Total points</span><strong>' + totalPoints + "</strong></div>" +
        '<div class="info-item"><span>Opens</span><strong>' + ui.esc(ui.fmtDate(exam.starts_at, true)) + "</strong></div>" +
        '<div class="info-item"><span>Closes</span><strong>' + ui.esc(ui.fmtDate(exam.ends_at, true)) + "</strong></div>" +
        "</div></div>" +
        '<div class="panel"><div class="panel-head"><h3>Question overview</h3></div>' +
        (questions.length
          ? '<div class="list">' + questions.slice(0, 8).map(function (question, index) {
              return '<div class="list-row"><span class="list-icon">' + (index + 1) + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(question.kind.toUpperCase()) + " · " +
                question.points + " point" + (question.points === 1 ? "" : "s") + "</strong><span>" +
                ui.esc(String(question.prompt || "").slice(0, 90)) + "</span></div></div>";
            }).join("") + (questions.length > 8 ? '<p class="small muted">…and ' + (questions.length - 8) +
              " more.</p>" : "") + "</div>"
          : '<p class="small muted">No questions have been added yet.</p>') + "</div></div>" +
        attemptsPanel +
        (isStudent && !state.open
          ? ui.alert("This exam is not open yet, or its window has closed. You can still review the details.", "warn")
          : "")
      );
    },
    after: async function (root, ctx) {
      if (ctx.user.role !== "student") return;
      const video = root.querySelector("#camera-video");
      const badge = root.querySelector("#camera-badge");
      const check = root.querySelector("#check-camera");
      const start = root.querySelector("#start-exam");
      if (!video || !check) return;
      let verified = false;

      function stopStream() {
        if (DEIY.state.cameraStream) {
          DEIY.state.cameraStream.getTracks().forEach(function (track) { track.stop(); });
          DEIY.state.cameraStream = null;
        }
      }

      check.addEventListener("click", async function () {
        check.disabled = true;
        check.textContent = "Checking…";
        let deviceId = "browser-camera";
        let streamOk = false;
        try {
          if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            stopStream();
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            DEIY.state.cameraStream = stream;
            video.srcObject = stream;
            await video.play().catch(function () {});
            const track = stream.getVideoTracks()[0];
            const settings = track && track.getSettings ? track.getSettings() : {};
            deviceId = settings.deviceId || "browser-camera";
            streamOk = true;
          }
        } catch (_) {
          streamOk = false;
        }
        if (!streamOk) {
          badge.textContent = "No camera preview — fallback check";
          badge.className = "badge badge-amber camera-badge";
          const useFallback = await ui.confirmDialog(
            "We could not access a camera preview. You can continue with a device-level check so you can still " +
            "sit this exam, but you must be on a device with a working camera. Continue?",
            { title: "Camera unavailable", confirmLabel: "Continue without preview" }
          );
          if (!useFallback) {
            check.disabled = false;
            check.innerHTML = ui.icon("camera") + " Check camera";
            return;
          }
          deviceId = "device-camera-fallback";
          streamOk = true;
        }
        try {
          await api.cameraCheck(ctx.params.id, { device_id: deviceId, stream_ok: streamOk });
          verified = true;
          badge.textContent = "Camera verified";
          badge.className = "badge badge-success camera-badge";
          start.disabled = false;
          ui.toast("Camera verified. You can start the exam.", "success");
        } catch (error) {
          badge.textContent = "Check failed";
          badge.className = "badge badge-danger camera-badge";
          ui.toast(error.message || "Camera verification failed.", "error");
        } finally {
          check.disabled = false;
          check.innerHTML = ui.icon("camera") + " Check again";
        }
      });

      start.addEventListener("click", async function () {
        if (!verified) {
          ui.toast("Run the camera check first.", "error");
          return;
        }
        start.disabled = true;
        start.textContent = "Starting…";
        try {
          const payload = await api.startAttempt(ctx.params.id, {
            camera_verified: true,
            camera_device: "browser-camera"
          });
          stopStream();
          DEIY.go("#/app/exams/attempt/" + encodeURIComponent(payload.attempt.id));
        } catch (error) {
          if (error.code === "attempt_finished") {
            ui.toast("You have already completed this exam.", "info");
            DEIY.go("#/app/gradebook");
            return;
          }
          if (error.code === "exam_expired" && error.details && error.details.attempt_id) {
            DEIY.go("#/app/exams/attempt/" + encodeURIComponent(error.details.attempt_id));
            return;
          }
          ui.toast(error.message || "Could not start the exam.", "error");
          start.disabled = false;
          start.innerHTML = ui.icon("play") + " Start / resume exam";
        }
      });
    },
    after: function (root, ctx) {
      const button = root.querySelector("[data-delete-exam]");
      if (!button || ctx.user.role === "student") return;
      button.addEventListener("click", async function () {
        const name = button.getAttribute("data-name") || "this exam";
        const ok = await ui.confirmDialog(
          "Delete " + name + "? Questions, attempts, answers and proctor events will also be removed.",
          { title: "Delete exam", confirmLabel: "Delete", danger: true }
        );
        if (!ok) return;
        button.disabled = true;
        try {
          await api.deleteExam(button.getAttribute("data-delete-exam"));
          ui.toast("Exam deleted.", "success");
          DEIY.go("#/app/exams");
        } catch (error) {
          ui.toast(error.message || "Could not delete the exam.", "error");
          button.disabled = false;
        }
      });
    },
    destroy: function () {
      if (DEIY.state.cameraStream) {
        DEIY.state.cameraStream.getTracks().forEach(function (track) { track.stop(); });
        DEIY.state.cameraStream = null;
      }
    }
  };

 
  pages.attempt = {
    app: true,
    title: "Exam attempt",
    render: async function (ctx) {
      let data;
      try {
        data = await api.attempt(ctx.params.id);
      } catch (error) {
        return ui.pageHead("Exam attempt", "") + ui.errorPanel(error, "Back to exams") +
          '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost" href="#/app/exams">← Exams</a></div>';
      }
      const attempt = data.attempt;
      const questions = data.questions || [];
      const totalPoints = questions.reduce(function (sum, question) { return sum + (question.points || 1); }, 0);

      if (attempt.status !== "in_progress") {
        const percent = totalPoints ? Math.round((Number(attempt.score || 0) / totalPoints) * 100) : 0;
        const integrity = attempt.integrity || {};
        return (
          ui.pageHead("Exam result", "This attempt is final.",
            '<a class="btn btn-ghost btn-sm" href="#/app/exams">← Exams</a>') +
          '<div class="grid-2" style="align-items:start">' +
          '<div class="panel attempt-summary"><div class="row">' +
          '<div class="score-ring" style="--score:' + percent + '"><span>' + percent + "%</span></div>" +
          '<div><h3>' + ui.badge(attempt.status, ui.statusTone(attempt.status)) + "</h3>" +
          '<p class="small muted">Score ' + ui.esc(Number(attempt.score || 0).toFixed(2)) + " of " +
          totalPoints + " points</p><p class=\"small muted\">Submitted " +
          ui.esc(ui.fmtDate(attempt.submitted_at, true)) + "</p></div></div>" +
          '<div class="info-list"><div class="info-item"><span>Started</span><strong>' +
          ui.esc(ui.fmtDate(attempt.started_at, true)) + "</strong></div>" +
          '<div class="info-item"><span>Deadline</span><strong>' +
          ui.esc(ui.fmtDate(attempt.deadline_at, true)) + "</strong></div>" +
          '<div class="info-item"><span>Camera</span><strong>' +
          (attempt.camera && attempt.camera.verified ? "Verified" : "Not verified") + "</strong></div></div>" +
          "</div>" +
          '<div class="stack"><div class="panel stack"><h3>Integrity report</h3>' +
          (integrity.recommendation
            ? '<div class="row">' + ui.badge(integrity.recommendation, integrity.recommendation === "clear" ? "success" : "amber") +
              '<span class="small muted">risk score ' + ui.esc(Number(integrity.risk_score || 0).toFixed(2)) + "</span></div>" +
              (integrity.rationale ? '<p class="small muted">' + ui.esc(integrity.rationale) + "</p>" : "") +
              ((integrity.flags || []).length ? '<div class="resource-tags">' + integrity.flags.map(function (flag) {
                return '<span class="tag">' + ui.esc(flag) + "</span>";
              }).join("") + "</div>" : "")
            : '<p class="small muted">No integrity signals were recorded for this attempt.</p>') +
          "</div>" +
          '<div class="panel stack"><h3>Your answers</h3>' +
          (data.saved_answers || []).map(function (saved) {
            const question = questions.find(function (q) { return q.id === saved.question_id; });
            return '<div class="info-item"><span>' + ui.esc(question ? String(question.prompt).slice(0, 60) : "Question") +
              "</span><strong>" + ui.esc(typeof saved.answer === "object" ? JSON.stringify(saved.answer) :
                String(saved.answer === null || saved.answer === undefined ? "—" : saved.answer)) + "</strong></div>";
          }).join("") + "</div></div></div>"
        );
      }

      return (
        ui.pageHead("Exam in progress", "Answers save automatically. Do not close this tab.",
          '<span class="timer" id="exam-timer">' + ui.fmtClock(attempt.remaining_seconds) + "</span>") +
        '<div class="exam-banner" style="padding:1rem 1.2rem"><div class="row-between">' +
        '<div><strong id="save-state">All changes saved</strong><p class="small" style="color:rgba(255,255,255,0.6)">' +
        "Autosave runs every few seconds · camera remains verified</p></div>" +
        '<button class="btn btn-amber btn-sm" type="button" id="submit-exam">Submit exam</button></div>' +
        '<div class="exam-progress" style="margin-top:0.5rem;color:rgba(255,255,255,0.7)">' +
        '<span id="answered-count">0</span>/<span>' + questions.length + "</span> answered" +
        '<div class="progress" style="background:rgba(255,255,255,0.15)"><span id="exam-progress-bar" ' +
        'style="width:0%;background:var(--teal-bright)"></span></div></div></div>' +
        '<div class="stack" id="questions" style="margin-top:1rem">' +
        questions.map(function (question, index) {
          const saved = (data.saved_answers || []).find(function (item) { return item.question_id === question.id; });
          const value = saved ? saved.answer : null;
          let input = "";
          if (question.kind === "mcq") {
            const selected = typeof value === "number" ? value : value && typeof value === "object" ? value.index : null;
            input = (question.options || []).map(function (option, optionIndex) {
              return '<label class="option' + (selected === optionIndex ? " selected" : "") + '" data-option="' +
                optionIndex + '"><input type="radio" name="q_' + ui.esc(question.id) + '" value="' + optionIndex + '"' +
                (selected === optionIndex ? " checked" : "") + " /><span>" + ui.esc(option) + "</span></label>";
            }).join("");
          } else {
            input = '<textarea class="textarea" data-question-input="' + ui.esc(question.id) + '" ' +
              'placeholder="Type your answer here…">' + ui.esc(typeof value === "string" ? value : "") + "</textarea>";
          }
          return '<article class="question-card" data-question="' + ui.esc(question.id) + '" data-kind="' +
            ui.esc(question.kind) + '"><div class="question-meta"><span class="badge badge-outline">Question ' +
            (index + 1) + "</span><span class=\"badge badge-teal\">" + question.points + " point" +
            (question.points === 1 ? "" : "s") + "</span><span class=\"badge badge-outline\">" +
            ui.esc(question.kind.toUpperCase()) + "</span></div><h3>" + ui.esc(question.prompt) + "</h3>" +
            '<div class="stack-sm">' + input + "</div></article>";
        }).join("") + "</div>" +
        '<div class="row" style="justify-content:space-between;margin-top:1rem">' +
        '<button class="btn btn-ghost" type="button" id="save-now">Save now</button>' +
        '<button class="btn btn-amber" type="button" id="submit-exam-2">Submit exam</button></div>'
      );
    },
    after: function (root, ctx) {
      const timer = root.querySelector("#exam-timer");
      const saveState = root.querySelector("#save-state");
      const answeredCount = root.querySelector("#answered-count");
      const progressBar = root.querySelector("#exam-progress-bar");
      const submitButtons = [root.querySelector("#submit-exam"), root.querySelector("#submit-exam-2")];
      const questions = Array.from(root.querySelectorAll("[data-question]"));
      const answers = {};
      let seq = 0;
      let dirty = false;
      let saving = false;
      let finished = false;
      let remaining = Number(root.querySelector("#exam-timer").textContent.split(":").reduce(function (acc, part) {
        return acc * 60 + Number(part || 0);
      }, 0)) || 0;
      let tickHandle = null;

      function collect() {
        const payload = [];
        questions.forEach(function (card) {
          const id = card.getAttribute("data-question");
          const kind = card.getAttribute("data-kind");
          let value = null;
          if (kind === "mcq") {
            const checked = card.querySelector('input[type="radio"]:checked');
            value = checked ? Number(checked.value) : null;
          } else {
            const area = card.querySelector("textarea");
            value = area ? area.value : "";
          }
          if (value !== null && value !== "") {
            answers[id] = value;
            payload.push({ question_id: id, answer: value });
          } else {
            delete answers[id];
          }
        });
        return payload;
      }

      function updateProgress() {
        const payload = collect();
        answeredCount.textContent = String(payload.length);
        progressBar.style.width = questions.length ? (payload.length / questions.length) * 100 + "%" : "0%";
      }

      async function save(silent) {
        if (saving || finished) return;
        const payload = collect();
        saving = true;
        if (saveState) saveState.textContent = "Saving…";
        try {
          seq += 1;
          const result = await api.autosaveAttempt(ctx.params.id, payload, seq);
          dirty = false;
          if (saveState) saveState.textContent = "All changes saved · " + ui.fmtTime(result.server_time);
          if (typeof result.remaining_seconds === "number") remaining = result.remaining_seconds;
        } catch (error) {
          if (error.code === "exam_expired" || error.code === "attempt_not_active") {
            finished = true;
            ui.toast("Time is up. Your answers were submitted automatically.", "info");
            DEIY.go("#/app/exams/attempt/" + encodeURIComponent(ctx.params.id));
            return;
          }
          if (saveState) saveState.textContent = "Autosave failed — retrying";
          dirty = true;
          if (!silent) ui.toast(error.message || "Could not save answers.", "error");
        } finally {
          saving = false;
        }
      }

      function reportEvent(kind, severity, payload) {
        if (finished) return;
        api.proctorEvents(ctx.params.id, [{
          kind: kind,
          severity: severity || "low",
          payload: payload || {}
        }]).catch(function () {});
      }

      function tick() {
        remaining -= 1;
        if (remaining < 0) remaining = 0;
        if (timer) {
          timer.textContent = ui.fmtClock(remaining);
          timer.classList.toggle("danger", remaining <= 60);
        }
        const minutes = Math.floor(remaining / 60);
        if (remaining === 300) reportEvent("time_warning", "low", { minutes_left: 5 });
        else if (remaining === 60) reportEvent("time_warning", "medium", { minutes_left: 1 });
        if (remaining === 0) {
          finished = true;
          clearInterval(tickHandle);
          ui.toast("Time is up. Submitting your answers…", "info");
          api.submitAttempt(ctx.params.id)
            .catch(function () {})
            .finally(function () { DEIY.go("#/app/exams/attempt/" + encodeURIComponent(ctx.params.id)); });
        }
        if (remaining % 15 === 0 && dirty) save(true);
      }

      root.querySelectorAll('input[type="radio"]').forEach(function (input) {
        input.addEventListener("change", function () {
          const card = input.closest("[data-question]");
          card.querySelectorAll(".option").forEach(function (option) { option.classList.remove("selected"); });
          input.closest(".option").classList.add("selected");
          dirty = true;
          updateProgress();
        });
      });
      root.querySelectorAll("textarea[data-question-input]").forEach(function (area) {
        area.addEventListener("input", function () {
          dirty = true;
          updateProgress();
        });
      });

      function onVisibility() {
        reportEvent("visibility_change", document.hidden ? "medium" : "low", {
          hidden: document.hidden
        });
      }
      function onBlur() {
        reportEvent("window_blur", "low", {});
      }
      function onCopy(event) {
        reportEvent("copy_attempt", "medium", { length: String(window.getSelection() || "").length });
      }
      function onPaste(event) {
        reportEvent("paste_attempt", "medium", { length: (event.clipboardData && event.clipboardData.getData("text") || "").length });
      }
      document.addEventListener("visibilitychange", onVisibility);
      window.addEventListener("blur", onBlur);
      document.addEventListener("copy", onCopy);
      document.addEventListener("paste", onPaste);

      async function submit() {
        const confirmed = await ui.confirmDialog(
          "Submit now? You cannot change your answers after submitting.",
          { title: "Submit exam", confirmLabel: "Submit exam" }
        );
        if (!confirmed) return;
        finished = true;
        submitButtons.forEach(function (button) { if (button) button.disabled = true; });
        clearInterval(tickHandle);
        try {
          await save(true);
          await api.submitAttempt(ctx.params.id);
          ui.toast("Exam submitted. Your result is ready.", "success");
        } catch (error) {
          ui.toast(error.message || "Submission failed — retrying once.", "error");
          try {
            await api.submitAttempt(ctx.params.id);
          } catch (_) {
            /* result page will show the state */
          }
        }
        DEIY.go("#/app/exams/attempt/" + encodeURIComponent(ctx.params.id));
      }

      submitButtons.forEach(function (button) {
        if (button) button.addEventListener("click", submit);
      });
      const saveNow = root.querySelector("#save-now");
      if (saveNow) saveNow.addEventListener("click", function () { save(false); });

      updateProgress();
      tickHandle = setInterval(tick, 1000);
      const autosave = setInterval(function () { if (dirty) save(true); }, 6000);

      DEIY.attemptCleanup = function () {
        clearInterval(tickHandle);
        clearInterval(autosave);
        document.removeEventListener("visibilitychange", onVisibility);
        window.removeEventListener("blur", onBlur);
        document.removeEventListener("copy", onCopy);
        document.removeEventListener("paste", onPaste);
      };
    },
    destroy: function () {
      if (DEIY.attemptCleanup) {
        DEIY.attemptCleanup();
        DEIY.attemptCleanup = null;
      }
    }
  };
})();
