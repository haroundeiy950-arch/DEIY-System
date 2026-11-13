
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  function seats(room) {
    const count = room.participant_count || 0;
    let html = "";
    for (let i = 0; i < room.capacity; i += 1) {
      html += '<span class="seat' + (i < count ? " filled" : "") + '"></span>';
    }
    return html;
  }

  function roomCard(room, canManage) {
    return (
      '<article class="room-card"><div class="row-between">' +
      ui.badge(room.status, ui.statusTone(room.status)) +
      '<span class="small muted">' + (room.participant_count || 0) + "/" + room.capacity + "</span></div>" +
      "<h3>" + ui.esc(room.title) + "</h3>" +
      '<p class="small muted">' + (room.status === "open"
        ? "Closes " + ui.esc(ui.fmtRelative(room.ends_at))
        : "Created " + ui.esc(ui.fmtRelative(room.created_at))) + "</p>" +
      '<div class="room-capacity" aria-hidden="true">' + seats(room) + "</div>" +
      '<div class="row" style="gap:0.4rem"><a class="btn btn-sm btn-primary" href="#/app/rooms/' +
      encodeURIComponent(room.id) + '">' +
      (room.status === "open" ? ui.icon("arrow") + " Join room" : ui.icon("info") + " View room") +
      "</a>" +
      (canManage
        ? '<button class="btn btn-sm btn-danger" type="button" data-delete-room="' + ui.esc(room.id) +
          '" data-name="' + ui.esc(room.title) + '">Delete</button>'
        : "") +
      "</div></article>"
    );
  }

  pages.rooms = {
    app: true,
    title: "Study rooms",
    render: async function (ctx) {
      let data;
      let courses = null;
      try {
        const results = await Promise.all([api.rooms(), api.courses().catch(() => null)]);
        data = results[0];
        courses = results[1];
      } catch (error) {
        return ui.pageHead("Study rooms", "") + ui.errorPanel(error, "Try again");
      }
      const rooms = data.rooms || [];
      const open = rooms.filter(function (room) { return room.status === "open"; });
      const courseList = (courses && courses.courses) || [];
      return (
        ui.pageHead("Micro study rooms", "Small groups, cameras on, and an AI summary after every session.",
          '<button class="btn btn-primary btn-sm" type="button" id="new-room">' + ui.icon("plus") +
          " Create room</button>") +
        ui.alert("Rooms hold 10–15 students, require an academic ID and a working camera, and close automatically " +
          "at the time limit. The AI summary is delivered shortly after the room ends.", "info") +
        '<div class="grid-4" style="margin:1rem 0">' +
        '<div class="stat-card accent"><span class="stat-label">Open now</span><span class="stat-value">' +
        open.length + '</span><span class="stat-note">Ready to join</span></div>' +
        '<div class="stat-card"><span class="stat-label">Total rooms</span><span class="stat-value">' +
        rooms.length + '</span><span class="stat-note">All sessions</span></div>' +
        '<div class="stat-card"><span class="stat-label">Capacity</span><span class="stat-value">10–15</span>' +
        '<span class="stat-note">Per room</span></div>' +
        '<div class="stat-card"><span class="stat-label">Summary SLA</span><span class="stat-value">5–10m</span>' +
        '<span class="stat-note">AI delivery window</span></div></div>' +
        (rooms.length
          ? '<div class="room-grid">' + rooms.map(function (room) {
              return roomCard(room, ctx.user.role === "admin" || room.host_id === ctx.user.id);
            }).join("") + "</div>"
          : ui.emptyState({
              icon: "room",
              title: "No study rooms yet",
              text: "Create the first room, or wait for a classmate to open one.",
              action: '<button class="btn btn-primary" type="button" data-create-room>Create a room</button>'
            })) +
        '<div class="panel stack" style="margin-top:1.4rem"><div class="row">' + ui.icon("spark") +
        '<div class="grow"><strong>How room summaries work</strong><p class="small muted">' +
        "When the host ends the session, the recording is transcribed by Whisper and summarised by Gemini. " +
        "The summary includes key points, decisions and action items.</p></div>" +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How do study rooms work?">' +
        "Ask about rooms</button></div></div>" +
        '<div id="room-courses" hidden data-courses="' + ui.esc(JSON.stringify(courseList)) + '"></div>'
      );
    },
    after: function (root, ctx) {
      const coursesHost = root.querySelector("#room-courses");
      let courses = [];
      try { courses = JSON.parse(coursesHost.getAttribute("data-courses") || "[]"); } catch (_) { courses = []; }
      const openCreate = function () {
        const options = ['<option value="">No specific course</option>'].concat(
          courses.map(function (course) {
            return '<option value="' + ui.esc(course.id) + '">' + ui.esc(course.code + " · " + course.title) + "</option>";
          })
        ).join("");
        ui.openModal({
          title: "Create a study room",
          subtitle: "Capacity must be between 10 and 15 students.",
          body:
            '<form id="create-room-form" class="stack">' +
            '<div class="field"><label for="room-title">Room title</label>' +
            '<input class="input" id="room-title" name="title" required placeholder="Algebra revision group" /></div>' +
            '<div class="grid-2"><div class="field"><label for="room-capacity">Capacity</label>' +
            '<input class="input" id="room-capacity" name="capacity" type="number" min="10" max="15" value="12" required />' +
            '<span class="hint">10 to 15 students</span></div>' +
            '<div class="field"><label for="room-course">Course (optional)</label>' +
            '<select class="select" id="room-course" name="course_id">' + options + "</select></div></div>" +
            '<div id="create-room-error" hidden></div>' +
            '<button class="btn btn-primary" type="submit">Create room</button></form>',
          onMount: function (modal, close) {
            modal.querySelector("#create-room-form").addEventListener("submit", async function (event) {
              event.preventDefault();
              const form = event.currentTarget;
              const errorBox = modal.querySelector("#create-room-error");
              const button = form.querySelector('button[type="submit"]');
              button.disabled = true;
              try {
                const payload = {
                  title: form.elements.namedItem("title").value.trim(),
                  capacity: Number(form.elements.namedItem("capacity").value),
                  course_id: form.elements.namedItem("course_id").value || null
                };
                const result = await api.createRoom(payload);
                ui.toast("Room created.", "success");
                close();
                DEIY.go("#/app/rooms/" + encodeURIComponent(result.room.id));
              } catch (error) {
                errorBox.hidden = false;
                errorBox.innerHTML = ui.alert(error.message || "Could not create the room.", "error");
                button.disabled = false;
              }
            });
          }
        });
      };
      const newRoom = root.querySelector("#new-room");
      if (newRoom) newRoom.addEventListener("click", openCreate);
      root.querySelectorAll("[data-create-room]").forEach(function (button) {
        button.addEventListener("click", openCreate);
      });
      root.querySelectorAll("[data-delete-room]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-delete-room");
          const name = button.getAttribute("data-name") || "this room";
          const ok = await ui.confirmDialog(
            "Delete " + name + "? Participants, the room summary and its history will be removed.",
            { title: "Delete study room", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.deleteRoom(id);
            ui.toast("Study room deleted.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not delete the room.", "error");
            button.disabled = false;
          }
        });
      });
    }
  };


  pages.room = {
    app: true,
    title: "Study room",
    render: async function (ctx) {
      let data;
      try {
        data = await api.room(ctx.params.id);
      } catch (error) {
        return ui.pageHead("Study room", "") + ui.errorPanel(error, "Back to rooms") +
          '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost" href="#/app/rooms">← Rooms</a></div>';
      }
      const room = data.room;
      const participants = data.participants || [];
      const isStudent = ctx.user.role === "student";
      const isHost = room.host_id === ctx.user.id;
      const canEnd = isHost || ctx.user.role === "admin" || ctx.user.role === "teacher";
      const isParticipant = Boolean(data.is_participant);

      let joinPanel = "";
      if (room.status !== "open") {
        joinPanel = ui.alert("This room is closed. The AI summary will appear below once it is ready.", "info");
      } else if (isStudent && !isParticipant) {
        joinPanel =
          '<div class="panel stack"><div class="panel-head"><h3>Join this room</h3>' +
          ui.badge((participants.length) + "/" + room.capacity, "outline") + "</div>" +
          '<p class="small muted">Your academic ID and camera are both required. The room closes automatically ' +
          "after " + room.max_duration_minutes + " minutes.</p>" +
          '<div class="grid-2" style="align-items:start">' +
          '<div class="field"><label for="join-academic-id">Academic ID</label>' +
          '<input class="input mono" id="join-academic-id" value="' + ui.esc(ctx.user.academic_id || "") +
          '" placeholder="Your academic ID" /></div>' +
          '<div class="camera-preview"><video id="room-camera" autoplay muted playsinline></video>' +
          '<span class="badge badge-outline camera-badge" id="room-camera-badge">Camera off</span></div></div>' +
          '<label class="checkbox"><input type="checkbox" id="room-camera-consent" checked />' +
          "<span>My camera is working and I consent to it being on for this session.</span></label>" +
          '<div id="join-error" hidden></div>' +
          '<button class="btn btn-primary" type="button" id="join-room">' + ui.icon("camera") +
          " Turn on camera and join</button></div>";
      } else if (isStudent && isParticipant) {
        joinPanel =
          '<div class="panel stack"><div class="panel-head"><h3>You are in this room</h3>' +
          ui.badge("camera on", "success") + "</div>" +
          '<div class="camera-preview"><video id="room-camera" autoplay muted playsinline></video>' +
          '<span class="badge badge-success camera-badge">Local preview · camera on</span></div>' +
          '<div class="row"><button class="btn btn-ghost" type="button" id="leave-room">Leave room</button>' +
          (canEnd ? '<button class="btn btn-danger" type="button" id="end-room">End room for everyone</button>' : "") +
          "</div></div>";
      } else if (canEnd) {
        joinPanel =
          '<div class="panel stack"><div class="panel-head"><h3>Host controls</h3>' +
          ui.badge(room.status, ui.statusTone(room.status)) + "</div>" +
          '<p class="small muted">Ending the room closes it for everyone and queues the AI summary.</p>' +
          '<div class="row"><button class="btn btn-danger" type="button" id="end-room"' +
          (room.status !== "open" ? " disabled" : "") + ">End room and summarise</button>" +
          '<button class="btn btn-ghost" type="button" id="summary-refresh">Refresh summary</button></div></div>';
      }

      return (
        ui.pageHead(room.title, "Capacity " + room.capacity + " · " +
          (room.status === "open" ? "Closes " + ui.fmtRelative(room.ends_at) : "Closed " +
            ui.fmtDate(room.ends_at, true)),
          '<div class="row">' +
          (canEnd
            ? '<button class="btn btn-danger btn-sm" type="button" data-delete-room="' +
              ui.esc(room.id) + '" data-name="' + ui.esc(room.title) + '">Delete room</button>'
            : "") +
          '<a class="btn btn-ghost btn-sm" href="#/app/rooms">← Rooms</a></div>') +
        '<div class="grid-2" style="grid-template-columns:minmax(0,1.3fr) minmax(300px,0.7fr);align-items:start">' +
        '<div class="stack">' + joinPanel +
        '<div class="panel"><div class="panel-head"><h3>Participants</h3>' +
        '<span class="badge badge-outline">' + participants.length + "/" + room.capacity + "</span></div>" +
        '<div class="room-capacity" style="margin-bottom:0.7rem">' + seats(Object.assign({}, room,
          { participant_count: participants.length })) + "</div>" +
        (participants.length
          ? '<div class="list">' + participants.map(function (participant) {
              return '<div class="list-row"><span class="list-icon">' + ui.icon("user") + "</span>" +
                '<div class="list-body"><strong>' + ui.esc(participant.full_name || participant.user_id) +
                "</strong><span class=\"mono\">" + ui.esc(participant.academic_id || "—") + " · joined " +
                ui.esc(ui.fmtRelative(participant.joined_at)) + "</span></div>" +
                ui.badge(participant.camera_on ? "camera on" : "camera off",
                  participant.camera_on ? "success" : "amber") + "</div>";
            }).join("") + "</div>"
          : '<p class="small muted">No one has joined yet.</p>') + "</div>" +
        '<div class="panel stack" id="summary-panel"><div class="panel-head"><h3>AI meeting summary</h3>' +
        '<button class="btn btn-xs btn-ghost" type="button" id="summary-refresh-2">Refresh</button></div>' +
        '<div id="summary-body"><p class="small muted">The summary appears after the room ends. It usually takes ' +
        "5–10 minutes.</p></div></div></div>" +
        '<div class="stack"><div class="panel stack"><h3>Room policy</h3>' +
        '<div class="info-list"><div class="info-item"><span>Capacity</span><strong>' + room.capacity +
        "</strong></div>" +
        '<div class="info-item"><span>Maximum duration</span><strong>' + room.max_duration_minutes +
        " minutes</strong></div>" +
        '<div class="info-item"><span>Camera</span><strong>Required</strong></div>' +
        '<div class="info-item"><span>Academic ID</span><strong>Required to join</strong></div>' +
        '<div class="info-item"><span>Auto-close</span><strong>Enabled</strong></div></div></div>' +
        '<div class="panel stack"><h3>Be a good study partner</h3>' +
        '<p class="small muted">Keep your camera on, mute when not speaking and use the summary to follow up on ' +
        "action items. Never share another student's academic ID.</p>" +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How do study rooms work?">' +
        ui.icon("spark") + " Ask the guide</button></div>" +
        '<div class="panel stack" id="room-timer-panel"><h3>Time remaining</h3>' +
        '<div class="timer" id="room-timer">' +
        (room.status === "open" ? ui.fmtClock(room.remaining_seconds) : "00:00") + "</div>" +
        '<div class="progress"><span id="room-progress" style="width:0%"></span></div>' +
        '<p class="tiny muted">The room closes automatically when the timer reaches zero.</p></div></div></div>'
      );
    },
    after: function (root, ctx) {
      const roomId = ctx.params.id;
      const timer = root.querySelector("#room-timer");
      const progress = root.querySelector("#room-progress");
      let remaining = timer ? Number(timer.textContent.split(":").reduce(function (acc, part) {
        return acc * 60 + Number(part || 0);
      }, 0)) : 0;
      let pollHandle = null;
      let tickHandle = null;
      let stream = null;

      async function startCamera() {
        const video = root.querySelector("#room-camera");
        const badge = root.querySelector("#room-camera-badge");
        if (!video) return false;
        try {
          if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error("unsupported");
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          video.srcObject = stream;
          await video.play().catch(function () {});
          if (badge) {
            badge.textContent = "Camera on";
            badge.className = "badge badge-success camera-badge";
          }
          return true;
        } catch (_) {
          if (badge) {
            badge.textContent = "No preview";
            badge.className = "badge badge-amber camera-badge";
          }
          return false;
        }
      }

      const joinButton = root.querySelector("#join-room");
      if (joinButton) {
        joinButton.addEventListener("click", async function () {
          const errorBox = root.querySelector("#join-error");
          const academicId = (root.querySelector("#join-academic-id").value || "").trim();
          const consent = root.querySelector("#room-camera-consent").checked;
          if (!academicId) {
            errorBox.hidden = false;
            errorBox.innerHTML = ui.alert("Enter your academic ID to join.", "error");
            return;
          }
          if (!consent) {
            errorBox.hidden = false;
            errorBox.innerHTML = ui.alert("Camera consent is required for study rooms.", "error");
            return;
          }
          joinButton.disabled = true;
          joinButton.textContent = "Joining…";
          const cameraOk = await startCamera();
          if (!cameraOk) {
            const proceed = await ui.confirmDialog(
              "We could not start your camera preview. Study rooms require a working camera. " +
              "Join anyway with a device-level camera check?",
              { title: "Camera unavailable", confirmLabel: "Join anyway" }
            );
            if (!proceed) {
              joinButton.disabled = false;
              joinButton.innerHTML = ui.icon("camera") + " Turn on camera and join";
              return;
            }
          }
          try {
            const payload = await api.joinRoom(roomId, { academic_id: academicId, camera_on: true });
            ui.toast("Joined the study room.", "success");
            DEIY.state.roomLearning = payload;
            DEIY.rerender();
          } catch (error) {
            errorBox.hidden = false;
            errorBox.innerHTML = ui.alert(error.message || "Could not join the room.", "error");
            joinButton.disabled = false;
            joinButton.innerHTML = ui.icon("camera") + " Turn on camera and join";
          }
        });
        startCamera();
      } else if (root.querySelector("#room-camera")) {
        startCamera();
      }

      const leave = root.querySelector("#leave-room");
      if (leave) {
        leave.addEventListener("click", async function () {
          leave.disabled = true;
          try {
            await api.leaveRoom(roomId);
            if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
            ui.toast("You left the room.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not leave the room.", "error");
            leave.disabled = false;
          }
        });
      }

      const end = root.querySelector("#end-room");
      if (end) {
        end.addEventListener("click", async function () {
          const ok = await ui.confirmDialog(
            "End the room for everyone? The AI summary will be queued immediately.",
            { title: "End room", confirmLabel: "End room", danger: true }
          );
          if (!ok) return;
          end.disabled = true;
          try {
            await api.endRoom(roomId);
            ui.toast("Room ended. The AI summary is queued.", "success");
            if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not end the room.", "error");
            end.disabled = false;
          }
        });
      }

      const deleteRoom = root.querySelector("[data-delete-room]");
      if (deleteRoom) {
        deleteRoom.addEventListener("click", async function () {
          const ok = await ui.confirmDialog(
            "Delete this study room? Participants, the summary and its history will be removed.",
            { title: "Delete study room", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          deleteRoom.disabled = true;
          try {
            await api.deleteRoom(roomId);
            if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
            ui.toast("Study room deleted.", "success");
            DEIY.go("#/app/rooms");
          } catch (error) {
            ui.toast(error.message || "Could not delete the room.", "error");
            deleteRoom.disabled = false;
          }
        });
      }

      async function loadSummary() {
        const body = root.querySelector("#summary-body");
        if (!body) return;
        try {
          const summary = await api.roomSummary(roomId);
          const parsed = summary.summary && typeof summary.summary === "object" ? summary.summary : {};
          const status = summary.status;
          body.innerHTML =
            '<div class="row">' + ui.badge(status, ui.statusTone(status)) +
            (summary.provider ? '<span class="badge badge-outline">' + ui.esc(summary.provider) + "</span>" : "") +
            "</div>" +
            (status === "ready"
              ? '<div class="room-summary" style="margin-top:0.7rem"><h4>' +
                ui.esc(parsed.title || "Session summary") + "</h4><p>" +
                ui.esc(parsed.overview || summary.summary || "") + "</p>" +
                ((parsed.key_points || []).length ? "<h4>Key points</h4><ul>" + parsed.key_points.map(function (point) {
                  return "<li>" + ui.esc(point) + "</li>";
                }).join("") + "</ul>" : "") +
                ((parsed.action_items || []).length ? "<h4>Action items</h4><ul>" + parsed.action_items.map(function (item) {
                  return "<li>" + ui.esc(item) + "</li>";
                }).join("") + "</ul>" : "") +
                ((parsed.decisions || []).length ? "<h4>Decisions</h4><ul>" + parsed.decisions.map(function (item) {
                  return "<li>" + ui.esc(item) + "</li>";
                }).join("") + "</ul>" : "") + "</div>"
              : '<p class="small muted" style="margin-top:0.6rem">' +
                (status === "failed"
                  ? "The summary could not be generated. " + ui.esc(summary.error || "")
                  : "The summary is " + ui.esc(status || "queued") + ". It will appear here automatically.") + "</p>");
        } catch (error) {
          body.innerHTML = '<p class="small muted">' + ui.esc(
            error.status === 404 ? "The summary appears after the room ends." : error.message
          ) + "</p>";
        }
      }

      function refresh() {
        loadSummary();
      }
      const refreshButtons = root.querySelectorAll("#summary-refresh, #summary-refresh-2");
      refreshButtons.forEach(function (button) { button.addEventListener("click", refresh); });

      function tick() {
        remaining -= 1;
        if (remaining < 0) remaining = 0;
        if (timer) {
          timer.textContent = ui.fmtClock(remaining);
          timer.classList.toggle("danger", remaining <= 60 && remaining > 0);
        }
        const maxSeconds = (DEIY.state.roomLearning && DEIY.state.roomLearning.room &&
          DEIY.state.roomLearning.room.max_duration_minutes) || 45;
        if (progress) {
          progress.style.width = Math.min(100, Math.max(0,
            (1 - remaining / (maxSeconds * 60)) * 100)) + "%";
        }
        if (remaining === 0) {
          clearInterval(tickHandle);
          if (pollHandle) clearInterval(pollHandle);
          DEIY.rerender();
        }
      }

      loadSummary();
      tickHandle = setInterval(tick, 1000);
      pollHandle = setInterval(function () {
        api.room(roomId).then(function (data) {
          const current = data.room;
          if (current.status !== "open" && remaining > 0) {
            remaining = 0;
          }
          const count = root.querySelector("#summary-body");
          if (count) loadSummary();
        }).catch(function () {});
      }, 20000);

      DEIY.roomCleanup = function () {
        clearInterval(tickHandle);
        clearInterval(pollHandle);
        if (stream) stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
      };
    },
    destroy: function () {
      if (DEIY.roomCleanup) {
        DEIY.roomCleanup();
        DEIY.roomCleanup = null;
      }
    }
  };
})();
