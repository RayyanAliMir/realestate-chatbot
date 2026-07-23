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

  // --- Styles ---
  const style = document.createElement("style");
  style.textContent = `
    #rec-widget-bubble {
      position: fixed; bottom: 20px; right: 20px; width: 56px; height: 56px;
      border-radius: 50%; background: #1a56db; color: white; display: flex;
      align-items: center; justify-content: center; cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 999999; font-size: 24px;
    }
    #rec-widget-panel {
      position: fixed; bottom: 90px; right: 20px; width: 340px; height: 460px;
      background: white; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.25);
      display: none; flex-direction: column; overflow: hidden; z-index: 999999;
      font-family: system-ui, sans-serif;
    }
    #rec-widget-header { background: #1a56db; color: white; padding: 12px 16px; font-weight: 600; }
    #rec-widget-messages { flex: 1; overflow-y: auto; padding: 12px; font-size: 14px; }
    .rec-msg { margin-bottom: 10px; line-height: 1.4; }
    .rec-msg.user { text-align: right; color: #1a56db; }
    .rec-msg.bot { text-align: left; color: #222; }
    #rec-widget-input-row { display: flex; border-top: 1px solid #eee; }
    #rec-widget-input { flex: 1; border: none; padding: 10px; font-size: 14px; }
    #rec-widget-send { border: none; background: #1a56db; color: white; padding: 0 16px; cursor: pointer; }
  `;
  document.head.appendChild(style);

  // --- DOM ---
  const bubble = document.createElement("div");
  bubble.id = "rec-widget-bubble";
  bubble.textContent = "💬";

  const panel = document.createElement("div");
  panel.id = "rec-widget-panel";
  panel.innerHTML = `
    <div id="rec-widget-header">Ask about our listings</div>
    <div id="rec-widget-messages"></div>
    <div id="rec-widget-input-row">
      <input id="rec-widget-input" type="text" placeholder="Type a question..." />
      <button id="rec-widget-send">Send</button>
    </div>
  `;

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  bubble.addEventListener("click", () => {
    panel.style.display = panel.style.display === "flex" ? "none" : "flex";
  });

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
