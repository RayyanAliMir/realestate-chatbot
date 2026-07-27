const apiBaseEl = document.getElementById("api-base");
const agentIdEl = document.getElementById("agent-id");
const dashboardKeyEl = document.getElementById("dashboard-key");
const loadBtn = document.getElementById("load-btn");
const statusEl = document.getElementById("status");
const leadsTbody = document.getElementById("leads-tbody");
const conversationListEl = document.getElementById("conversation-list");
const conversationLogEl = document.getElementById("conversation-log");

apiBaseEl.value = localStorage.getItem("dashboard-api-base") || apiBaseEl.value;
agentIdEl.value = localStorage.getItem("dashboard-agent-id") || "";
dashboardKeyEl.value = localStorage.getItem("dashboard-key") || "";

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.className = isError ? "status error" : "status";
}

function formatTimestamp(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString();
}

function renderLeads(leads) {
  leadsTbody.innerHTML = "";

  if (!leads.length) {
    leadsTbody.innerHTML = `<tr><td class="empty-cell" colspan="4">No leads yet.</td></tr>`;
    return;
  }

  for (const lead of leads) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${lead.name || "—"}</td>
      <td>${lead.contact || "—"}</td>
      <td>${lead.question || "—"}</td>
      <td>${formatTimestamp(lead.created_at)}</td>
    `;
    leadsTbody.appendChild(tr);
  }
}

function renderConversationList(conversations) {
  conversationListEl.innerHTML = "";
  const ids = Object.keys(conversations);

  if (!ids.length) {
    conversationListEl.innerHTML = `<div class="empty-state">No conversations yet.</div>`;
    return;
  }

  ids.forEach((id, index) => {
    const item = document.createElement("div");
    item.className = "conversation-item";
    item.textContent = id;
    item.addEventListener("click", () => {
      document.querySelectorAll(".conversation-item").forEach((el) => el.classList.remove("active"));
      item.classList.add("active");
      renderConversationLog(conversations[id]);
    });
    conversationListEl.appendChild(item);

    if (index === 0) {
      item.classList.add("active");
      renderConversationLog(conversations[id]);
    }
  });
}

function renderConversationLog(messages) {
  conversationLogEl.innerHTML = "";

  if (!messages || !messages.length) {
    conversationLogEl.innerHTML = `<div class="empty-state">No messages in this conversation.</div>`;
    return;
  }

  for (const msg of messages) {
    const div = document.createElement("div");
    div.className = `msg ${msg.role}`;
    div.innerHTML = `<span class="role-label">${msg.role}</span>${msg.content}`;
    conversationLogEl.appendChild(div);
  }
}

async function loadDashboard() {
  const apiBase = apiBaseEl.value.trim().replace(/\/$/, "");
  const agentId = agentIdEl.value.trim();
  const dashboardKey = dashboardKeyEl.value.trim();

  if (!apiBase || !agentId || !dashboardKey) {
    setStatus("Enter an API base, agent ID, and dashboard key.", true);
    return;
  }

  localStorage.setItem("dashboard-api-base", apiBase);
  localStorage.setItem("dashboard-agent-id", agentId);
  localStorage.setItem("dashboard-key", dashboardKey);

  setStatus("Loading...");

  try {
    const headers = { "X-Dashboard-Key": dashboardKey };
    const [leadsRes, conversationsRes] = await Promise.all([
      fetch(`${apiBase}/agents/${agentId}/leads`, { headers }),
      fetch(`${apiBase}/agents/${agentId}/conversations`, { headers }),
    ]);

    if (leadsRes.status === 401 || conversationsRes.status === 401) {
      throw new Error("Invalid dashboard key.");
    }
    if (!leadsRes.ok) throw new Error(`Leads request failed (${leadsRes.status})`);
    if (!conversationsRes.ok) throw new Error(`Conversations request failed (${conversationsRes.status})`);

    const leads = await leadsRes.json();
    const conversations = await conversationsRes.json();

    renderLeads(leads);
    renderConversationList(conversations);
    setStatus(`Loaded ${leads.length} lead(s) and ${Object.keys(conversations).length} conversation(s).`);
  } catch (err) {
    setStatus(err.message || "Failed to load dashboard data.", true);
  }
}

loadBtn.addEventListener("click", loadDashboard);
for (const el of [agentIdEl, dashboardKeyEl]) {
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadDashboard();
  });
}

if (agentIdEl.value && dashboardKeyEl.value) loadDashboard();
