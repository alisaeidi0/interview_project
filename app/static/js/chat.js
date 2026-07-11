// Floor Assistant — chat UI logic. Vanilla JS, no build step.
(() => {
  "use strict";

  const messagesEl = document.getElementById("messages");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("input");
  const sendEl = document.getElementById("send");
  const suggestionsEl = document.getElementById("suggestions");

  let messageCounter = 0;

  const DOMAIN_LABELS = {
    safety: "Safety procedures",
    maintenance: "Maintenance manuals",
    quality_control: "Quality control",
    unrouted: "No match",
  };

  // --- Minimal, safe markdown: escape first, then apply a tiny subset. ---
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function renderMarkdown(md) {
    const lines = escapeHtml(md).split("\n");
    let html = "";
    let listType = null; // 'ol' | 'ul' | null

    const closeList = () => {
      if (listType) { html += `</${listType}>`; listType = null; }
    };

    for (let raw of lines) {
      const line = raw.trim();
      const ol = line.match(/^\d+\.\s+(.*)$/);
      const ul = line.match(/^[-*]\s+(.*)$/);
      if (ol) {
        if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; }
        html += `<li>${inline(ol[1])}</li>`;
      } else if (ul) {
        if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
        html += `<li>${inline(ul[1])}</li>`;
      } else if (line === "") {
        closeList();
      } else {
        closeList();
        html += `<p>${inline(line)}</p>`;
      }
    }
    closeList();
    return html;
  }

  function inline(text) {
    return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  // --- DOM builders ---
  function addUserMessage(text) {
    const wrap = document.createElement("div");
    wrap.className = "msg user";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = `<p>${inline(escapeHtml(text))}</p>`;
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function addTyping() {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    wrap.dataset.typing = "1";
    wrap.innerHTML =
      '<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function badge(domain, confidence) {
    const dLabel = DOMAIN_LABELS[domain] || domain;
    const pct = Math.round((confidence.score || 0) * 100);
    const cLevel = confidence.level || "low";
    return `
      <div class="answer-meta">
        <span class="badge domain-${domain}"><span class="badge-dot"></span>${dLabel}</span>
        <span class="badge confidence ${cLevel}">Confidence: ${cLevel} · ${pct}%</span>
      </div>`;
  }

  function citationsBlock(citations) {
    if (!citations || citations.length === 0) return "";
    const items = citations
      .map((c, i) => {
        const loc = [c.section, c.page ? `p. ${c.page}` : null]
          .filter(Boolean)
          .join(" · ");
        const title = escapeHtml(c.source_title || "Source");
        const link = c.url
          ? `<a href="${encodeURI(c.url)}" target="_blank" rel="noopener">${title}</a>`
          : title;
        const snip = c.snippet
          ? `<span class="citation-snip">“${escapeHtml(c.snippet)}”</span>`
          : "";
        return `
          <div class="citation">
            <span class="citation-num">${i + 1}</span>
            <span class="citation-body">${link}
              ${loc ? `<span class="citation-loc"> — ${escapeHtml(loc)}</span>` : ""}
              ${snip}
            </span>
          </div>`;
      })
      .join("");
    return `<div class="citations"><div class="citations-title">Sources</div>${items}</div>`;
  }

  function feedbackBlock(messageId, question) {
    return `
      <div class="feedback" data-msg-id="${messageId}" data-question="${escapeHtml(question)}">
        <span class="feedback-label">Was this helpful?</span>
        <button class="fb-btn fb-up" aria-label="Helpful">👍</button>
        <button class="fb-btn fb-down" aria-label="Not helpful">👎</button>
      </div>`;
  }

  function addAssistantMessage(result, question) {
    const id = `m${++messageCounter}`;
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const showMeta = result.domain && result.domain !== "unrouted";
    bubble.innerHTML =
      (showMeta ? badge(result.domain, result.confidence || {}) : "") +
      renderMarkdown(result.answer || "") +
      citationsBlock(result.citations) +
      feedbackBlock(id, question);
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    wireFeedback(bubble);
    scrollToBottom();
  }

  function wireFeedback(bubble) {
    const fb = bubble.querySelector(".feedback");
    if (!fb) return;
    const up = fb.querySelector(".fb-up");
    const down = fb.querySelector(".fb-down");

    const send = async (rating, btn, other) => {
      btn.classList.add(rating === "up" ? "active-up" : "active-down");
      other.classList.remove("active-up", "active-down");
      try {
        await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_id: fb.dataset.msgId,
            rating,
            question: fb.dataset.question || "",
          }),
        });
        if (!fb.querySelector(".fb-thanks")) {
          const t = document.createElement("span");
          t.className = "fb-thanks";
          t.textContent = "Thanks for the feedback";
          fb.appendChild(t);
        }
      } catch (e) {
        console.error("feedback failed", e);
      }
    };

    up.addEventListener("click", () => send("up", up, down));
    down.addEventListener("click", () => send("down", down, up));
  }

  function scrollToBottom() {
    const main = document.querySelector(".chat-main");
    main.scrollTop = main.scrollHeight;
  }

  // --- Send flow ---
  async function sendMessage(text) {
    if (!text.trim()) return;
    if (suggestionsEl) suggestionsEl.style.display = "none";
    addUserMessage(text);
    inputEl.value = "";
    autoGrow();
    sendEl.disabled = true;
    const typing = addTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      typing.remove();
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();
      addAssistantMessage(result, text);
    } catch (e) {
      typing.remove();
      addAssistantMessage(
        { answer: "Sorry — something went wrong reaching the assistant. Please try again.",
          domain: "unrouted", confidence: { level: "low", score: 0 }, citations: [] },
        text
      );
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
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputEl.value);
    }
  });

  formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(inputEl.value);
  });

  if (suggestionsEl) {
    suggestionsEl.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => sendMessage(chip.dataset.q));
    });
  }

  inputEl.focus();
})();
