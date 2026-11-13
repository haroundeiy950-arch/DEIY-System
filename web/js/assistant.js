(function () {
  "use strict";

  const api = window.DEIY && window.DEIY.api;
  if (!api) return;

  const GREETING =
    "Hi! I am the DEIY AI guide. I can explain how to apply, verify your email, " +
    "get approved, find library resources, join study rooms or prepare for exams. " +
    "You do not need an account to ask me a question.";

  const DEFAULT_PROMPTS = [
    "How do I apply step by step?",
    "What details or documents do I need?",
    "I did not receive my OTP",
    "How long does approval take?",
    "What is an academic ID?"
  ];

  const ICONS = {
    chat:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.4 8.8 8.8 0 0 1-3.9-.9L3 21l1.9-5.4A8.4 8.4 0 1 1 21 11.5Z"/><path d="M8.5 10h7M8.5 13.5h4.5"/></svg>',
    close:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>',
    send:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m4 4 16 8-16 8 3.5-8L4 4Z"/><path d="M7.5 12H20"/></svg>',
    spark:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v3M12 18v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M3 12h3M18 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/><circle cx="12" cy="12" r="3.2"/></svg>'
  };

  let panel;
  let log;
  let input;
  let sendButton;
  let promptsBox;
  let statusLine;
  let fab;
  let busy = false;
  let messages = 0;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function build() {
    fab = el("button", "assistant-fab");
    fab.type = "button";
    fab.setAttribute("aria-label", "Ask the DEIY AI assistant");
    fab.innerHTML = ICONS.chat + '<span class="fab-dot"></span>';
    fab.addEventListener("click", open);

    panel = el("section", "assistant-panel");
    panel.setAttribute("aria-label", "DEIY AI assistant");
    panel.hidden = true;

    const head = el("div", "assistant-head");
    const avatar = el("div", "assistant-avatar");
    avatar.innerHTML = ICONS.spark;
    const titleWrap = el("div");
    titleWrap.appendChild(el("strong", "", "DEIY AI guide"));
    statusLine = el("span", "", "Online · no sign-in needed");
    titleWrap.appendChild(statusLine);
    const close = el("button", "icon-btn");
    close.type = "button";
    close.setAttribute("aria-label", "Close assistant");
    close.innerHTML = ICONS.close;
    close.addEventListener("click", hide);
    head.append(avatar, titleWrap, close);

    const body = el("div", "assistant-body");
    log = el("div", "assistant-log");
    log.setAttribute("role", "log");
    log.setAttribute("aria-live", "polite");

    promptsBox = el("div", "assistant-prompts");

    const compose = el("form", "assistant-compose");
    input = el("textarea", "textarea");
    input.rows = 1;
    input.placeholder = "Ask about applying, OTP, approval, exams…";
    input.setAttribute("aria-label", "Your question");
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submit();
      }
    });
    sendButton = el("button", "btn btn-primary");
    sendButton.type = "submit";
    sendButton.setAttribute("aria-label", "Send question");
    sendButton.innerHTML = ICONS.send;
    compose.append(input, sendButton);
    compose.addEventListener("submit", (event) => {
      event.preventDefault();
      submit();
    });

    const foot = el("div", "assistant-foot");
    const footText = el("span", "", "AI answers can be imperfect. Never share your password.");
    const guideLink = el("a", "", "Application guide");
    guideLink.href = "#/apply";
    guideLink.addEventListener("click", hide);
    foot.append(footText, guideLink);

    body.append(log, promptsBox, compose, foot);
    panel.append(head, body);
    document.body.append(fab, panel);

    addMessage("bot", GREETING);
    renderPrompts(DEFAULT_PROMPTS);
    updateIdentity();
  }

  function updateIdentity() {
    if (!statusLine) return;
    const signedIn = Boolean(api.store.token());
    statusLine.textContent = signedIn
      ? "Signed in · support tickets enabled"
      : "Online · no sign-in needed";
  }

  function renderPrompts(prompts) {
    if (!promptsBox) return;
    promptsBox.replaceChildren();
    (prompts || []).slice(0, 5).forEach((prompt) => {
      const chip = el("button", "chip", prompt);
      chip.type = "button";
      chip.addEventListener("click", () => ask(prompt));
      promptsBox.appendChild(chip);
    });
  }

  function addMessage(kind, text, meta) {
    const node = el("div", "assistant-msg " + kind);
    node.textContent = text;
    if (meta) {
      const metaNode = el("span", "msg-meta", meta);
      node.appendChild(metaNode);
    }
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    messages += 1;
    if (messages > 60) {
      while (log.children.length > 50) log.firstElementChild.remove();
    }
    return node;
  }

  function addAction(text, actions) {
    const node = addMessage("system", text);
    if (actions && actions.length) {
      const row = el("div", "row");
      row.style.marginTop = "0.5rem";
      actions.forEach((action) => {
        const link = el("a", "btn btn-sm " + (action.primary ? "btn-primary" : "btn-ghost"), action.label);
        link.href = action.href;
        link.addEventListener("click", hide);
        row.appendChild(link);
      });
      node.appendChild(row);
    }
    return node;
  }

  function showTyping() {
    const node = el("div", "assistant-msg bot");
    node.dataset.typing = "true";
    node.innerHTML = '<span class="chat-bubble typing" style="background:transparent;border:0;padding:0"><span></span><span></span><span></span></span>';
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    return node;
  }

  function removeTyping() {
    const node = log.querySelector('[data-typing="true"]');
    if (node) node.remove();
  }

  async function submit() {
    const question = (input.value || "").trim();
    if (!question) {
      input.focus();
      return;
    }
    input.value = "";
    await ask(question);
  }

  async function ask(question) {
    if (!question || busy) return;
    open();
    busy = true;
    sendButton.disabled = true;
    input.disabled = true;
    addMessage("user", question);
    renderPrompts([]);
    const typing = showTyping();

    try {
      const data = await api.assistant(question, { page: location.hash || "#/" });
      removeTyping();
      const confidence =
        typeof data.confidence === "number"
          ? Math.round(data.confidence * 100) + "% confidence"
          : null;
      const meta = [data.provider ? "AI · " + data.provider : null, confidence]
        .filter(Boolean)
        .join(" · ");
      addMessage("bot", data.answer || "I could not find an answer to that.", meta || null);

      if (data.escalated) {
        const signedIn = Boolean(api.store.token());
        if (data.ticket_id) {
          addAction(
            "I opened support ticket " + data.ticket_id + " so a human agent can follow up.",
            [{ label: "Open helpdesk", href: "#/app/help", primary: true }]
          );
        } else {
          addAction(
            data.next_action ||
              "Create an account, then open a support ticket so a human agent can help.",
            [
              { label: "Apply now", href: "#/apply", primary: true },
              { label: "Sign in", href: "#/login" }
            ]
          );
        }
        if (signedIn && !data.ticket_id) {
          addAction("You are signed in, so you can also open a ticket from the helpdesk.", [
            { label: "Open helpdesk", href: "#/app/help", primary: true }
          ]);
        }
      }

      renderPrompts(Array.isArray(data.quick_prompts) ? data.quick_prompts : DEFAULT_PROMPTS.slice(0, 3));
    } catch (error) {
      removeTyping();
      addMessage(
        "system",
        error && error.message
          ? error.message
          : "The assistant is unavailable right now. Please try again."
      );
      renderPrompts(DEFAULT_PROMPTS.slice(0, 3));
    } finally {
      busy = false;
      sendButton.disabled = false;
      input.disabled = false;
      updateIdentity();
      setTimeout(() => input && input.focus(), 40);
    }
  }

  function open(prefill) {
    if (!panel) return;
    panel.hidden = false;
    fab.hidden = true;
    setTimeout(() => input && input.focus(), 60);
    if (typeof prefill === "string" && prefill.trim()) {
      ask(prefill.trim());
    }
  }

  function hide() {
    if (!panel) return;
    panel.hidden = true;
    fab.hidden = false;
    fab.focus();
  }

  function toggle() {
    if (panel.hidden) open();
    else hide();
  }

  window.DEIYAssistant = {
    open,
    close: hide,
    toggle,
    ask
  };

  window.addEventListener("deiy:session-changed", updateIdentity);
  window.addEventListener("deiy:unauthorized", updateIdentity);

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-assistant]");
    if (!trigger) return;
    event.preventDefault();
    open(trigger.getAttribute("data-assistant") || undefined);
  });

  build();
})();
