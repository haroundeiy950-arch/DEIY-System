/* ==========================================================================
   DEIY authoring: create courses, upload library resources, schedule live
   sessions, build proctored exams and create assignments.
   ========================================================================== */
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  const TABS = [
    { id: "course", label: "Course" },
    { id: "resource", label: "Library resource" },
    { id: "live", label: "Live session" },
    { id: "exam", label: "Exam" },
    { id: "assignment", label: "Assignment" }
  ];

  const RESOURCE_KINDS = ["video", "pdf", "epub", "audio", "image"];

  function tabsBar(active) {
    return (
      '<div class="admin-tabs" role="tablist">' +
      TABS.map(function (tab) {
        return '<button class="admin-tab' + (tab.id === active ? " active" : "") +
          '" type="button" role="tab" aria-selected="' + (tab.id === active) +
          '" data-manage-tab="' + tab.id + '">' + ui.esc(tab.label) + "</button>";
      }).join("") +
      "</div>"
    );
  }

  function courseOptions(courses, selected) {
    return ['<option value="">No specific course</option>'].concat(
      (courses || []).map(function (course) {
        return '<option value="' + ui.esc(course.id) + '"' +
          (selected === course.id ? " selected" : "") + ">" +
          ui.esc(course.code + " · " + course.title) + "</option>";
      })
    ).join("");
  }

  function toIso(value) {
    if (!value) return null;
    const date = new Date(value);
    if (isNaN(date.getTime())) return null;
    return date.toISOString();
  }

  /* ------------------------------------------------------------------ course */
  async function coursePanel(courses) {
    return (
      '<div class="grid-2" style="align-items:start">' +
      '<form id="course-form" class="panel stack">' +
      '<div class="panel-head"><h3>Create a course</h3>' + ui.badge("teacher / admin", "teal") + "</div>" +
      "<p class=\"small muted\">Courses group library resources, live sessions, exams and assignments.</p>" +
      '<div class="grid-2"><div class="field"><label for="course-code">Course code</label>' +
      '<input class="input mono" id="course-code" name="code" required placeholder="MTH101" /></div>' +
      '<div class="field"><label for="course-department">Department</label>' +
      '<input class="input" id="course-department" name="department" value="General" /></div></div>' +
      '<div class="field"><label for="course-title">Title</label>' +
      '<input class="input" id="course-title" name="title" required placeholder="Introduction to Algebra" /></div>' +
      '<div class="field"><label for="course-level">Level</label>' +
      '<select class="select" id="course-level" name="level">' +
      '<option>Undergraduate</option><option>Postgraduate</option><option>Foundation</option>' +
      '<option>Secondary</option></select></div>' +
      '<div class="field"><label for="course-description">Description</label>' +
      '<textarea class="textarea" id="course-description" name="description" ' +
      'placeholder="What will students learn?"></textarea></div>' +
      '<div id="course-error" hidden></div>' +
      '<button class="btn btn-primary" type="submit">Create course</button></form>' +
      '<div class="panel stack"><div class="panel-head"><h3>Existing courses</h3>' +
      '<span class="badge badge-outline">' + (courses || []).length + "</span></div>" +
      ((courses || []).length
        ? '<div class="list">' + courses.map(function (course) {
            return '<div class="list-row"><span class="list-icon">' + ui.icon("book") + "</span>" +
              '<div class="list-body"><strong>' + ui.esc(course.code + " · " + course.title) + "</strong><span>" +
              ui.esc(course.department) + " · " + ui.esc(course.level) +
              (course.description ? " · " + ui.esc(course.description).slice(0, 80) : "") +
              "</span></div></div>";
          }).join("") + "</div>"
        : '<p class="small muted">No courses yet. Create the first one.</p>') +
      "</div></div>"
    );
  }

  /* ---------------------------------------------------------------- resource */
  async function resourcePanel(courses) {
    let recent = [];
    try {
      const data = await api.resources({ limit: 8 });
      recent = data.results || [];
    } catch (_) {
      recent = [];
    }
    const kindOptions = RESOURCE_KINDS.map(function (kind) {
      return '<option value="' + kind + '">' + ui.titleCase(kind) + "</option>";
    }).join("");
    return (
      '<div class="grid-2" style="align-items:start">' +
      '<form id="resource-form" class="panel stack">' +
      '<div class="panel-head"><h3>Publish a resource</h3>' + ui.badge("AI enriched", "teal") + "</div>" +
      '<p class="small muted">Upload a file and the AI adds a summary and tags. Videos also get a media ' +
      "variant manifest and a watermarked viewer.</p>" +
      '<div class="field"><label for="res-title">Title</label>' +
      '<input class="input" id="res-title" name="title" required placeholder="Cell structure explained" /></div>' +
      '<div class="grid-2"><div class="field"><label for="res-kind">Type</label>' +
      '<select class="select" id="res-kind" name="kind">' + kindOptions + "</select></div>" +
      '<div class="field"><label for="res-course">Course</label>' +
      '<select class="select" id="res-course" name="course_id">' + courseOptions(courses) + "</select></div></div>" +
      '<div class="field"><label for="res-file">File</label>' +
      '<input class="input" id="res-file" name="file" type="file" />' +
      '<span class="hint">Upload a file, or leave empty and provide a storage key below.</span></div>' +
      '<div class="field"><label for="res-key">Storage key (alternative to upload)</label>' +
      '<input class="input mono" id="res-key" name="storage_key" placeholder="library/video/lesson-1.mp4" /></div>' +
      '<div class="grid-2"><div class="field"><label for="res-author">Author</label>' +
      '<input class="input" id="res-author" name="author" placeholder="Department of Biology" /></div>' +
      '<div class="field"><label for="res-duration">Duration (seconds)</label>' +
      '<input class="input" id="res-duration" name="duration_seconds" type="number" min="0" value="0" /></div></div>' +
      '<div class="field"><label for="res-transcript">Transcript or body text (optional)</label>' +
      '<textarea class="textarea" id="res-transcript" name="transcript" rows="3" ' +
      'placeholder="Paste a transcript so the resource is searchable and summarised accurately."></textarea></div>' +
      '<div id="resource-error" hidden></div>' +
      '<button class="btn btn-primary" type="submit">Publish resource</button></form>' +
      '<div class="panel stack"><div class="panel-head"><h3>Recently published</h3>' +
      '<a class="small strong" href="#/app/library">Open library →</a></div>' +
      (recent.length
        ? '<div class="list">' + recent.map(function (item) {
            return '<div class="list-row"><span class="list-icon">' + ui.icon(
              { video: "video", pdf: "file", epub: "book", audio: "audio", image: "image" }[item.kind] || "file"
            ) + "</span><div class=\"list-body\"><strong>" + ui.esc(item.title) + "</strong><span>" +
              ui.esc(ui.titleCase(item.kind)) + " · " + ui.esc(item.author || "DEIY") +
              (item.ai_summary ? " · " + ui.esc(item.ai_summary).slice(0, 70) : "") +
              "</span></div></div>";
          }).join("") + "</div>"
        : '<p class="small muted">Nothing published yet.</p>') +
      "</div></div>"
    );
  }

  /* -------------------------------------------------------------------- live */
  async function livePanel(courses) {
    let sessions = [];
    try {
      const data = await api.liveSessions({});
      sessions = data.sessions || [];
    } catch (_) {
      sessions = [];
    }
    return (
      '<div class="grid-2" style="align-items:start">' +
      '<form id="live-form" class="panel stack">' +
      '<div class="panel-head"><h3>Schedule a live session</h3>' + ui.badge("auto archive", "teal") + "</div>" +
      "<p class=\"small muted\">When the session ends, the recording is queued for automatic archiving and " +
      "appears in the library for revision.</p>" +
      '<div class="field"><label for="live-title">Title</label>' +
      '<input class="input" id="live-title" name="title" required placeholder="Algebra revision clinic" /></div>' +
      '<div class="grid-2"><div class="field"><label for="live-when">Starts at</label>' +
      '<input class="input" id="live-when" name="scheduled_at" type="datetime-local" required /></div>' +
      '<div class="field"><label for="live-course">Course</label>' +
      '<select class="select" id="live-course" name="course_id">' + courseOptions(courses) + "</select></div></div>" +
      '<div id="live-error" hidden></div>' +
      '<button class="btn btn-primary" type="submit">Schedule session</button></form>' +
      '<div class="panel stack"><div class="panel-head"><h3>Sessions</h3>' +
      '<span class="badge badge-outline">' + sessions.length + "</span></div>" +
      (sessions.length
        ? '<div class="list">' + sessions.map(function (session) {
            const live = session.status === "live" || session.status === "started";
            return '<div class="list-row"><span class="list-icon">' + ui.icon("video") + "</span>" +
              '<div class="list-body"><strong>' + ui.esc(session.title) + "</strong><span>" +
              ui.esc(ui.fmtDate(session.scheduled_at, true)) + " · " +
              ui.esc(ui.titleCase(session.status)) + "</span></div>" +
              '<div class="list-actions">' +
              (session.status === "scheduled"
                ? '<button class="btn btn-xs btn-primary" type="button" data-start-live="' +
                  ui.esc(session.id) + '">Start</button>'
                : "") +
              (live
                ? '<button class="btn btn-xs btn-danger" type="button" data-end-live="' +
                  ui.esc(session.id) + '">End</button>'
                : "") +
              "</div></div>";
          }).join("") + "</div>"
        : '<p class="small muted">No live sessions scheduled.</p>') +
      "</div></div>"
    );
  }

  /* -------------------------------------------------------------------- exam */
  function questionBlock(index) {
    return (
      '<div class="question-card" data-exam-question>' +
      '<div class="row-between"><strong class="small">Question <span data-question-number>' +
      (index + 1) + "</span></strong>" +
      '<button class="btn btn-xs btn-ghost" type="button" data-remove-question>Remove</button></div>' +
      '<div class="field"><label>Prompt</label>' +
      '<textarea class="textarea" name="prompt" rows="2" required placeholder="Write the question…"></textarea></div>' +
      '<div class="grid-3"><div class="field"><label>Type</label>' +
      '<select class="select" name="kind">' +
      '<option value="mcq">Multiple choice</option><option value="short">Short answer</option>' +
      '<option value="essay">Essay</option></select></div>' +
      '<div class="field"><label>Points</label>' +
      '<input class="input" name="points" type="number" min="1" value="1" required /></div>' +
      '<div class="field" data-correct-wrap><label>Correct option</label>' +
      '<select class="select" name="correct_index">' +
      '<option value="0">Option 1</option><option value="1">Option 2</option>' +
      '<option value="2">Option 3</option><option value="3">Option 4</option></select></div></div>' +
      '<div data-mcq-options><div class="grid-2">' +
      [0, 1, 2, 3].map(function (optionIndex) {
        return '<div class="field"><label>Option ' + (optionIndex + 1) + "</label>" +
          '<input class="input" name="option" data-option="' + optionIndex + '" ' +
          (optionIndex < 2 ? 'value="" required' : "") + " /></div>";
      }).join("") + "</div></div>" +
      '<div class="field" data-short-answer hidden><label>Expected answer</label>' +
      '<input class="input" name="expected_answer" placeholder="Used by AI-assisted grading" /></div>' +
      '<div class="field" data-rubric hidden><label>Rubric</label>' +
      '<textarea class="textarea" name="rubric" rows="2" ' +
      'placeholder="What should a strong answer include?"></textarea></div></div>'
    );
  }

  async function examPanel(courses) {
    let exams = [];
    try {
      const data = await api.exams({});
      exams = data.exams || [];
    } catch (_) {
      exams = [];
    }
    return (
      '<form id="exam-form" class="panel stack">' +
      '<div class="panel-head"><h3>Create a proctored exam</h3>' + ui.badge("camera required", "amber") + "</div>" +
      "<p class=\"small muted\">Students must pass a camera check before starting. Answers autosave and the " +
      "attempt submits automatically when time runs out.</p>" +
      '<div class="field"><label for="exam-title">Exam title</label>' +
      '<input class="input" id="exam-title" name="title" required placeholder="Mid-term: Algebra" /></div>' +
      '<div class="grid-3"><div class="field"><label for="exam-course">Course</label>' +
      '<select class="select" id="exam-course" name="course_id">' + courseOptions(courses) + "</select></div>" +
      '<div class="field"><label for="exam-start">Opens</label>' +
      '<input class="input" id="exam-start" name="starts_at" type="datetime-local" required /></div>' +
      '<div class="field"><label for="exam-end">Closes</label>' +
      '<input class="input" id="exam-end" name="ends_at" type="datetime-local" required /></div></div>' +
      '<div class="grid-2"><div class="field"><label for="exam-duration">Duration (minutes)</label>' +
      '<input class="input" id="exam-duration" name="duration_minutes" type="number" min="5" value="60" /></div>' +
      '<div class="field"><label for="exam-instructions">Instructions</label>' +
      '<input class="input" id="exam-instructions" name="instructions" ' +
      'placeholder="Read every question carefully." /></div></div>' +
      '<div class="divider"></div>' +
      '<div class="row-between"><strong>Questions</strong>' +
      '<button class="btn btn-ghost btn-sm" type="button" id="add-question">' + ui.icon("plus") +
      " Add question</button></div>" +
      '<div class="stack" id="question-list"></div>' +
      '<div id="exam-error" hidden></div>' +
      '<div class="row"><button class="btn btn-primary" type="submit">Create exam</button>' +
      '<span class="small muted" id="exam-question-count">0 questions</span></div></form>' +
      '<div class="panel stack" style="margin-top:1rem"><div class="panel-head"><h3>Existing exams</h3>' +
      '<span class="badge badge-outline">' + exams.length + "</span></div>" +
      (exams.length
        ? '<div class="list">' + exams.map(function (exam) {
            return '<div class="list-row"><span class="list-icon">' + ui.icon("exam") + "</span>" +
              '<div class="list-body"><strong>' + ui.esc(exam.title) + "</strong><span>" +
              ui.esc(ui.fmtDate(exam.starts_at, true)) + " → " + ui.esc(ui.fmtDate(exam.ends_at, true)) +
              " · " + ui.esc(exam.status) + "</span></div>" +
              '<a class="btn btn-xs btn-ghost" href="#/app/exams/' + encodeURIComponent(exam.id) +
              '">Open</a></div>';
          }).join("") + "</div>"
        : '<p class="small muted">No exams created yet.</p>') +
      "</div>"
    );
  }

  /* -------------------------------------------------------------- assignment */
  async function assignmentPanel(courses) {
    let assignments = [];
    try {
      const data = await api.assignments({});
      assignments = data.assignments || [];
    } catch (_) {
      assignments = [];
    }
    return (
      '<div class="grid-2" style="align-items:start">' +
      '<form id="manage-assignment-form" class="panel stack">' +
      '<div class="panel-head"><h3>Create an assignment</h3></div>' +
      '<div class="field"><label for="assign-title">Title</label>' +
      '<input class="input" id="assign-title" name="title" required placeholder="Essay: causes of the civil war" /></div>' +
      '<div class="field"><label for="assign-course">Course</label>' +
      '<select class="select" id="assign-course" name="course_id">' + courseOptions(courses) + "</select></div>" +
      '<div class="field"><label for="assign-due">Due</label>' +
      '<input class="input" id="assign-due" name="due_at" type="datetime-local" required /></div>' +
      '<div class="field"><label for="assign-description">Brief</label>' +
      '<textarea class="textarea" id="assign-description" name="description" rows="4" ' +
      'placeholder="What should students submit?"></textarea></div>' +
      '<div id="assign-error" hidden></div>' +
      '<button class="btn btn-primary" type="submit">Create assignment</button></form>' +
      '<div class="panel stack"><div class="panel-head"><h3>Assignments</h3>' +
      '<span class="badge badge-outline">' + assignments.length + "</span></div>" +
      (assignments.length
        ? '<div class="list">' + assignments.map(function (item) {
            return '<div class="list-row"><span class="list-icon">' + ui.icon("file") + "</span>" +
              '<div class="list-body"><strong>' + ui.esc(item.title) + "</strong><span>Due " +
              ui.esc(ui.fmtDate(item.due_at, true)) + "</span></div>" +
              '<a class="btn btn-xs btn-ghost" href="#/app/assignments">Open</a></div>';
          }).join("") + "</div>"
        : '<p class="small muted">No assignments created yet.</p>') +
      "</div></div>"
    );
  }

  /* ----------------------------------------------------------------------- page */
  pages.manage = {
    app: true,
    title: "Author content",
    render: async function (ctx) {
      if (ctx.user.role !== "teacher" && ctx.user.role !== "admin") {
        return ui.pageHead("Author content", "") +
          ui.alert("Only teachers and administrators can publish content.", "error");
      }
      const tab = ctx.query.get("tab") || "course";
      let courses = [];
      try {
        const data = await api.courses();
        courses = data.courses || [];
      } catch (_) {
        courses = [];
      }
      let body;
      if (tab === "resource") body = await resourcePanel(courses);
      else if (tab === "live") body = await livePanel(courses);
      else if (tab === "exam") body = await examPanel(courses);
      else if (tab === "assignment") body = await assignmentPanel(courses);
      else body = await coursePanel(courses);

      return (
        ui.pageHead("Author content", "Publish courses, resources, sessions, exams and assignments.",
          '<a class="btn btn-ghost btn-sm" href="#/app/library">' + ui.icon("library") + " View library</a>") +
        tabsBar(tab) +
        '<div id="manage-body">' + body + "</div>"
      );
    },
    after: function (root, ctx) {
      root.querySelectorAll("[data-manage-tab]").forEach(function (button) {
        button.addEventListener("click", function () {
          DEIY.go("#/app/manage?tab=" + button.getAttribute("data-manage-tab"));
        });
      });

      function showError(selector, message) {
        const box = root.querySelector(selector);
        if (box) {
          box.hidden = false;
          box.innerHTML = ui.alert(message, "error");
        }
        ui.toast(message, "error");
      }

      /* ------------------------------------------------------------- course */
      const courseForm = root.querySelector("#course-form");
      if (courseForm) {
        courseForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const submit = courseForm.querySelector('button[type="submit"]');
          submit.disabled = true;
          try {
            await api.createCourse({
              code: courseForm.elements.namedItem("code").value.trim().toUpperCase(),
              title: courseForm.elements.namedItem("title").value.trim(),
              department: courseForm.elements.namedItem("department").value.trim() || "General",
              level: courseForm.elements.namedItem("level").value,
              description: courseForm.elements.namedItem("description").value || null
            });
            ui.toast("Course created.", "success");
            DEIY.rerender();
          } catch (error) {
            showError("#course-error", error.message || "Could not create the course.");
            submit.disabled = false;
          }
        });
      }

      /* ----------------------------------------------------------- resource */
      const resourceForm = root.querySelector("#resource-form");
      if (resourceForm) {
        resourceForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const submit = resourceForm.querySelector('button[type="submit"]');
          const fileInput = resourceForm.elements.namedItem("file");
          const file = fileInput.files && fileInput.files[0];
          const storageKey = resourceForm.elements.namedItem("storage_key").value.trim();
          if (!file && !storageKey) {
            showError("#resource-error", "Choose a file to upload or provide a storage key.");
            return;
          }
          submit.disabled = true;
          submit.textContent = file ? "Uploading…" : "Publishing…";
          try {
            let result;
            if (file) {
              const form = new FormData();
              form.append("title", resourceForm.elements.namedItem("title").value.trim());
              form.append("kind", resourceForm.elements.namedItem("kind").value);
              form.append("course_id", resourceForm.elements.namedItem("course_id").value || "");
              form.append("author", resourceForm.elements.namedItem("author").value || "");
              form.append("duration_seconds", resourceForm.elements.namedItem("duration_seconds").value || "0");
              form.append("transcript", resourceForm.elements.namedItem("transcript").value || "");
              form.append("file", file);
              result = await api.request("/library/resources/upload", { method: "POST", body: form });
            } else {
              result = await api.createResource({
                title: resourceForm.elements.namedItem("title").value.trim(),
                kind: resourceForm.elements.namedItem("kind").value,
                course_id: resourceForm.elements.namedItem("course_id").value || null,
                author: resourceForm.elements.namedItem("author").value || null,
                storage_key: storageKey,
                duration_seconds: Number(resourceForm.elements.namedItem("duration_seconds").value || 0),
                transcript: resourceForm.elements.namedItem("transcript").value || null
              });
            }
            ui.toast("Resource published: " + result.resource.title, "success");
            DEIY.rerender();
          } catch (error) {
            showError("#resource-error", error.message || "Could not publish the resource.");
            submit.disabled = false;
            submit.textContent = "Publish resource";
          }
        });
      }

      /* --------------------------------------------------------------- live */
      const liveForm = root.querySelector("#live-form");
      if (liveForm) {
        liveForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const when = toIso(liveForm.elements.namedItem("scheduled_at").value);
          if (!when) {
            showError("#live-error", "Choose a valid start date and time.");
            return;
          }
          const submit = liveForm.querySelector('button[type="submit"]');
          submit.disabled = true;
          try {
            await api.scheduleLiveSession({
              title: liveForm.elements.namedItem("title").value.trim(),
              scheduled_at: when,
              course_id: liveForm.elements.namedItem("course_id").value || null
            });
            ui.toast("Live session scheduled.", "success");
            DEIY.rerender();
          } catch (error) {
            showError("#live-error", error.message || "Could not schedule the session.");
            submit.disabled = false;
          }
        });
      }

      root.querySelectorAll("[data-start-live]").forEach(function (button) {
        button.addEventListener("click", async function () {
          button.disabled = true;
          try {
            await api.startLiveSession(button.getAttribute("data-start-live"));
            ui.toast("Live session started.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not start the session.", "error");
            button.disabled = false;
          }
        });
      });

      root.querySelectorAll("[data-end-live]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const ok = await ui.confirmDialog(
            "End this live session? The recording will be queued for archiving.",
            { title: "End live session", confirmLabel: "End session", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.endLiveSession(button.getAttribute("data-end-live"));
            ui.toast("Session ended and recording queued.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not end the session.", "error");
            button.disabled = false;
          }
        });
      });

      /* --------------------------------------------------------------- exam */
      const examForm = root.querySelector("#exam-form");
      if (examForm) {
        const list = root.querySelector("#question-list");
        const counter = root.querySelector("#exam-question-count");

        function renumber() {
          const cards = Array.from(list.querySelectorAll("[data-exam-question]"));
          cards.forEach(function (card, index) {
            const label = card.querySelector("[data-question-number]");
            if (label) label.textContent = String(index + 1);
          });
          if (counter) counter.textContent = cards.length + " question" + (cards.length === 1 ? "" : "s");
        }

        function addQuestion() {
          const index = list.querySelectorAll("[data-exam-question]").length;
          const holder = document.createElement("div");
          holder.innerHTML = questionBlock(index);
          const card = holder.firstElementChild;
          list.appendChild(card);
          renumber();
          card.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        const addButton = root.querySelector("#add-question");
        if (addButton) addButton.addEventListener("click", addQuestion);
        addQuestion();

        list.addEventListener("click", function (event) {
          if (!event.target.closest("[data-remove-question]")) return;
          const card = event.target.closest("[data-exam-question]");
          if (card) {
            card.remove();
            if (!list.querySelector("[data-exam-question]")) addQuestion();
            renumber();
          }
        });

        list.addEventListener("change", function (event) {
          const select = event.target.closest('select[name="kind"]');
          if (!select) return;
          const card = select.closest("[data-exam-question]");
          const kind = select.value;
          const mcq = card.querySelector("[data-mcq-options]");
          const correct = card.querySelector("[data-correct-wrap]");
          const short = card.querySelector("[data-short-answer]");
          const rubric = card.querySelector("[data-rubric]");
          mcq.hidden = kind !== "mcq";
          correct.hidden = kind !== "mcq";
          short.hidden = kind !== "short";
          rubric.hidden = kind !== "essay";
        });

        examForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const startsAt = toIso(examForm.elements.namedItem("starts_at").value);
          const endsAt = toIso(examForm.elements.namedItem("ends_at").value);
          if (!startsAt || !endsAt) {
            showError("#exam-error", "Choose when the exam opens and closes.");
            return;
          }
          if (new Date(endsAt).getTime() <= new Date(startsAt).getTime()) {
            showError("#exam-error", "The closing time must be after the opening time.");
            return;
          }
          const questions = [];
          Array.from(list.querySelectorAll("[data-exam-question]")).forEach(function (card) {
            const kind = card.querySelector('select[name="kind"]').value;
            const prompt = (card.querySelector('textarea[name="prompt"]').value || "").trim();
            if (!prompt) return;
            const question = {
              prompt: prompt,
              kind: kind,
              points: Math.max(1, Number(card.querySelector('input[name="points"]').value || 1))
            };
            if (kind === "mcq") {
              const options = [];
              card.querySelectorAll("[data-mcq-options] input[data-option]").forEach(function (input) {
                if (input.value.trim()) options.push(input.value.trim());
              });
              if (options.length < 2) {
                question.invalid = true;
                return;
              }
              question.options = options;
              question.correct_index = Number(card.querySelector('select[name="correct_index"]').value || 0);
            } else if (kind === "short") {
              question.expected_answer = card.querySelector('input[name="expected_answer"]').value || null;
            } else {
              question.rubric = card.querySelector('textarea[name="rubric"]').value || null;
            }
            questions.push(question);
          });
          const invalid = questions.find(function (question) { return question.invalid; });
          if (invalid) {
            showError("#exam-error", "Every multiple-choice question needs at least two options.");
            return;
          }
          if (!questions.length) {
            showError("#exam-error", "Add at least one question with a prompt.");
            return;
          }
          questions.forEach(function (question) { delete question.invalid; });

          const submit = examForm.querySelector('button[type="submit"]');
          submit.disabled = true;
          submit.textContent = "Creating…";
          try {
            await api.request("/exams", {
              method: "POST",
              body: {
                title: examForm.elements.namedItem("title").value.trim(),
                starts_at: startsAt,
                ends_at: endsAt,
                duration_minutes: Number(examForm.elements.namedItem("duration_minutes").value || 60),
                course_id: examForm.elements.namedItem("course_id").value || null,
                instructions: examForm.elements.namedItem("instructions").value || null,
                questions: questions
              }
            });
            ui.toast("Exam created.", "success");
            DEIY.rerender();
          } catch (error) {
            showError("#exam-error", error.message || "Could not create the exam.");
            submit.disabled = false;
            submit.textContent = "Create exam";
          }
        });
      }

      /* --------------------------------------------------------- assignment */
      const assignmentForm = root.querySelector("#manage-assignment-form");
      if (assignmentForm) {
        assignmentForm.addEventListener("submit", async function (event) {
          event.preventDefault();
          const due = toIso(assignmentForm.elements.namedItem("due_at").value);
          if (!due) {
            showError("#assign-error", "Choose a valid due date and time.");
            return;
          }
          const submit = assignmentForm.querySelector('button[type="submit"]');
          submit.disabled = true;
          try {
            await api.createAssignment({
              title: assignmentForm.elements.namedItem("title").value.trim(),
              course_id: assignmentForm.elements.namedItem("course_id").value || null,
              due_at: due,
              description: assignmentForm.elements.namedItem("description").value || null
            });
            ui.toast("Assignment created.", "success");
            DEIY.rerender();
          } catch (error) {
            showError("#assign-error", error.message || "Could not create the assignment.");
            submit.disabled = false;
          }
        });
      }
    }
  };
})();
