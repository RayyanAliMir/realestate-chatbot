/**
 * Embeddable real estate chatbot widget.
 * Usage: drop this script on an agent's site and set the API base + widget key:
 *
 *   <script src="widget.js"
 *           data-api-base="https://your-backend.example.com"
 *           data-widget-key="AGENT_WIDGET_KEY"></script>
 */
(function () {
  const scriptTag = document.currentScript;
  const API_BASE = scriptTag.getAttribute("data-api-base");
  const WIDGET_KEY = scriptTag.getAttribute("data-widget-key");

  let conversationId = null;
  let isOpen = false;

  const CHAT_ICON = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-4.2 3.5a.6.6 0 0 1-1-.46V17H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"
            stroke="white" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
  const CLOSE_ICON = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M6 6l12 12M18 6 6 18" stroke="white" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
  const SEND_ICON = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 12 20 4l-6.5 16-2.7-7.3L4 12Z" stroke="white" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;

  // --- Styles ---
  const style = document.createElement("style");
  style.textContent = `
    #rec-widget-bubble {
      position: fixed; bottom: 24px; right: 24px; width: 58px; height: 58px;
      border-radius: 50%; background: #1a56db; color: white; display: flex;
      align-items: center; justify-content: center; cursor: pointer; border: none;
      box-shadow: 0 6px 20px rgba(26,86,219,0.35); z-index: 999999;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    #rec-widget-bubble:hover { transform: scale(1.06); box-shadow: 0 8px 24px rgba(26,86,219,0.45); }
    #rec-widget-panel {
      position: fixed; bottom: 96px; right: 24px; width: 350px; height: 480px;
      background: white; border-radius: 16px; box-shadow: 0 12px 40px rgba(0,0,0,0.18);
      display: flex; flex-direction: column; overflow: hidden; z-index: 999999;
      font-family: system-ui, -apple-system, sans-serif;
      opacity: 0; transform: translateY(12px) scale(0.98); pointer-events: none;
      transition: opacity 0.18s ease, transform 0.18s ease;
    }
    #rec-widget-panel.rec-open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
    #rec-widget-header {
      background: #1a56db; color: white; padding: 16px 18px; font-weight: 600; font-size: 15px;
      flex-shrink: 0;
    }
    #rec-widget-messages {
      flex: 1; overflow-y: auto; padding: 16px; background: #fafbfc;
      display: flex; flex-direction: column; gap: 10px;
    }
    .rec-msg {
      max-width: 78%; padding: 10px 14px; border-radius: 16px; line-height: 1.45;
      font-size: 14px; word-wrap: break-word; white-space: pre-wrap;
    }
    .rec-msg.user {
      align-self: flex-end; background: #1a56db; color: white; border-bottom-right-radius: 4px;
    }
    .rec-msg.bot {
      align-self: flex-start; background: white; color: #222;
      border: 1px solid #e8eaed; border-bottom-left-radius: 4px;
    }
    #rec-widget-input-row {
      display: flex; align-items: center; gap: 8px; padding: 10px;
      border-top: 1px solid #eee; background: white; flex-shrink: 0;
    }
    #rec-widget-input {
      flex: 1; border: 1px solid #ddd; border-radius: 20px; padding: 9px 14px;
      font-size: 14px; outline: none; font-family: inherit;
      transition: border-color 0.15s ease;
    }
    #rec-widget-input:focus { border-color: #1a56db; }
    #rec-widget-send {
      border: none; background: #1a56db; color: white; width: 36px; height: 36px;
      border-radius: 50%; cursor: pointer; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; transition: background 0.15s ease;
    }
    #rec-widget-send:hover { background: #1443ad; }
  `;
  document.head.appendChild(style);

  // --- DOM ---
  const bubble = document.createElement("button");
  bubble.id = "rec-widget-bubble";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.innerHTML = CHAT_ICON;

  const panel = document.createElement("div");
  panel.id = "rec-widget-panel";
  panel.innerHTML = `
    <div id="rec-widget-header">Ask about our listings</div>
    <div id="rec-widget-messages"></div>
    <div id="rec-widget-input-row">
      <input id="rec-widget-input" type="text" placeholder="Type a question..." />
      <button id="rec-widget-send" aria-label="Send">${SEND_ICON}</button>
    </div>
  `;

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  function setOpen(open) {
    isOpen = open;
    panel.classList.toggle("rec-open", open);
    bubble.innerHTML = open ? CLOSE_ICON : CHAT_ICON;
    bubble.setAttribute("aria-label", open ? "Close chat" : "Open chat");
  }

  bubble.addEventListener("click", () => setOpen(!isOpen));

  const messagesEl = panel.querySelector("#rec-widget-messages");
  const inputEl = panel.querySelector("#rec-widget-input");
  const sendBtn = panel.querySelector("#rec-widget-send");

  function addMessage(text, sender) {
    const div = document.createElement("div");
    div.className = `rec-msg ${sender}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;
    addMessage(text, "user");
    inputEl.value = "";

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          widget_key: WIDGET_KEY,
          conversation_id: conversationId,
          message: text,
        }),
      });
      const data = await res.json();
      conversationId = data.conversation_id;
      addMessage(data.reply, "bot");
    } catch (err) {
      addMessage("Sorry, something went wrong. Please try again.", "bot");
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  addMessage("Hi! Ask me anything about our current listings.", "bot");
})();
