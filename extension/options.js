"use strict";

const SERVERS = {
  dev:        "http://localhost:8001/v1",
  production: "https://api.tovbase.com/v1",
};

const radioOptions = document.querySelectorAll(".radio-option");
const customField = document.getElementById("custom-field");
const customUrl = document.getElementById("custom-url");
const saveBtn = document.getElementById("save-btn");
const savedMsg = document.getElementById("saved-msg");

function setActive(value) {
  radioOptions.forEach((opt) => {
    const radio = opt.querySelector("input[type=radio]");
    if (radio.value === value) {
      opt.classList.add("active");
      radio.checked = true;
    } else {
      opt.classList.remove("active");
      radio.checked = false;
    }
  });
  customField.style.display = value === "custom" ? "block" : "none";
}

// Click handler for radio options
radioOptions.forEach((opt) => {
  opt.addEventListener("click", () => {
    const value = opt.dataset.value;
    setActive(value);
  });
});

// Load saved settings
chrome.storage.sync.get(["tg_server", "tg_custom_url"], (result) => {
  const server = result.tg_server || "dev";
  setActive(server);
  if (result.tg_custom_url) {
    customUrl.value = result.tg_custom_url;
  }
});

// Save
saveBtn.addEventListener("click", () => {
  const selected = document.querySelector('input[name="server"]:checked');
  if (!selected) return;

  const server = selected.value;
  const data = { tg_server: server };

  if (server === "custom") {
    const url = customUrl.value.trim().replace(/\/+$/, "");
    if (!url) {
      customUrl.style.borderColor = "#ef4444";
      return;
    }
    data.tg_custom_url = url;
  }

  chrome.storage.sync.set(data, () => {
    savedMsg.classList.add("show");
    setTimeout(() => savedMsg.classList.remove("show"), 2000);
  });
});
