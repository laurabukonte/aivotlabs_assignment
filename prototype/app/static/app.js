/* ===================================================================
   Hammashoitola – Ajanvaraus  |  Client Application
   =================================================================== */

// ---------------------------------------------------------------------------
// Constants (injected by server via data attributes on <body>)
// ---------------------------------------------------------------------------
const SESSION_TIMEOUT = parseInt(document.body.dataset.sessionTimeout || "600", 10);
const SESSION_WARNING = parseInt(document.body.dataset.sessionWarning || "480", 10);

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let sessionId = null;
let lastActivityTime = Date.now();
let timeoutTimerId = null;

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $messages  = () => $("#messages");
const $input     = () => $("#userInput");
const $sendBtn   = () => $("#sendBtn");
const $state     = () => $("#stateBadge");
const $banner    = () => $("#timeoutBanner");

function escapeHtml(text) {
  const el = document.createElement("div");
  el.textContent = text;
  return el.innerHTML;
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------
function appendMsg(role, content) {
  const container = $messages();
  if (!container) return;
  const div = document.createElement("div");
  div.className = "msg " + role;
  const ts = new Date().toLocaleTimeString("fi-FI");
  div.innerHTML = escapeHtml(content) + `<span class="ts">${ts}</span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ---------------------------------------------------------------------------
// State & session
// ---------------------------------------------------------------------------
function updateState(state) {
  const badge = $state();
  if (!badge) return;
  badge.textContent = state;
  badge.className = "state-badge state-" + state;
}

function resetSession() {
  sessionId = null;
  updateState("greeting");
  if ($messages()) {
    $messages().innerHTML = `
    <div class="msg assistant">
      Hei! Tervetuloa hammashoitolaan. Kirjoita viesti aloittaaksesi ajanvarauksen.
      <span class="ts">Järjestelmä</span>
    </div>`;
  }
  hideBanner();
}

// ---------------------------------------------------------------------------
// Timeout handling
// ---------------------------------------------------------------------------
function resetActivityTimer() {
  lastActivityTime = Date.now();
  hideBanner();
  clearInterval(timeoutTimerId);
  timeoutTimerId = setInterval(checkTimeout, 5000);
}

function checkTimeout() {
  if (!sessionId) return;

  const elapsed = (Date.now() - lastActivityTime) / 1000;

  if (elapsed >= SESSION_TIMEOUT) {
    // Session expired
    showBanner("Istunto on vanhentunut. Aloita uusi keskustelu.", true);
    updateState("expired");
    $input().disabled = true;
    $sendBtn().disabled = true;
    clearInterval(timeoutTimerId);
    return;
  }

  if (elapsed >= SESSION_WARNING) {
    const remaining = Math.ceil(SESSION_TIMEOUT - elapsed);
    showBanner(`Istunto vanhenee ${remaining} sekunnin kuluttua. Kirjoita viesti jatkaaksesi.`, false);
  }
}

function showBanner(text, isExpired) {
  const banner = $banner();
  if (!banner) return;
  banner.textContent = text;
  banner.classList.add("visible");
  banner.classList.toggle("expired", isExpired);
}

function hideBanner() {
  const banner = $banner();
  if (!banner) return;
  banner.classList.remove("visible", "expired");
  if ($input()) {
    $input().disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
async function sendMessage() {
  const input = $input();
  const text = input.value.trim();
  if (!text) return;

  // Check if session expired
  if ($state().textContent === "expired") {
    resetSession();
  }

  input.value = "";
  appendMsg("user", text);
  $sendBtn().disabled = true;
  resetActivityTimer();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`Palvelin palautti ${res.status}: ${errBody}`);
    }

    const data = await res.json();

    sessionId = data.session_id;
    updateState(data.state);
    appendMsg("assistant", data.response);
  } catch (err) {
    appendMsg("tool", "Virhe: " + err.message);
  } finally {
    $sendBtn().disabled = false;
    input.focus();
  }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const input = $input();
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMessage();
    });
  }

  const sendBtn = $sendBtn();
  if (sendBtn) {
    sendBtn.addEventListener("click", sendMessage);
  }
  resetActivityTimer();
});
