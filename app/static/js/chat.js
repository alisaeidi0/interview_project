// Floor Assistant — chat UI. Sessions, history, theming, feedback. Vanilla JS.
(() => {
  "use strict";

  const messagesEl = document.getElementById("messages");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("input");
  const sendEl = document.getElementById("send");
  const suggestionsEl = document.getElementById("suggestions");
  const sessionsEl = document.getElementById("sessions");
  const newChatEl = document.getElementById("new-chat");
  const mainTitleEl = document.getElementById("main-title");
  const sidebarEl = document.getElementById("sidebar");

  let currentSessionId = null;

  const DOMAIN_LABELS = {
    safety: "Safety procedures",
    maintenance: "Maintenance manuals",
    quality_control: "Quality control",
    unrouted: "No match",
  };

  const WELCOME =
    "Hi — ask me about <strong>safety procedures</strong>, <strong>equipment maintenance</strong>, " +
    "or <strong>quality-control standards</strong>. I'll route your question to the right " +
    "documentation and answer with citations and a confidence score.";

  // --- Theme ---
  const themeBtn = document.getElementById("theme-toggle");
  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function activeTheme() {
    return document.documentElement.getAttribute("data-theme") || systemTheme();
  }
  function updateThemeUI(t) {
    const icon = document.getElementById("theme-icon");
    const label = document.getElementById("theme-label");
    if (t === "dark") { icon.textContent = "☀️"; label.textContent = "Light mode"; }
    else { icon.textContent = "🌙"; label.textContent = "Dark mode"; }
  }
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("theme", t);
    updateThemeUI(t);
  }
  updateThemeUI(activeTheme());
  themeBtn.addEventListener("click", () => applyTheme(activeTheme() === "dark" ? "light" : "dark"));

  // --- Mobile sidebar toggle ---
  const menuBtn = document.getElementById("menu-btn");
  if (menuBtn) menuBtn.addEventListener("click", () => sidebarEl.classList.toggle("open"));

  // --- Safe minimal markdown ---
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
  function inline(text) { return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"); }
  function renderMarkdown(md) {
    const lines = escapeHtml(md).split("\n");
    let html = "", listType = null;
    const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };
    for (const raw of lines) {
      const line = raw.trim();
      const ol = line.match(/^\d+\.\s+(.*)$/);
      const ul = line.match(/^[-*]\s+(.*)$/);
      if (ol) { if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; } html += `<li>${inline(ol[1])}</li>`; }
      else if (ul) { if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; } html += `<li>${inline(ul[1])}</li>`; }
      else if (line === "") { closeList(); }
      else { closeList(); html += `<p>${inline(line)}</p>`; }
    }
    closeList();
    return html;
  }

  // --- DOM builders ---
  function showWelcome() {
    messagesEl.innerHTML = `<div class="msg assistant"><div class="bubble"><p>${WELCOME}</p></div></div>`;
    if (suggestionsEl) suggestionsEl.style.display = "flex";
  }

  function addUserMessage(text) {
    if (suggestionsEl) suggestionsEl.style.display = "none";
    const wrap = document.createElement("div");
    wrap.className = "msg user";
    wrap.innerHTML = `<div class="bubble"><p>${inline(escapeHtml(text))}</p></div>`;
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function addTyping() {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    wrap.innerHTML = '<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function badge(domain, confidence) {
    const dLabel = DOMAIN_LABELS[domain] || domain;
    const pct = Math.round((confidence.score || 0) * 100);
    const level = confidence.level || "low";
    return `<div class="answer-meta">
        <span class="badge domain-${domain}"><span class="badge-dot"></span>${dLabel}</span>
        <span class="badge confidence ${level}">Confidence: ${level} · ${pct}%</span>
      </div>`;
  }

  function citationsBlock(citations) {
    if (!citations || !citations.length) return "";
    const items = citations.map((c, i) => {
      const loc = [c.section, c.page ? `p. ${c.page}` : null].filter(Boolean).join(" · ");
      const title = escapeHtml(c.source_title || "Source");
      const link = c.url ? `<a href="${encodeURI(c.url)}" target="_blank" rel="noopener">${title}</a>` : title;
      const snip = c.snippet ? `<span class="citation-snip">“${escapeHtml(c.snippet)}”</span>` : "";
      return `<div class="citation"><span class="citation-num">${i + 1}</span>
          <span class="citation-body">${link}
            ${loc ? `<span class="citation-loc"> — ${escapeHtml(loc)}</span>` : ""}${snip}
          </span></div>`;
    }).join("");
    return `<div class="citations"><div class="citations-title">Sources</div>${items}</div>`;
  }

  // Render an assistant message. `feedbackState` is "up"|"down"|null (from history).
  function addAssistantMessage(messageId, data, feedbackState) {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const showMeta = data.domain && data.domain !== "unrouted";
    bubble.innerHTML =
      (showMeta ? badge(data.domain, data.confidence || {}) : "") +
      renderMarkdown(data.answer || "") +
      citationsBlock(data.citations) +
      feedbackHtml(messageId);
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    wireFeedback(bubble, feedbackState);
    scrollToBottom();
  }

  function feedbackHtml(messageId) {
    return `<div class="feedback" data-msg-id="${messageId}">
        <span class="feedback-label">Was this helpful?</span>
        <button class="fb-btn fb-up" aria-label="Helpful">👍</button>
        <button class="fb-btn fb-down" aria-label="Not helpful">👎</button>
      </div>`;
  }

  function wireFeedback(bubble, existing) {
    const fb = bubble.querySelector(".feedback");
    if (!fb) return;
    const up = fb.querySelector(".fb-up");
    const down = fb.querySelector(".fb-down");

    const markDone = (rating) => {
      (rating === "up" ? up : down).classList.add(rating === "up" ? "active-up" : "active-down");
      if (!fb.querySelector(".fb-thanks")) {
        const t = document.createElement("span");
        t.className = "fb-thanks";
        t.textContent = "Thanks for the feedback";
        fb.appendChild(t);
      }
      fb.classList.add("done"); // gray out + non-interactive
    };

    if (existing) { markDone(existing); return; } // already rated (from history)

    const send = async (rating) => {
      try {
        const res = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message_id: Number(fb.dataset.msgId), rating }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        markDone(rating);
      } catch (e) { console.error("feedback failed", e); }
    };
    up.addEventListener("click", () => send("up"));
    down.addEventListener("click", () => send("down"));
  }

  function scrollToBottom() {
    const main = document.querySelector(".chat-main");
    main.scrollTop = main.scrollHeight;
  }

  // --- Sessions ---
  async function loadSessions() {
    try {
      const res = await fetch("/api/sessions");
      if (!res.ok) return;
      const sessions = await res.json();
      renderSessions(sessions);
    } catch (e) { console.error(e); }
  }

  function renderSessions(sessions) {
    sessionsEl.innerHTML = "";
    if (!sessions.length) {
      sessionsEl.innerHTML = '<div class="sessions-empty">No chats yet.</div>';
      return;
    }
    for (const s of sessions) {
      const btn = document.createElement("button");
      btn.className = "session-item" + (s.id === currentSessionId ? " active" : "");
      btn.textContent = s.title;
      btn.dataset.id = s.id;
      btn.addEventListener("click", () => openSession(s.id, s.title));
      sessionsEl.appendChild(btn);
    }
  }

  function setActiveSession(id, title) {
    currentSessionId = id;
    mainTitleEl.textContent = title || "New chat";
    for (const el of sessionsEl.querySelectorAll(".session-item")) {
      el.classList.toggle("active", Number(el.dataset.id) === id);
    }
  }

  async function openSession(id, title) {
    setActiveSession(id, title);
    sidebarEl.classList.remove("open");
    try {
      const res = await fetch(`/api/sessions/${id}/messages`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const msgs = await res.json();
      messagesEl.innerHTML = "";
      if (suggestionsEl) suggestionsEl.style.display = "none";
      for (const m of msgs) {
        if (m.role === "user") addUserMessage(m.content);
        else addAssistantMessage(m.id, { ...(m.meta || {}), answer: m.content }, m.feedback);
      }
    } catch (e) { console.error(e); }
  }

  function newChat() {
    currentSessionId = null;
    mainTitleEl.textContent = "New chat";
    for (const el of sessionsEl.querySelectorAll(".session-item")) el.classList.remove("active");
    showWelcome();
    inputEl.focus();
  }

  // --- Send flow ---
  async function sendMessage(text) {
    if (!text.trim()) return;
    addUserMessage(text);
    inputEl.value = "";
    autoGrow();
    sendEl.disabled = true;
    const typing = addTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: currentSessionId }),
      });
      typing.remove();
      if (res.status === 401) { window.location.href = "/login"; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();

      const isNew = currentSessionId === null;
      setActiveSession(result.session_id, result.session_title);
      addAssistantMessage(result.message_id, result, null);
      if (isNew) loadSessions(); // surface the new session in the sidebar
    } catch (e) {
      typing.remove();
      addAssistantMessage(-1,
        { answer: "Sorry — something went wrong reaching the assistant. Please try again.",
          domain: "unrouted", confidence: { level: "low", score: 0 }, citations: [] }, null);
      console.error(e);
    } finally {
      sendEl.disabled = false;
      inputEl.focus();
    }
  }

  // --- Input behaviors ---
  function autoGrow() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
  }
  inputEl.addEventListener("input", autoGrow);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(inputEl.value); }
  });
  formEl.addEventListener("submit", (e) => { e.preventDefault(); sendMessage(inputEl.value); });
  newChatEl.addEventListener("click", newChat);
  if (suggestionsEl) {
    suggestionsEl.querySelectorAll(".chip").forEach((chip) =>
      chip.addEventListener("click", () => sendMessage(chip.dataset.q)));
  }

  // --- Init ---
  showWelcome();
  loadSessions();
  inputEl.focus();
})();
