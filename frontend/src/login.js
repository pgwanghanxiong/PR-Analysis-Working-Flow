const ACCESS_TOKEN_KEY = "questionnaireAccessToken";
const ACCESS_MESSAGE_KEY = "questionnaireAccessMessage";
const accessForm = document.querySelector("#access-form");
const accessStatus = document.querySelector("#access-status");
const accessSubmit = document.querySelector("#access-submit");

const savedMessage = sessionStorage.getItem(ACCESS_MESSAGE_KEY);
if (savedMessage) {
  accessStatus.textContent = savedMessage;
  accessStatus.classList.add("error");
  sessionStorage.removeItem(ACCESS_MESSAGE_KEY);
}

refreshUsageCount();

async function refreshUsageCount() {
  try {
    const response = await fetch("/api/usage/count");
    if (!response.ok) return;
    const payload = await response.json();
    document.querySelector("#gate-use-count").textContent = payload.total_uses;
  } catch {
    return;
  }
}

accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  accessSubmit.disabled = true;
  accessStatus.classList.remove("error");
  accessStatus.textContent = "Confirming access...";

  try {
    const response = await fetch("/api/access/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.querySelector("#access-email").value,
        business_unit: document.querySelector("#access-bu").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Unable to confirm access.");
    sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.session_token);
    window.location.assign("/workspace");
  } catch (error) {
    accessStatus.textContent = error.message;
    accessStatus.classList.add("error");
  } finally {
    accessSubmit.disabled = false;
  }
});