/* ==========================================================================
   DEIY API client
   Small, dependency-free wrapper around the FastAPI backend. The bearer token
   is kept in localStorage; every error becomes an ApiError with a friendly
   message so the UI can show it directly.
   ========================================================================== */
(function () {
  "use strict";

  const TOKEN_KEY = "deiy.access_token";
  const USER_KEY = "deiy.user";
  const PENDING_KEY = "deiy.pending_email";

  class ApiError extends Error {
    constructor(message, options) {
      super(message);
      this.name = "ApiError";
      const opts = options || {};
      this.status = opts.status || 0;
      this.code = opts.code || "request_failed";
      this.details = opts.details || null;
    }
  }

  const store = {
    token() {
      try { return localStorage.getItem(TOKEN_KEY); } catch (_) { return null; }
    },
    user() {
      try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch (_) { return null; }
    },
    setSession(token, user) {
      try {
        if (token) localStorage.setItem(TOKEN_KEY, token);
        if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
      } catch (_) { /* private mode */ }
    },
    updateUser(user) {
      try { localStorage.setItem(USER_KEY, JSON.stringify(user)); } catch (_) { /* ignore */ }
    },
    pendingEmail(email) {
      try {
        if (email) localStorage.setItem(PENDING_KEY, email);
        else localStorage.removeItem(PENDING_KEY);
      } catch (_) { /* ignore */ }
    },
    getPendingEmail() {
      try { return localStorage.getItem(PENDING_KEY); } catch (_) { return null; }
    },
    clear() {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      } catch (_) { /* ignore */ }
    }
  };

  async function request(path, options) {
    const opts = options || {};
    const method = opts.method || "GET";
    const headers = Object.assign({}, opts.headers || {});
    const auth = opts.auth !== false;
    const token = store.token();

    if (auth && token) headers.Authorization = "Bearer " + token;
    let body = opts.body;
    if (body !== undefined && body !== null && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        body,
        signal: opts.signal
      });
    } catch (error) {
      throw new ApiError(
        "Cannot reach the DEIY server. Check your connection and try again.",
        { code: "network_error" }
      );
    }

    const contentType = response.headers.get("content-type") || "";
    let data = null;
    if (contentType.includes("application/json")) {
      try { data = await response.json(); } catch (_) { data = null; }
    } else if (opts.raw) {
      data = await response.text();
    } else {
      try { data = await response.text(); } catch (_) { data = null; }
    }

    if (!response.ok) {
      if (response.status === 401 && auth && token) {
        store.clear();
        window.dispatchEvent(new CustomEvent("deiy:unauthorized"));
      }
      const payload = data && typeof data === "object" ? data : {};
      const message =
        payload.message ||
        (typeof data === "string" && data && data.length < 300 ? data : "") ||
        "Request failed (" + response.status + ").";
      throw new ApiError(message, {
        status: response.status,
        code: payload.error || "http_" + response.status,
        details: payload.details || null
      });
    }
    return data;
  }

  function query(params) {
    const search = new URLSearchParams();
    Object.keys(params || {}).forEach((key) => {
      const value = params[key];
      if (value !== undefined && value !== null && value !== "") search.set(key, value);
    });
    const text = search.toString();
    return text ? "?" + text : "";
  }

  const api = {
    ApiError,
    store,
    request,

    /* -------------------------------------------------------------- public */
    guide() { return request("/support/guide", { auth: false }); },
    assistant(question, context) {
      if (store.token()) {
        return request("/utilities/helpdesk", { method: "POST", body: { question } });
      }
      return request("/support/assistant", {
        method: "POST",
        auth: false,
        body: { question, context: context || { page: location.hash || "#/" } }
      });
    },

    /* ---------------------------------------------------------------- auth */
    register(payload) {
      return request("/auth/register", { method: "POST", auth: false, body: payload });
    },
    verifyEmail(payload) {
      return request("/auth/verify-email", { method: "POST", auth: false, body: payload });
    },
    resendVerification(email) {
      return request("/auth/resend-verification", { method: "POST", auth: false, body: { email } });
    },
    async login(email, password) {
      const data = await request("/auth/login", {
        method: "POST",
        auth: false,
        body: { email, password }
      });
      store.setSession(data.access_token, data.user);
      return data;
    },
    async devAdminSession() {
      const data = await request("/auth/dev-session", {
        method: "POST",
        auth: false
      });
      store.setSession(data.access_token, data.user);
      return data;
    },
    async me() {
      const data = await request("/auth/me");
      if (data && data.user) store.updateUser(data.user);
      return data.user;
    },
    logout() {
      const token = store.token();
      store.clear();
      if (token) request("/auth/logout", { method: "POST" }).catch(() => {});
    },

    /* ------------------------------------------------------------- library */
    courses(params) { return request("/library/courses" + query(params)); },
    resources(params) { return request("/library/resources" + query(params)); },
    resource(id) { return request("/library/resources/" + encodeURIComponent(id)); },
    resourceAccess(id) { return request("/library/resources/" + encodeURIComponent(id) + "/access"); },
    resourceDownload(id, variant) {
      return request(
        "/library/resources/" + encodeURIComponent(id) + "/download" +
          query({ variant: variant || "original" })
      );
    },
    liveSessions(params) { return request("/library/live-sessions" + query(params)); },
    createCourse(payload) { return request("/library/courses", { method: "POST", body: payload }); },
    createResource(payload) { return request("/library/resources", { method: "POST", body: payload }); },
    scheduleLiveSession(payload) {
      return request("/library/live-sessions", { method: "POST", body: payload });
    },
    startLiveSession(id) {
      return request("/library/live-sessions/" + encodeURIComponent(id) + "/start", { method: "POST" });
    },
    endLiveSession(id) {
      return request("/library/live-sessions/" + encodeURIComponent(id) + "/end", { method: "POST" });
    },

    /* --------------------------------------------------------------- exams */
    exams(params) { return request("/exams" + query(params)); },
    exam(id) { return request("/exams/" + encodeURIComponent(id)); },
    cameraCheck(id, payload) {
      return request("/exams/" + encodeURIComponent(id) + "/camera-check", { method: "POST", body: payload });
    },
    startAttempt(id, payload) {
      return request("/exams/" + encodeURIComponent(id) + "/attempts", { method: "POST", body: payload });
    },
    attempt(id) { return request("/exams/attempts/" + encodeURIComponent(id)); },
    autosaveAttempt(id, answers, clientSeq) {
      return request("/exams/attempts/" + encodeURIComponent(id) + "/autosave", {
        method: "POST",
        body: { answers, client_seq: clientSeq || 0 }
      });
    },
    submitAttempt(id) {
      return request("/exams/attempts/" + encodeURIComponent(id) + "/submit", { method: "POST" });
    },
    proctorEvents(id, events) {
      return request("/exams/attempts/" + encodeURIComponent(id) + "/proctor-events", {
        method: "POST",
        body: { events }
      });
    },
    integrity(id) {
      return request("/exams/attempts/" + encodeURIComponent(id) + "/integrity");
    },
    examAttempts(examId) {
      return request("/exams/" + encodeURIComponent(examId) + "/attempts");
    },

    /* --------------------------------------------------------------- rooms */
    rooms(params) { return request("/rooms" + query(params)); },
    createRoom(payload) { return request("/rooms", { method: "POST", body: payload }); },
    room(id) { return request("/rooms/" + encodeURIComponent(id)); },
    joinRoom(id, payload) {
      return request("/rooms/" + encodeURIComponent(id) + "/join", { method: "POST", body: payload });
    },
    leaveRoom(id) {
      return request("/rooms/" + encodeURIComponent(id) + "/leave", { method: "POST" });
    },
    endRoom(id, transcript) {
      return request("/rooms/" + encodeURIComponent(id) + "/end", {
        method: "POST",
        body: transcript ? { transcript } : {}
      });
    },
    roomSummary(id) { return request("/rooms/" + encodeURIComponent(id) + "/summary"); },

    /* ----------------------------------------------------------- utilities */
    calendar() { return request("/utilities/calendar"); },
    gradebook(studentId, insights) {
      return request("/utilities/gradebook" + query({ student_id: studentId, insights: insights !== false }));
    },
    notifications(unreadOnly) {
      return request("/utilities/notifications" + query({ unread_only: unreadOnly ? "true" : "" }));
    },
    markAllNotificationsRead() {
      return request("/utilities/notifications/read-all", { method: "POST" });
    },
    markNotificationRead(id) {
      return request("/utilities/notifications/" + encodeURIComponent(id) + "/read", { method: "POST" });
    },
    helpdesk(question) {
      return request("/utilities/helpdesk", { method: "POST", body: { question } });
    },
    createTicket(subject, body) {
      return request("/utilities/tickets", { method: "POST", body: { subject, body } });
    },
    tickets(params) { return request("/utilities/tickets" + query(params)); },
    ticket(id) { return request("/utilities/tickets/" + encodeURIComponent(id)); },
    replyTicket(id, body) {
      return request("/utilities/tickets/" + encodeURIComponent(id) + "/reply", { method: "POST", body: { body } });
    },
    assignments(params) { return request("/utilities/assignments" + query(params)); },
    createAssignment(payload) {
      return request("/utilities/assignments", { method: "POST", body: payload });
    },
    submitAssignment(id, content) {
      return request("/utilities/assignments/" + encodeURIComponent(id) + "/submit", {
        method: "POST",
        body: { content }
      });
    },
    assignmentSubmissions(id) {
      return request("/utilities/assignments/" + encodeURIComponent(id) + "/submissions");
    },
    gradeSubmission(id, payload) {
      return request("/utilities/assignments/" + encodeURIComponent(id) + "/grade", {
        method: "POST",
        body: payload
      });
    },
    metrics() { return request("/utilities/metrics"); },

    /* --------------------------------------------------------------- admin */
    adminUsers(params) { return request("/admin/users" + query(params)); },
    adminApplications() { return request("/admin/applications"); },
    adminUser(id) { return request("/admin/users/" + encodeURIComponent(id)); },
    approveUser(id) {
      return request("/admin/users/" + encodeURIComponent(id) + "/approve", { method: "POST" });
    },
    rejectUser(id, reason) {
      return request("/admin/users/" + encodeURIComponent(id) + "/reject", {
        method: "POST",
        body: { reason }
      });
    },
    setUserRole(id, role) {
      return request("/admin/users/" + encodeURIComponent(id) + "/role", {
        method: "PATCH",
        body: { role }
      });
    },
    createStaff(payload) { return request("/admin/staff", { method: "POST", body: payload }); },
    adminConfig() { return request("/admin/config"); },
    updateAdminConfig(values) {
      return request("/admin/config", { method: "PATCH", body: { values } });
    },
    aiUsage() { return request("/admin/ai-usage"); },
    auditLogs(limit) { return request("/admin/audit-logs" + query({ limit: limit || 100 })); }
  };

  window.DEIY = window.DEIY || {};
  window.DEIY.api = api;
  window.DEIY.ApiError = ApiError;
})();
