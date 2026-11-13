
(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  const KINDS = ["video", "pdf", "epub", "audio", "image"];

  function kindIcon(kind) {
    return { video: "video", pdf: "file", epub: "book", audio: "audio", image: "image" }[kind] || "file";
  }

  function resourceCard(item, canManage) {
    const match = item.match
      ? '<span class="match-note" title="' + ui.esc(item.match.reason || "") + '">AI match ' +
        Math.round((item.match.score || 0) * 100) + "%</span>"
      : "";
    return (
      '<article class="resource-card"><div class="resource-cover" data-kind="' + ui.esc(item.kind) + '">' +
      '<span class="kind-label">' + ui.esc(item.kind) + "</span>" + ui.icon(kindIcon(item.kind)) + "</div>" +
      '<div class="resource-body"><div class="row" style="gap:0.4rem">' + match +
      (item.duration_seconds ? '<span class="resource-meta">' + ui.esc(ui.fmtDuration(item.duration_seconds)) +
        "</span>" : "") + "</div>" +
      "<h3>" + ui.esc(item.title) + "</h3>" +
      '<span class="resource-meta">' + ui.esc(item.author || "DEIY library") +
      (item.size_bytes ? " · " + ui.esc(ui.fmtBytes(item.size_bytes)) : "") + "</span>" +
      (item.ai_summary ? '<p class="small muted" style="display:-webkit-box;-webkit-line-clamp:2;' +
        '-webkit-box-orient:vertical;overflow:hidden">' + ui.esc(item.ai_summary) + "</p>" : "") +
      '<div class="resource-tags">' + (item.tags || []).slice(0, 4).map(function (tag) {
        return '<span class="tag">' + ui.esc(tag) + "</span>";
      }).join("") + "</div>" +
      '<div class="row" style="gap:0.4rem"><a class="btn btn-sm btn-primary" href="#/app/library/' +
      encodeURIComponent(item.id) + '">' + ui.icon("play") + " Open resource</a>" +
      (canManage
        ? '<button class="btn btn-sm btn-danger" type="button" data-delete-resource="' + ui.esc(item.id) +
          '" data-name="' + ui.esc(item.title) + '">Delete</button>'
        : "") +
      "</div></div></article>"
    );
  }

  pages.library = {
    app: true,
    title: "Library",
    render: async function (ctx) {
      const params = {
        q: ctx.query.get("q") || "",
        kind: ctx.query.get("kind") || "",
        course_id: ctx.query.get("course_id") || "",
        limit: 60
      };
      let resources;
      let courses;
      try {
        const results = await Promise.all([api.resources(params), api.courses().catch(() => null)]);
        resources = results[0];
        courses = results[1];
      } catch (error) {
        return ui.pageHead("Library", "Search the digital collection.") + ui.errorPanel(error, "Try again");
      }
      const list = resources.results || [];
      const courseList = (courses && courses.courses) || [];
      const courseMap = {};
      courseList.forEach(function (course) { courseMap[course.id] = course; });

      const courseOptions = ['<option value="">All courses</option>'].concat(
        courseList.map(function (course) {
          return '<option value="' + ui.esc(course.id) + '"' +
            (params.course_id === course.id ? " selected" : "") + ">" +
            ui.esc(course.code + " · " + course.title) + "</option>";
        })
      ).join("");

      return (
        ui.pageHead("Digital library", "AI-ranked search across videos, documents, audio and images.",
          (ctx.user.role === "teacher" || ctx.user.role === "admin")
            ? '<a class="btn btn-ghost btn-sm" href="#/app/manage?tab=resource">' + ui.icon("upload") +
              " Add resource</a>"
            : "") +
        '<form id="library-search" class="panel" style="padding:1rem">' +
        '<div class="search-bar">' + ui.icon("search") +
        '<input class="input" name="q" type="search" value="' + ui.esc(params.q) +
        '" placeholder="Try “algebra”, “cell biology” or an author name" aria-label="Search the library" /></div>' +
        '<div class="filter-bar" style="margin-bottom:0">' +
        '<a class="chip' + (!params.kind ? " active" : "") + '" href="#/app/library' +
        (params.q ? "?q=" + encodeURIComponent(params.q) : "") + '">All</a>' +
        KINDS.map(function (kind) {
          const query = new URLSearchParams();
          if (params.q) query.set("q", params.q);
          if (params.course_id) query.set("course_id", params.course_id);
          query.set("kind", kind);
          return '<a class="chip' + (params.kind === kind ? " active" : "") + '" href="#/app/library?' +
            query.toString() + '">' + ui.esc(ui.titleCase(kind)) + "</a>";
        }).join("") +
        '<span class="grow"></span>' +
        '<select class="select" name="course_id" style="width:auto;min-width:200px" aria-label="Filter by course">' +
        courseOptions + "</select>" +
        '<button class="btn btn-primary btn-sm" type="submit">Search</button></div></form>' +
        '<div class="row-between" style="margin:1rem 0 0.8rem"><p class="small muted">' +
        list.length + " resource" + (list.length === 1 ? "" : "s") +
        (params.q ? ' matching “' + ui.esc(params.q) + "”" : "") + "</p>" +
        (params.q ? '<span class="badge badge-teal">' + ui.icon("spark") + " AI-ranked results</span>" : "") +
        "</div>" +
        (list.length
          ? '<div class="resource-grid">' + list.map(function (item) {
              return resourceCard(item, ctx.user.role === "teacher" || ctx.user.role === "admin");
            }).join("") + "</div>"
          : ui.emptyState({
              icon: "library",
              title: params.q ? "No resources matched" : "The library is empty",
              text: params.q
                ? "Try a broader word, remove a filter, or ask the AI guide to suggest a topic."
                : "When teachers publish resources they will appear here.",
              action: params.q
                ? '<a class="btn btn-ghost" href="#/app/library">Clear search</a>'
                : ""
            })) +
        '<div class="panel stack" style="margin-top:1.4rem"><div class="row">' + ui.icon("spark") +
        '<div class="grow"><strong>Cannot find what you need?</strong><p class="small muted">' +
        "The AI guide can suggest search words or point you to the right course.</p></div>" +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How do I search the library?">' +
        "Ask the guide</button></div></div>"
      );
    },
    after: function (root, ctx) {
      const form = root.querySelector("#library-search");
      if (form) {
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          const text = (form.elements.namedItem("q").value || "").trim();
          const course = form.elements.namedItem("course_id").value;
          const query = new URLSearchParams();
          if (text) query.set("q", text);
          if (course) query.set("course_id", course);
          if (ctx.query.get("kind")) query.set("kind", ctx.query.get("kind"));
          DEIY.go("#/app/library" + (query.toString() ? "?" + query.toString() : ""));
        });
      }
      root.querySelectorAll("[data-delete-resource]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const id = button.getAttribute("data-delete-resource");
          const name = button.getAttribute("data-name") || "this resource";
          const ok = await ui.confirmDialog(
            "Delete " + name + "? The resource and its links will be removed.",
            { title: "Delete resource", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.deleteResource(id);
            ui.toast("Resource deleted.", "success");
            DEIY.rerender();
          } catch (error) {
            ui.toast(error.message || "Could not delete the resource.", "error");
            button.disabled = false;
          }
        });
      });
    }
  };


  pages.resource = {
    app: true,
    title: "Resource",
    render: async function (ctx) {
      const id = ctx.params.id;
      let access;
      try {
        access = await api.resourceAccess(id);
      } catch (error) {
        return ui.pageHead("Resource", "") + ui.errorPanel(error, "Back to library") +
          '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost" href="#/app/library">' +
          "← Library</a></div>";
      }
      const resource = access.resource;
      const variants = access.variants || [];
      const original = variants.find(function (variant) { return variant.resolution === "original"; }) ||
        variants.find(function (variant) { return variant.available !== false; }) || variants[0] || {};
      const audioVariant = variants.find(function (variant) {
        return variant.resolution === "audio" || variant.kind === "audio";
      });
      const mediaUrl = original.url || "";
      let viewer = "";

      if (resource.kind === "video") {
        viewer = mediaUrl
          ? '<video controls preload="metadata" playsinline src="' + ui.esc(mediaUrl) + '"></video>'
          : '<div class="stack center" style="padding:2rem"><strong>Video preview unavailable</strong>' +
            '<p class="small">The media file has not been uploaded yet. Use the download panel if a variant exists.</p></div>';
      } else if (resource.kind === "audio") {
        viewer = mediaUrl
          ? '<div style="padding:2rem;width:100%"><audio controls style="width:100%" src="' +
            ui.esc(mediaUrl) + '"></audio></div>'
          : '<div class="center" style="padding:2rem"><strong>Audio preview unavailable</strong></div>';
      } else if (resource.kind === "pdf") {
        viewer = mediaUrl
          ? '<iframe src="' + ui.esc(mediaUrl) + '" title="' + ui.esc(resource.title) + '"></iframe>'
          : '<div class="center" style="padding:2rem"><strong>PDF preview unavailable</strong>' +
            '<p class="small">The file has not been uploaded yet.</p></div>';
      } else if (resource.kind === "image") {
        viewer = mediaUrl
          ? '<img src="' + ui.esc(mediaUrl) + '" alt="' + ui.esc(resource.title) + '" />'
          : '<div class="center" style="padding:2rem"><strong>Image preview unavailable</strong></div>';
      } else {
        viewer = '<div class="center stack" style="padding:2rem">' + ui.icon("book") +
          "<strong>ePUB reader</strong><p class=\"small\">" +
          "This resource opens in the in-browser reader. Use download to read it offline.</p>" +
          '<a class="btn btn-sm btn-primary" href="' + ui.esc(mediaUrl) + '" target="_blank" rel="noopener">' +
          "Open in reader</a></div>";
      }

      const watermark = access.watermark || {};
      const overlay = watermark.overlay || {};
      return (
        ui.pageHead(resource.title, (resource.author || "DEIY library") + " · " +
          ui.titleCase(resource.kind) +
          (resource.duration_seconds ? " · " + ui.fmtDuration(resource.duration_seconds) : ""),
          '<div class="row">' +
          ((ctx.user.role === "teacher" || ctx.user.role === "admin")
            ? '<button class="btn btn-danger btn-sm" type="button" data-delete-resource="' +
              ui.esc(resource.id) + '" data-name="' + ui.esc(resource.title) + '">Delete</button>'
            : "") +
          '<a class="btn btn-ghost btn-sm" href="#/app/library">← Library</a></div>') +
        '<div class="grid-2" style="grid-template-columns:minmax(0,1.55fr) minmax(280px,0.45fr);align-items:start">' +
        '<div class="panel stack" style="padding:0.7rem">' +
        '<div class="media-frame" style="position:relative">' + viewer +
        '<div style="position:absolute;right:12px;bottom:10px;background:rgba(0,0,0,0.45);color:rgba(255,255,255,0.85);' +
        'font-size:10px;padding:2px 8px;border-radius:4px;pointer-events:none;letter-spacing:0.04em">' +
        ui.esc(overlay.text || ctx.user.full_name) + " · " + ui.esc(overlay.secondary_text || resource.title) +
        "</div></div>" +
        '<div class="row" style="padding:0.2rem 0.3rem"><span class="badge badge-teal">' +
        ui.icon("shield") + " Watermarked view</span>" +
        '<span class="badge badge-outline">' + ui.esc(ui.titleCase(access.viewer && access.viewer.mode || "in-browser")) +
        "</span>" +
        (audioVariant ? '<span class="badge badge-amber">Audio-only available</span>' : "") +
        '<span class="grow"></span><span class="tiny muted">Expires in ' +
        ui.esc(ui.fmtDuration(access.watermark && access.watermark.expires_in)) + "</span></div></div>" +
        '<div class="stack">' +
        '<div class="panel stack"><h3>About this resource</h3>' +
        (resource.ai_summary ? '<p class="small">' + ui.esc(resource.ai_summary) + "</p>" : "") +
        '<div class="resource-tags">' + (resource.tags || []).map(function (tag) {
          return '<span class="tag">' + ui.esc(tag) + "</span>";
        }).join("") + "</div>" +
        '<div class="info-list">' +
        '<div class="info-item"><span>Type</span><strong>' + ui.esc(ui.titleCase(resource.kind)) + "</strong></div>" +
        '<div class="info-item"><span>Size</span><strong>' + ui.esc(ui.fmtBytes(resource.size_bytes)) +
        "</strong></div>" +
        '<div class="info-item"><span>Transcript</span><strong>' +
        (resource.has_transcript ? "Available" : "Not available") + "</strong></div>" +
        '<div class="info-item"><span>Full-text search</span><strong>' +
        (access.viewer && access.viewer.full_text_search ? "Enabled" : "—") + "</strong></div></div></div>" +
        '<div class="panel stack"><h3>Download</h3>' +
        '<p class="small muted">Downloads carry your name and academic ID as a watermark. Do not share them.</p>' +
        '<div class="stack-sm" id="variant-list">' +
        (variants.length
          ? variants.map(function (variant) {
              return '<button class="btn btn-ghost btn-sm btn-block" type="button" data-variant="' +
                ui.esc(variant.resolution || "original") + '"' +
                (variant.available === false || !variant.url ? " disabled" : "") + ">" +
                ui.icon("download") + " " + ui.esc(variant.resolution || "original") +
                (variant.size_bytes ? " · " + ui.esc(ui.fmtBytes(variant.size_bytes)) : "") +
                "</button>";
            }).join("")
          : '<p class="small muted">No download variants are available yet.</p>') +
        "</div></div>" +
        '<div class="panel stack"><h3>Need a hand?</h3>' +
        '<p class="small muted">Questions about this topic? Ask the AI guide for a starting point.</p>' +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="Help me understand ' +
        ui.esc(resource.title) + '">' + ui.icon("spark") + " Ask about this resource</button></div>" +
        "</div></div>" +
        '<div class="row" style="margin-top:1rem"><a class="btn btn-ghost btn-sm" href="#/app/library">' +
        "← Back to library</a><span class=\"small muted\">Academic ID on this view: <strong class=\"mono\">" +
        ui.esc(ctx.user.academic_id || "—") + "</strong></span></div>"
      );
    },
    after: function (root, ctx) {
      root.querySelectorAll("[data-delete-resource]").forEach(function (button) {
        button.addEventListener("click", async function () {
          const name = button.getAttribute("data-name") || "this resource";
          const ok = await ui.confirmDialog(
            "Delete " + name + "? The resource and its links will be removed.",
            { title: "Delete resource", confirmLabel: "Delete", danger: true }
          );
          if (!ok) return;
          button.disabled = true;
          try {
            await api.deleteResource(button.getAttribute("data-delete-resource"));
            ui.toast("Resource deleted.", "success");
            DEIY.go("#/app/library");
          } catch (error) {
            ui.toast(error.message || "Could not delete the resource.", "error");
            button.disabled = false;
          }
        });
      });
      root.querySelectorAll("[data-variant]").forEach(function (button) {
        button.addEventListener("click", async function () {
          button.disabled = true;
          try {
            const data = await api.resourceDownload(ctx.params.id, button.getAttribute("data-variant"));
            const mark = data.watermark || {};
            ui.openModal({
              title: "Watermarked download ready",
              subtitle: data.variant + " · expires in " + ui.fmtDuration(data.expires_in),
              body: ui.alert("This file is personalised with your name and academic ID. Sharing it is prohibited.", "warn") +
                (data.download_url
                  ? '<div class="panel stack" style="margin-top:0.8rem"><p class="small muted">Watermark text</p>' +
                    '<p class="mono small">' + ui.esc((mark.overlay && mark.overlay.text) || "") + "</p>" +
                    '<a class="btn btn-primary" href="' + ui.esc(data.download_url) + '" target="_blank" ' +
                    'rel="noopener" download>' + ui.icon("download") + " Download file</a></div>"
                  : ui.alert("The media file has not been uploaded for this resource yet.", "info"))
            });
          } catch (error) {
            ui.toast(error.message || "Could not prepare the download.", "error");
          } finally {
            button.disabled = false;
          }
        });
      });
    }
  };
})();
