(function () {
  "use strict";

  const DEIY = (window.DEIY = window.DEIY || {});
  const ui = DEIY.ui;
  const api = DEIY.api;
  const pages = (DEIY.pages = DEIY.pages || {});

  const DEMO_ACCOUNTS = [
    { role: "Admin", email: "admin@deiy.local", password: "AdminPass1" },
    { role: "Teacher", email: "teacher@deiy.local", password: "TeacherPass1" },
    { role: "Student", email: "student@deiy.local", password: "StudentPass1" },
    { role: "Proctor", email: "proctor@deiy.local", password: "ProctorPass1" }
  ];

  const COUNTRIES = [
    "Somalia", "Kenya", "Ethiopia", "Djibouti", "Uganda", "Tanzania", "Rwanda",
    "South Sudan", "Sudan", "Egypt", "Nigeria", "Ghana", "South Africa", "India",
    "Pakistan", "Bangladesh", "Indonesia", "Malaysia", "Turkey", "United Arab Emirates",
    "Saudi Arabia", "Qatar", "Jordan", "Lebanon", "United Kingdom", "United States",
    "Canada", "Germany", "France", "Netherlands", "Sweden", "Norway", "Australia"
  ];

  const FALLBACK_PROGRAMS = [
    { code: "CS", name: "Computer Science" },
    { code: "IT", name: "Information Technology" },
    { code: "SE", name: "Software Engineering" },
    { code: "BBA", name: "Business Administration" },
    { code: "AF", name: "Accounting and Finance" },
    { code: "NUR", name: "Nursing" },
    { code: "PH", name: "Public Health" },
    { code: "EDU", name: "Education" },
    { code: "CE", name: "Civil Engineering" },
    { code: "EE", name: "Electrical Engineering" },
    { code: "LAW", name: "Law" },
    { code: "AGR", name: "Agriculture" },
    { code: "ECO", name: "Economics" },
    { code: "SW", name: "Social Work" },
    { code: "GEN", name: "General Studies" }
  ];

  const AUTH_PROVIDERS = [
    { code: "email", name: "Email and password" },
    { code: "google", name: "Google" },
    { code: "facebook", name: "Facebook" },
    { code: "other", name: "Other provider" }
  ];

  const FALLBACK_GUIDE = {
    minimum_age: 15,
    programs: FALLBACK_PROGRAMS,
    auth_providers: AUTH_PROVIDERS,
    steps: [
      { title: "Create your account", description: "Enter your four-part full name, email and a strong password." },
      { title: "Add your details", description: "Choose your program, nationality, phone numbers and date of birth, then upload a clear photo." },
      { title: "Verify your email", description: "Enter the 6-digit code or use the activation link we email you." },
      { title: "Wait for approval", description: "An administrator reviews your application, usually within 1–2 working days." },
      { title: "Start learning", description: "Your academic ID arrives by email; sign in to open the library and exams." }
    ],
    requirements: [],
    faq: []
  };

  function guideFor(ctx) {
    return (ctx && ctx.guide) || DEIY.state.guide || FALLBACK_GUIDE;
  }

  function devHint() {
    try {
      const code = sessionStorage.getItem("deiy.dev_code");
      if (code) {
        return ui.alert(
          "Development mode: your verification code is " + code + " (also shown in the API response).",
          "warn"
        );
      }
    } catch (_) {

    }
    return "";
  }

  function storeDevCode(data) {
    try {
      if (data && data.dev_code) sessionStorage.setItem("deiy.dev_code", data.dev_code);
      else sessionStorage.removeItem("deiy.dev_code");
    } catch (_) {
    }
  }

  pages.landing = {
    public: true,
    chrome: true,
    title: "DEIY · Learn without limits",
    render: async function (ctx) {
      let guide = guideFor(ctx);
      if (!ctx.guide && !DEIY.state.guide) {
        try {
          guide = await api.guide();
          DEIY.state.guide = guide;
        } catch (_) {
          guide = FALLBACK_GUIDE;
        }
      }
      const steps = (guide.steps || FALLBACK_GUIDE.steps).slice(0, 5);
      const features = [
        {
          icon: "user",
          title: "A guided application",
          text: "Four name parts, a photo, your program, nationality and phone numbers. The assistant explains each field as you go.",
          link: "#/apply",
          cta: "Start your application"
        },
        {
          icon: "library",
          title: "A library that finds things",
          text: "Videos, PDFs, ePUBs and audio with AI-ranked search, a watermarked viewer and data-saving downloads.",
          link: "#/app/library",
          cta: "Explore the library"
        },
        {
          icon: "exam",
          title: "Fair, proctored exams",
          text: "Camera verification, resilient autosave, integrity analysis and automatic submission when time runs out.",
          link: "#/app/exams",
          cta: "See exams"
        },
        {
          icon: "room",
          title: "Small study rooms",
          text: "10–15 students, cameras on, 45-minute sessions and an AI summary delivered soon after you finish.",
          link: "#/app/rooms",
          cta: "Open study rooms"
        },
        {
          icon: "chart",
          title: "Progress you can see",
          text: "Gradebook averages, attendance, AI insights and a calendar that brings deadlines into one place.",
          link: "#/app/gradebook",
          cta: "View progress"
        },
        {
          icon: "help",
          title: "Help before you sign in",
          text: "The AI guide answers application, OTP, approval and camera questions without an account.",
          link: "#/guide",
          cta: "Read the guide"
        }
      ];

      return (
        '<section class="hero"><div class="container">' +
        '<div><span class="eyebrow">DEIY learning platform</span>' +
        "<h1>Apply once.<br /><em>Learn anywhere.</em></h1>" +
        '<p class="hero-lead">A complete education platform built around you: a guided application, ' +
        "a searchable digital library, proctored exams, small AI-summarised study rooms and progress " +
        "insights — with an AI guide that helps even before you have an account.</p>" +
        '<div class="hero-actions">' +
        '<a class="btn btn-amber" href="#/apply">' + ui.icon("arrow") + " Apply now</a>" +
        '<button class="btn btn-light" type="button" data-assistant="How do I apply step by step?">' +
        ui.icon("spark") + " Ask the AI guide</button>" +
        '<a class="btn btn-light" href="#/login">Sign in</a></div>' +
        '<div class="hero-stats">' +
        '<div class="hero-stat"><strong>5 min</strong><span>To apply</span></div>' +
        '<div class="hero-stat"><strong>3</strong><span>Code + photo + email steps</span></div>' +
        '<div class="hero-stat"><strong>24/7</strong><span>AI application help</span></div>' +
        "</div></div>" +
        '<aside class="journey-card"><h2>Your path from applicant to student</h2>' +
        "<p>Five short steps. The AI guide is beside you the whole way.</p>" +
        '<ol class="journey">' +
        steps
          .map(function (step, index) {
            const ai = index === 2;
            return (
              '<li><span class="journey-step' + (ai ? " ai-step" : "") + '">' +
              (index + 1) + "</span><div><strong>" + ui.esc(step.title) + "</strong>" +
              "<p>" + ui.esc(step.description) + "</p></div></li>"
            );
          })
          .join("") +
        '<li><span class="journey-step ai-step">' + ui.icon("spark") + "</span>" +
        "<div><strong>Ask whenever you are stuck</strong><p>The AI guide answers without a login.</p></div></li>" +
        "</ol></aside></div></section>" +

        '<section class="section"><div class="container">' +
        '<div class="section-head center"><span class="eyebrow">Everything in one place</span>' +
        "<h2>Built for the way students actually study</h2>" +
        "<p>Every feature is connected to the same account, the same academic ID and the same AI layer.</p></div>" +
        '<div class="feature-grid">' +
        features
          .map(function (feature) {
            return (
              '<article class="feature-card"><div class="feature-icon">' +
              ui.icon(feature.icon) + "</div><h3>" + ui.esc(feature.title) + "</h3><p>" +
              ui.esc(feature.text) + '</p><a class="feature-link" href="' + feature.link + '">' +
              ui.esc(feature.cta) + " →</a></article>"
            );
          })
          .join("") +
        "</div></div></section>" +

        '<section class="section section-alt"><div class="container">' +
        '<div class="section-head"><span class="eyebrow">Applying is simple</span>' +
        "<h2>No jargon. No dead ends.</h2>" +
        "<p>If you have never applied online before, start here. Each field includes a plain-language hint, " +
        "and the assistant can explain anything you do not understand.</p></div>" +
        '<div class="steps-grid">' +
        [
          ["Create your account", "Four name parts, one email and a password with upper case, lower case and a number."],
          ["Add your photo and details", "Your program, nationality, phone numbers, date of birth, country and a clear JPG, PNG or WebP under 5 MB."],
          ["Verify your email", "Type the 6-digit code from your inbox. Codes last 10 minutes and can be resent."],
          ["Get approved and sign in", "An administrator reviews your application. Your academic ID arrives by email."]
        ]
          .map(function (item) {
            return "<article class=\"step-card\"><h3>" + ui.esc(item[0]) + "</h3><p>" +
              ui.esc(item[1]) + "</p></article>";
          })
          .join("") +
        "</div>" +
        '<div class="row" style="margin-top:1.4rem">' +
        '<a class="btn btn-primary" href="#/apply">Start your application</a>' +
        '<a class="btn btn-ghost" href="#/guide">Read the full guide</a>' +
        '<button class="btn btn-ghost" type="button" data-assistant="What do I need before I start?">' +
        "Ask what you need</button></div></div></section>" +

        '<section class="section"><div class="container">' +
        '<div class="ai-callout"><div><span class="eyebrow">AI guide</span>' +
        "<h2>Stuck? Ask in your own words.</h2>" +
        "<p>The guide knows how registration, OTP verification, admin approval, academic IDs and the " +
        "camera check work. It answers before sign-in, in plain language, and points you to the next action.</p>" +
        '<div class="hero-actions"><button class="btn btn-amber" type="button" ' +
        'data-assistant="How do I apply step by step?">Ask the AI guide</button>' +
        '<a class="btn btn-light" href="#/guide">Browse the FAQ</a></div></div>' +
        '<div class="chat-preview"><div class="chat-bubble user">I have never applied online before. What do I do?</div>' +
        '<div class="chat-bubble">Start with Apply. You will need your full name in four parts, an email address, ' +
        "a password, your date of birth, your country and a clear photo. I will explain each step as you go.</div>" +
        '<div class="chat-bubble user">What happens after I verify my email?</div>' +
        '<div class="chat-bubble">Your status becomes Pending Approval. An administrator reviews it, usually in ' +
        "1–2 working days. Once approved, your academic ID is emailed to you and you can sign in.</div>" +
        '<div class="chat-bubble typing"><span></span><span></span><span></span></div></div></div></div></section>' +

        `<section class="section section-alt"><div class="container"><div class="grid-2" style="align-items:start;gap:2rem"><div><div class="section-head" style="margin-bottom:1.2rem"><span class="eyebrow">For every role</span><h2>One platform, four views</h2></div><div class="role-grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">${[
          ["Student", "Apply, verify, learn, take exams, join rooms and track progress."],
          ["Teacher", "Publish resources, author exams and assignments, review submissions."],
          ["Proctor", "Monitor attempts, integrity signals and exam activity."],
          ["Administrator", "Approve applications, manage roles, tune policy and watch AI cost."]
        ]
          .map(function (item) {
            return '<div class="role-card"><h3>' + ui.esc(item[0]) + "</h3><p>" + ui.esc(item[1]) + "</p></div>";
          })
          .join("")}</div></div><div class="demo-box"><h3>Try the demo accounts</h3><p>These accounts exist when you run <code>python seed.py</code>. Click one to open the sign-in page with it filled in.</p><div class="demo-accounts">${DEMO_ACCOUNTS.map(function (account) {
            return (
              '<button class="demo-account" type="button" data-demo-email="' + ui.esc(account.email) +
              '" data-demo-password="' + ui.esc(account.password) + '"><strong>' + ui.esc(account.role) +
              "</strong>" + ui.esc(account.email) + "</button>"
            );
          }).join("")}</div><p class="tiny">Seeded data only. Change every password before using a real deployment.</p><a class="btn btn-light btn-sm" href="#/login">Open sign in</a></div></div></div></section>`
      );
    },
    after: function (root) {
      root.querySelectorAll("[data-demo-email]").forEach(function (button) {
        button.addEventListener("click", function () {
          sessionStorage.setItem("deiy.demo_email", button.getAttribute("data-demo-email"));
          sessionStorage.setItem("deiy.demo_password", button.getAttribute("data-demo-password"));
          DEIY.go("#/login");
        });
      });
    }
  };
  pages.apply = {
    public: true,
    title: "Apply to DEIY",
    render: async function (ctx) {
      const guide = guideFor(ctx);
      const countries = COUNTRIES.map(function (name) {
        return '<option value="' + ui.esc(name) + '">' + ui.esc(name) + "</option>";
      }).join("");
      const programs = (guide.programs || FALLBACK_PROGRAMS).map(function (program) {
        return '<option value="' + ui.esc(program.name) + '">' + ui.esc(program.name) +
          " (" + ui.esc(program.code) + ")</option>";
      }).join("");
      const providers = (guide.auth_providers || AUTH_PROVIDERS).map(function (provider) {
        return '<option value="' + ui.esc(provider.code) + '">' + ui.esc(provider.name) + "</option>";
      }).join("");
      return (
        '<section class="section-tight"><div class="container" style="max-width:900px">' +
        '<div class="auth-card wide">' +
        '<span class="eyebrow">Application</span>' +
        "<h1>Join DEIY in three short steps</h1>" +
        '<p class="lead">You do not need to prepare documents. You need your full name, an email ' +
        "address, a password, your program of study, your nationality, your phone numbers, your " +
        "date of birth and a clear photo. You must be at least " + ui.esc(guide.minimum_age || 15) +
        " years old.</p>" +
        '<div class="row" style="margin-top:0.9rem">' +
        '<button class="btn btn-ghost btn-sm" type="button" data-assistant="How do I apply step by step?">' +
        ui.icon("spark") + " Ask the AI guide</button>" +
        '<a class="btn btn-ghost btn-sm" href="#/guide">Application guide</a></div>' +
        '<div class="wizard-steps" aria-hidden="true">' +
        '<div class="wizard-step active" data-step-indicator="1">Your name &amp; email</div>' +
        '<div class="wizard-step" data-step-indicator="2">Photo &amp; details</div>' +
        '<div class="wizard-step" data-step-indicator="3">Password &amp; review</div>' +
        "</div>" +
        '<form id="apply-form" novalidate>' +

        '<div class="wizard-pane" data-step="1">' +
        '<div class="form-grid">' +
        field("First name", "first_name", "text", "Amina", "As written on your records") +
        field("Second name", "second_name", "text", "Yusuf", "Your father's or second given name") +
        field("Third name", "third_name", "text", "Hassan", "Your grandfather's or third given name") +
        field("Family name", "family_name", "text", "Ali", "Your surname / family name") +
        '<div class="span-2">' + field("Email address", "email", "email", "amina@example.com",
          "Verification and approval messages go here") + "</div>" +
        "</div>" +
        ui.alert("Your full name must have four parts. Example: Amina Yusuf Hassan Ali.", "info") +
        '<div class="wizard-actions"><a class="btn btn-ghost" href="#/">Cancel</a>' +
        '<button class="btn btn-primary" type="button" data-next="2">Continue ' + ui.icon("arrow") + "</button></div>" +
        "</div>" +

        '<div class="wizard-pane" data-step="2" hidden>' +
        '<div class="form-grid">' +
        '<div class="field"><label for="program">Program of study</label>' +
        '<select class="select" id="program" name="program" required>' +
        '<option value="">Choose your program</option>' + programs + "</select></div>" +
        '<div class="field"><label for="nationality">Nationality</label>' +
        '<select class="select" id="nationality" name="nationality" required>' +
        '<option value="">Choose your nationality</option>' + countries + "</select></div>" +
        '<div class="field"><label for="dob">Date of birth</label>' +
        '<input class="input" id="dob" name="date_of_birth" type="date" required />' +
        '<span class="hint">You must be at least ' + ui.esc(guide.minimum_age || 15) + " years old.</span></div>" +
        '<div class="field"><label for="country">Country / residence</label>' +
        '<select class="select" id="country" name="country" required>' +
        '<option value="">Choose your country</option>' + countries + "</select></div>" +
        '<div class="field"><label for="phone_number">Phone number</label>' +
        '<input class="input" id="phone_number" name="phone_number" type="tel" ' +
        'placeholder="+252 61 234 5678" required />' +
        '<span class="hint">Your own number, including the country code.</span></div>' +
        '<div class="field"><label for="father_phone_number">Father\'s phone number</label>' +
        '<input class="input" id="father_phone_number" name="father_phone_number" type="tel" ' +
        'placeholder="+252 61 876 5432" required />' +
        '<span class="hint">A parent or guardian number we can call.</span></div>' +
        "</div>" +
        '<div class="photo-drop"><div class="photo-preview" id="photo-preview">' + ui.icon("user") + "</div>" +
        '<div class="stack-sm"><strong>Your photo</strong>' +
        '<span class="small muted">A clear, front-facing photo. JPG, PNG or WebP, 5 MB maximum.</span>' +
        '<div class="row"><label class="btn btn-ghost btn-sm" for="photo-file">' + ui.icon("upload") +
        ' Choose a file<input id="photo-file" type="file" accept="image/jpeg,image/png,image/webp" hidden /></label>' +
        '<span class="tiny muted" id="photo-status">No file selected</span></div>' +
        '<input class="input" id="photo-url" name="photo_url" type="url" ' +
        'placeholder="Or paste an https image URL" autocomplete="off" /></div></div>' +
        '<div class="wizard-actions"><button class="btn btn-ghost" type="button" data-back="1">Back</button>' +
        '<button class="btn btn-primary" type="button" data-next="3">Review your details ' + ui.icon("arrow") +
        "</button></div></div>" +

        '<div class="wizard-pane" data-step="3" hidden>' +
        '<div class="form-grid">' +
        field("Create a password", "password", "password", "At least 8 characters",
          "Include upper case, lower case and a number") +
        field("Confirm password", "confirm_password", "password", "Repeat your password", "") +
        '<div class="span-2 field"><label for="auth_provider">How will you sign in?</label>' +
        '<select class="select" id="auth_provider" name="auth_provider">' + providers + "</select>" +
        '<span class="hint">Choose Google, Facebook or another provider if you prefer. ' +
        "Every application still verifies its email address before review.</span></div>" +
        "</div>" +
        '<div id="apply-review" class="review-list"></div>' +
        '<label class="checkbox"><input type="checkbox" id="apply-truth" />' +
        "<span>I confirm the information is accurate and that I understand an administrator will review " +
        "my application before my account is activated.</span></label>" +
        '<div id="apply-error" hidden></div>' +
        '<div class="wizard-actions"><button class="btn btn-ghost" type="button" data-back="2">Back</button>' +
        '<button class="btn btn-amber" type="submit" id="apply-submit">Submit application ' +
        ui.icon("arrow") + "</button></div></div>" +
        "</form>" +
        '<p class="auth-footer-note">Already applied? <a href="#/verify">Verify your email</a> · ' +
        '<a href="#/login">Sign in</a></p>' +
        "</div></div></section>"
      );
    },
    after: function (root) {
      const form = root.querySelector("#apply-form");
      if (!form) return;
      const panes = Array.from(form.querySelectorAll("[data-step]"));
      const indicators = Array.from(root.querySelectorAll("[data-step-indicator]"));
      let step = 1;
      let photoData = "";
      const errorBox = root.querySelector("#apply-error");

      const byName = function (name) {
        return form.elements.namedItem(name);
      };
      const values = function () {
        return {
          first_name: (byName("first_name").value || "").trim(),
          second_name: (byName("second_name").value || "").trim(),
          third_name: (byName("third_name").value || "").trim(),
          family_name: (byName("family_name").value || "").trim(),
          email: (byName("email").value || "").trim().toLowerCase(),
          date_of_birth: byName("date_of_birth").value,
          country: byName("country").value,
          nationality: byName("nationality").value,
          program: byName("program").value,
          phone_number: (byName("phone_number").value || "").trim(),
          father_phone_number: (byName("father_phone_number").value || "").trim(),
          auth_provider: byName("auth_provider").value || "email",
          password: byName("password").value,
          photo: photoData || (byName("photo_url").value || "").trim()
        };
      };

      const phoneValid = function (value) {
        const digits = String(value || "").replace(/\D/g, "");
        return digits.length >= 7 && digits.length <= 15;
      };

      const ageOn = function (isoDate) {
        const dob = new Date(isoDate + "T00:00:00");
        if (isNaN(dob.getTime())) return -1;
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const beforeBirthday =
          today.getMonth() < dob.getMonth() ||
          (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate());
        if (beforeBirthday) age -= 1;
        return age;
      };
      const showError = function (message) {
        errorBox.hidden = false;
        errorBox.innerHTML = ui.alert(message, "error");
        errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
      };

      const goTo = function (target) {
        if (target === 2) {
          const data = values();
          if (!data.first_name || !data.second_name || !data.third_name || !data.family_name) {
            ui.toast("Enter all four parts of your full name.", "error");
            return;
          }
          if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(data.email)) {
            ui.toast("Enter a valid email address.", "error");
            return;
          }
        }
        if (target === 3) {
          const data = values();
          if (!data.program) {
            ui.toast("Choose your program of study.", "error");
            return;
          }
          if (!data.nationality) {
            ui.toast("Choose your nationality.", "error");
            return;
          }
          if (!data.date_of_birth) {
            ui.toast("Choose your date of birth.", "error");
            return;
          }
          const dob = new Date(data.date_of_birth + "T00:00:00");
          if (isNaN(dob.getTime()) || dob >= new Date()) {
            ui.toast("Date of birth must be in the past.", "error");
            return;
          }
          const minimumAge = Number(guide.minimum_age || 15);
          if (ageOn(data.date_of_birth) < minimumAge) {
            ui.toast("You must be at least " + minimumAge + " years old to apply.", "error");
            return;
          }
          if (!data.country) {
            ui.toast("Choose your country.", "error");
            return;
          }
          if (!phoneValid(data.phone_number)) {
            ui.toast("Enter a valid phone number (7-15 digits).", "error");
            return;
          }
          if (!phoneValid(data.father_phone_number)) {
            ui.toast("Enter a valid father/guardian phone number (7-15 digits).", "error");
            return;
          }
          if (!data.photo) {
            ui.toast("Add a photo by uploading a file or pasting an image URL.", "error");
            return;
          }
          renderReview();
        }
        step = target;
        panes.forEach(function (pane) {
          pane.hidden = Number(pane.getAttribute("data-step")) !== step;
        });
        indicators.forEach(function (indicator) {
          const index = Number(indicator.getAttribute("data-step-indicator"));
          indicator.classList.toggle("active", index === step);
          indicator.classList.toggle("done", index < step);
        });
        form.scrollIntoView({ behavior: "smooth", block: "start" });
      };

      const renderReview = function () {
        const data = values();
        const review = root.querySelector("#apply-review");
        const provider = (guide.auth_providers || AUTH_PROVIDERS).filter(function (item) {
          return item.code === data.auth_provider;
        })[0];
        const rows = [
          ["Full name", [data.first_name, data.second_name, data.third_name, data.family_name].join(" ")],
          ["Email", data.email],
          ["Program of study", data.program],
          ["Nationality", data.nationality],
          ["Phone number", data.phone_number],
          ["Father's phone number", data.father_phone_number],
          ["Date of birth", ui.fmtDate(data.date_of_birth)],
          ["Country", data.country],
          ["Sign-in method", provider ? provider.name : data.auth_provider],
          ["Photo", data.photo.indexOf("data:image/") === 0 ? "Uploaded photo" : data.photo]
        ];
        review.innerHTML = rows
          .map(function (row) {
            return '<dl class="review-item"><dt>' + ui.esc(row[0]) + "</dt><dd>" + ui.esc(row[1]) +
              "</dd></dl>";
          })
          .join("");
      };

      form.querySelectorAll("[data-next]").forEach(function (button) {
        button.addEventListener("click", function () {
          goTo(Number(button.getAttribute("data-next")));
        });
      });
      form.querySelectorAll("[data-back]").forEach(function (button) {
        button.addEventListener("click", function () {
          goTo(Number(button.getAttribute("data-back")));
        });
      });

      const fileInput = root.querySelector("#photo-file");
      fileInput.addEventListener("change", function () {
        const file = fileInput.files && fileInput.files[0];
        const status = root.querySelector("#photo-status");
        if (!file) return;
        if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
          status.textContent = "Use a JPG, PNG or WebP image";
          ui.toast("That file type is not supported. Choose a JPG, PNG or WebP.", "error");
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          status.textContent = "Image is larger than 5 MB";
          ui.toast("Choose an image smaller than 5 MB.", "error");
          return;
        }
        const reader = new FileReader();
        reader.onload = function () {
          photoData = String(reader.result || "");
          root.querySelector("#photo-preview").innerHTML =
            '<img src="' + photoData + '" alt="Your photo preview" />';
          status.textContent = file.name + " · " + ui.fmtBytes(file.size);
          byName("photo_url").value = "";
        };
        reader.readAsDataURL(file);
      });

      byName("photo_url").addEventListener("input", function () {
        if (this.value) {
          photoData = "";
          root.querySelector("#photo-preview").innerHTML =
            '<img src="' + ui.esc(this.value) + '" alt="" onerror="this.remove()" />';
        }
      });

      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const data = values();
        if (data.password.length < 8 || !/[A-Z]/.test(data.password) || !/[a-z]/.test(data.password) ||
            !/\d/.test(data.password)) {
          showError("Your password needs at least 8 characters, one upper-case letter, one lower-case letter and one number.");
          return;
        }
        if (data.password !== byName("confirm_password").value) {
          showError("The two passwords do not match.");
          return;
        }
        if (!root.querySelector("#apply-truth").checked) {
          showError("Please confirm that your information is accurate.");
          return;
        }
        const button = root.querySelector("#apply-submit");
        button.disabled = true;
        button.textContent = "Submitting…";
        try {
          const result = await api.register({
            full_name: [data.first_name, data.second_name, data.third_name, data.family_name].join(" "),
            email: data.email,
            password: data.password,
            photo: data.photo,
            date_of_birth: data.date_of_birth,
            program: data.program,
            phone_number: data.phone_number,
            father_phone_number: data.father_phone_number,
            nationality: data.nationality,
            country: data.country,
            auth_provider: data.auth_provider,
            language: DEIY.i18n ? DEIY.i18n.getLanguage() : "en"
          });
          api.store.pendingEmail(data.email);
          storeDevCode(result);
          if (result.dev_link) sessionStorage.setItem("deiy.dev_link", result.dev_link);
          if (result.user && result.user.registration_number) {
            sessionStorage.setItem("deiy.registration_number", result.user.registration_number);
          }
          ui.toast(
            "Application received. Registration number: " +
              ((result.user && result.user.registration_number) || "issued") +
              ". Check your email for the 6-digit code.",
            "success"
          );
          DEIY.go("#/verify");
        } catch (error) {
          showError(error.message || "We could not submit your application.");
          button.disabled = false;
          button.textContent = "Submit application";
        }
      });
    }
  };

  function field(label, name, type, placeholder, hint) {
    return (
      '<div class="field"><label for="' + name + '">' + ui.esc(label) + "</label>" +
      '<input class="input" id="' + name + '" name="' + name + '" type="' + type + '" ' +
      'placeholder="' + ui.esc(placeholder) + '" ' +
      (type === "password" ? 'autocomplete="new-password" ' : "") +
      "required />" + (hint ? '<span class="hint">' + ui.esc(hint) + "</span>" : "") + "</div>"
    );
  }

  /* ------------------------------------------------------------------- verify */
  pages.verify = {
    public: true,
    title: "Verify your email",
    render: async function (ctx) {
      const token = ctx.query.get("token") || "";
      const error = ctx.query.get("error") || "";
      const pending = api.store.getPendingEmail() || "";
      const registration = sessionStorage.getItem("deiy.registration_number") || "";
      return (
        '<section class="section-tight"><div class="container" style="max-width:620px">' +
        '<div class="auth-card">' +
        '<span class="eyebrow">Step 3 of 5</span>' +
        "<h1>Verify your email</h1>" +
        '<p class="lead">Enter the 6-digit code we sent to your inbox, or use the activation link from the email. ' +
        "Codes expire after 10 minutes.</p>" +
        (error ? ui.alert(error, "error") : "") +
        (registration
          ? ui.alert("Your registration number is " + registration + ". Keep it for your records.", "success")
          : "") +
        (token ? ui.alert("We are verifying your activation link…", "info") : "") +
        devHint() +
        '<div id="verify-result"></div>' +
        '<form id="verify-form" class="stack" style="margin-top:1.1rem" ' + (token ? "hidden" : "") + ">" +
        '<div class="field"><label for="verify-email">Email address</label>' +
        '<input class="input" id="verify-email" name="email" type="email" value="' +
        ui.esc(pending) + '" placeholder="you@example.com" required /></div>' +
        '<div class="field"><label for="verify-code">6-digit code</label>' +
        '<input class="input otp-input" id="verify-code" name="code" inputmode="numeric" ' +
        'autocomplete="one-time-code" maxlength="6" pattern="\\d{6}" placeholder="000000" required />' +
        '<span class="hint">Check your spam folder if it has not arrived.</span></div>' +
        '<div id="verify-error" hidden></div>' +
        '<button class="btn btn-primary btn-block" type="submit" id="verify-submit">Verify email</button>' +
        "</form>" +
        '<div class="row" style="justify-content:space-between;margin-top:1rem">' +
        '<button class="btn btn-ghost btn-sm" type="button" id="resend">Resend code</button>' +
        '<a class="btn btn-ghost btn-sm" href="#/login">Go to sign in</a></div>' +
        '<div class="timeline">' +
        '<div class="timeline-item done"><span class="timeline-dot">' + ui.icon("check") +
        '</span><div><strong>Account created</strong><span class="muted small"> Your details are saved.</span></div></div>' +
        '<div class="timeline-item current"><span class="timeline-dot">2</span>' +
        "<div><strong>Verify your email</strong><span class=\"muted small\"> Enter the code or open the link.</span></div></div>" +
        '<div class="timeline-item"><span class="timeline-dot">3</span>' +
        "<div><strong>Admin review</strong><span class=\"muted small\"> Usually 1–2 working days.</span></div></div>" +
        '<div class="timeline-item"><span class="timeline-dot">4</span>' +
        "<div><strong>Academic ID issued</strong><span class=\"muted small\"> Emailed to you on approval.</span></div></div>" +
        "</div>" +
        '<p class="auth-footer-note">Need help? <button class="btn btn-xs btn-ghost" type="button" ' +
        'data-assistant="I did not receive my OTP">Ask the AI guide</button></p>' +
        "</div></div></section>"
      );
    },
    after: async function (root, ctx) {
      const form = root.querySelector("#verify-form");
      const errorBox = root.querySelector("#verify-error");
      const result = root.querySelector("#verify-result");
      const token = ctx.query.get("token");

      const showError = function (message) {
        errorBox.hidden = false;
        errorBox.innerHTML = ui.alert(message, "error");
      };

      const success = function (data) {
        form.hidden = true;
        result.innerHTML =
          ui.alert("Email verified. Your application is now pending administrator approval.", "success") +
          '<div class="panel stack" style="margin-top:1rem"><h3>What happens next?</h3>' +
          '<p class="small muted">An administrator reviews your application, usually within 1–2 working days. ' +
          "Once approved, your unique academic ID is emailed to you. You can then sign in.</p>" +
          '<div class="row"><a class="btn btn-primary" href="#/login">Go to sign in</a>' +
          '<button class="btn btn-ghost" type="button" data-assistant="How long does approval take?">' +
          "Ask about approval</button></div></div>";
        ui.toast("Email verified. Approval is the next step.", "success");
      };

      if (token) {
        try {
          const data = await api.verifyEmail({ token: token });
          storeDevCode(null);
          success(data);
          return;
        } catch (error) {
          form.hidden = false;
          showError(error.message || "That activation link is invalid or expired. Enter a code instead.");
        }
      }

      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const email = form.elements.namedItem("email").value.trim().toLowerCase();
        const code = form.elements.namedItem("code").value.trim();
        if (!/^\d{6}$/.test(code)) {
          showError("Enter the 6-digit code from your email.");
          return;
        }
        const button = root.querySelector("#verify-submit");
        button.disabled = true;
        button.textContent = "Verifying…";
        try {
          const data = await api.verifyEmail({ email: email, code: code });
          api.store.pendingEmail(email);
          storeDevCode(null);
          success(data);
        } catch (error) {
          showError(error.message || "We could not verify that code.");
          button.disabled = false;
          button.textContent = "Verify email";
        }
      });

      root.querySelector("#resend").addEventListener("click", async function () {
        const email =
          (form.elements.namedItem("email").value || api.store.getPendingEmail() || "").trim().toLowerCase();
        if (!email) {
          showError("Enter your email address first.");
          return;
        }
        this.disabled = true;
        try {
          const data = await api.resendVerification(email);
          storeDevCode(data);
          ui.toast("A new code is on its way. It expires in 10 minutes.", "success");
          if (data && data.dev_code) {
            ui.toast("Development code: " + data.dev_code, "info");
          }
        } catch (error) {
          showError(error.message || "We could not resend the code.");
        } finally {
          this.disabled = false;
        }
      });
    }
  };

  /* -------------------------------------------------------------------- login */
  pages.login = {
    public: true,
    title: "Sign in",
    render: async function (ctx) {
      const verified = ctx.query.get("verified") === "1";
      return (
        '<section class="auth-shell">' +
        '<aside class="auth-aside">' +
        '<a class="brand" href="#/"><span class="brand-mark">D</span><span>DEIY<small>Learning platform</small></span></a>' +
        '<h1>Welcome back to your learning space.</h1>' +
        '<p>Sign in to open the library, sit proctored exams, join study rooms and see your progress.</p>' +
        '<div class="auth-points">' +
        ["Your academic ID unlocks study rooms and watermarked downloads.",
          "Autosave keeps exam answers safe if your connection drops.",
          "The AI guide is available before and after sign-in."]
          .map(function (text) {
            return '<div class="auth-point">' + ui.icon("check") + "<span>" + ui.esc(text) + "</span></div>";
          })
          .join("") +
        "</div>" +
        '<div style="margin-top:auto"><a class="btn btn-light btn-sm" href="#/apply">Need an account? Apply</a></div>' +
        "</aside>" +
        '<main class="auth-main">' +
        '<div class="auth-top"><a class="brand" href="#/"><span class="brand-mark">D</span>' +
        "<span>DEIY<small>Learning platform</small></span></a>" +
        '<a class="btn btn-ghost btn-sm" href="#/">Back to home</a></div>' +
        '<div class="auth-card"><span class="eyebrow">Sign in</span><h1>Continue learning</h1>' +
        '<p class="lead">Use the email address and password you registered with. If your application is still ' +
        "pending, you will see that status here.</p>" +
        (verified ? ui.alert("Your email is verified. Sign in once your application is approved.", "success") : "") +
        '<form id="login-form" class="stack" style="margin-top:1.2rem">' +
        '<div class="field"><label for="login-email">Email address</label>' +
        '<input class="input" id="login-email" name="email" type="email" autocomplete="email" ' +
        'placeholder="you@example.com" required /></div>' +
        '<div class="field"><label for="login-password">Password</label>' +
        '<div class="search-bar"><input class="input" id="login-password" name="password" type="password" ' +
        'autocomplete="current-password" placeholder="Your password" required />' +
        '<button class="icon-btn" type="button" id="toggle-password" aria-label="Show password" ' +
        'style="position:absolute;right:4px;border:0;background:transparent">' + ui.icon("lock") + "</button></div></div>" +
        '<div id="login-error" hidden></div>' +
        '<button class="btn btn-primary btn-block" type="submit" id="login-submit">Sign in</button>' +
        "</form>" +
        '<div class="row" style="justify-content:space-between;margin-top:1rem">' +
        '<span class="small muted">New here? <a href="#/apply">Apply for an account</a></span>' +
        '<button class="btn btn-xs btn-ghost" type="button" data-assistant="I need help signing in">Need help?</button>' +
        "</div>" +
        '<div class="panel-flat" style="margin-top:1rem;padding:0.9rem;border:1px solid var(--line);border-radius:12px">' +
        '<strong class="small">Prefer Google, Facebook or another provider?</strong>' +
        '<p class="tiny muted" style="margin:0.35rem 0 0.6rem">Choose your provider on the ' +
        "application form. Every application verifies its email address before an administrator " +
        "reviews it.</p>" +
        '<a class="btn btn-ghost btn-sm" href="#/apply">Apply with a provider</a></div>' +
        '<div class="divider"></div>' +
        '<p class="tiny muted"><strong>Demo accounts</strong> (after running <code>python seed.py</code>)</p>' +
        '<div class="chat-suggestions" style="margin-top:0.5rem">' +
        DEMO_ACCOUNTS.map(function (account) {
          return '<button class="chip" type="button" data-demo-email="' + ui.esc(account.email) +
            '" data-demo-password="' + ui.esc(account.password) + '">' + ui.esc(account.role) + "</button>";
        }).join("") +
        "</div></div>" +
        '<p class="auth-footer-note">Trouble signing in? <a href="#/verify">Verify your email</a> or ' +
        '<a href="#/guide">read the guide</a>.</p>' +
        "</main></section>"
      );
    },
    after: function (root, ctx) {
      const form = root.querySelector("#login-form");
      const errorBox = root.querySelector("#login-error");
      const emailInput = root.querySelector("#login-email");
      const passwordInput = root.querySelector("#login-password");
      const demoEmail = sessionStorage.getItem("deiy.demo_email");
      const demoPassword = sessionStorage.getItem("deiy.demo_password");
      if (demoEmail) emailInput.value = demoEmail;
      if (demoPassword) passwordInput.value = demoPassword;
      sessionStorage.removeItem("deiy.demo_password");
      sessionStorage.removeItem("deiy.demo_email");
      const pending = api.store.getPendingEmail();
      if (!emailInput.value && pending) emailInput.value = pending;

      const toggle = root.querySelector("#toggle-password");
      toggle.addEventListener("click", function () {
        passwordInput.type = passwordInput.type === "password" ? "text" : "password";
      });

      root.querySelectorAll("[data-demo-email]").forEach(function (button) {
        button.addEventListener("click", function () {
          emailInput.value = button.getAttribute("data-demo-email");
          passwordInput.value = button.getAttribute("data-demo-password");
          passwordInput.focus();
        });
      });

      form.addEventListener("submit", async function (event) {
        event.preventDefault();
        errorBox.hidden = true;
        const button = root.querySelector("#login-submit");
        button.disabled = true;
        button.textContent = "Signing in…";
        try {
          await api.login(emailInput.value.trim(), passwordInput.value);
          ui.toast("Signed in. Welcome back.", "success");
          window.dispatchEvent(new CustomEvent("deiy:session-changed"));
          const redirect = ctx.query.get("next");
          DEIY.go(redirect ? decodeURIComponent(redirect) : "#/app/dashboard");
        } catch (error) {
          errorBox.hidden = false;
          const message = error.message || "We could not sign you in.";
          let extra = "";
          if (/pending/i.test(message)) {
            extra = '<p class="small" style="margin-top:0.5rem">Your application is waiting for administrator ' +
              "approval. You will receive your academic ID by email once it is reviewed.</p>";
          } else if (/verify/i.test(message)) {
            extra = '<p class="small" style="margin-top:0.5rem"><a href="#/verify">Verify your email</a> to continue.</p>';
          }
          errorBox.innerHTML = ui.alert(message + extra, "error");
          button.disabled = false;
          button.textContent = "Sign in";
        }
      });
    }
  };

  /* -------------------------------------------------------------------- guide */
  pages.guide = {
    public: true,
    chrome: true,
    title: "Application guide",
    render: async function (ctx) {
      const guide = guideFor(ctx);
      return (
        '<section class="section-tight"><div class="container" style="max-width:960px">' +
        '<div class="section-head"><span class="eyebrow">Plain-language guide</span>' +
        "<h1 style=\"font-family:var(--serif);font-size:clamp(2rem,4vw,3rem);margin:0.6rem 0\">" +
        "How to apply, step by step</h1>" +
        "<p>If you have never applied online before, follow this page from top to bottom. " +
        "The AI guide can answer follow-up questions without an account.</p></div>" +
        '<div class="row" style="margin-bottom:1.5rem">' +
        '<button class="btn btn-primary" type="button" data-assistant="How do I apply step by step?">' +
        ui.icon("spark") + " Ask the AI guide</button>" +
        '<a class="btn btn-ghost" href="#/apply">Start applying</a></div>' +
        '<div class="grid-2" style="align-items:start">' +
        '<div class="panel stack"><h3>The five steps</h3>' +
        (guide.steps || [])
          .map(function (step, index) {
            return '<div class="timeline-item"><span class="timeline-dot">' + (index + 1) + "</span>" +
              "<div><strong>" + ui.esc(step.title) + '</strong><p class="small muted">' +
              ui.esc(step.description) + "</p></div></div>";
          })
          .join("") +
        "</div>" +
        '<div class="panel stack"><h3>What you need</h3>' +
        ((guide.requirements || []).length
          ? guide.requirements
              .map(function (item) {
                return '<div class="info-item"><span>' + ui.esc(item.label) + "</span><strong>" +
                  ui.esc(item.detail) + "</strong></div>";
              })
              .join("")
          : '<p class="small muted">A four-part full name, email, strong password, program, nationality, phone numbers, photo, date of birth and country.</p>') +
        '<div class="divider"></div><h3>Good to know</h3>' +
        '<div class="info-item"><span>Minimum age</span><strong>' + ui.esc(guide.minimum_age || 15) +
        " years</strong></div>" +
        '<div class="info-item"><span>Code length</span><strong>6 digits</strong></div>' +
        '<div class="info-item"><span>Code lifetime</span><strong>' +
        ui.esc(guide.otp_ttl_minutes || 10) + " minutes</strong></div>" +
        '<div class="info-item"><span>Photo limit</span><strong>5 MB</strong></div>' +
        '<div class="info-item"><span>Approval time</span><strong>1–2 working days</strong></div>' +
        "</div></div>" +
        '<div class="panel stack" style="margin-top:1.2rem"><h3>Frequently asked questions</h3>' +
        ((guide.faq || []).length
          ? guide.faq
              .map(function (item) {
                return '<details style="padding:0.5rem 0;border-bottom:1px solid var(--line)">' +
                  "<summary style=\"cursor:pointer;font-weight:650\">" + ui.esc(item.question) +
                  '</summary><p class="small muted" style="margin-top:0.4rem">' + ui.esc(item.answer) +
                  "</p></details>";
              })
              .join("")
          : '<p class="small muted">Use the AI guide for answers.</p>') +
        "</div>" +
        '<div class="ai-callout" style="margin-top:1.5rem"><div><span class="eyebrow">Still unsure?</span>' +
        "<h2>Ask in your own words.</h2><p>No account needed. The guide can explain registration, OTP, " +
        "approval, academic IDs, cameras and exams.</p></div>" +
        '<div class="row"><button class="btn btn-amber" type="button" data-assistant="I am not sure how to apply">' +
        "Open the AI guide</button></div></div>" +
        "</div></section>"
      );
    }
  };
})();
