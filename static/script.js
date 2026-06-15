(function () {
  "use strict";

  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const messages = document.getElementById("messages");
  const button = form.querySelector("button");

  function appendMessage(text, sender, source) {
    const el = document.createElement("div");
    el.className = "message " + sender;
    el.textContent = text;
    if (source) {
      const meta = document.createElement("span");
      meta.className = "source";
      meta.textContent = "Source: " + source;
      el.appendChild(meta);
    }
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  async function sendMessage(message) {
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message }),
      });
      const data = await response.json();
      if (!response.ok) {
        appendMessage(data.error || "Something went wrong.", "bot");
        return;
      }
      appendMessage(data.reply, "bot", data.found ? data.source : "");
    } catch (err) {
      appendMessage("Network error. Please try again.", "bot");
    }
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) {
      return;
    }
    appendMessage(message, "user");
    input.value = "";
    input.focus();
    button.disabled = true;
    await sendMessage(message);
    button.disabled = false;
  });
})();
