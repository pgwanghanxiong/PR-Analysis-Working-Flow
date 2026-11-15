const PAGE_ACCESS_TOKEN_KEY = "questionnaireAccessToken";
const PAGE_ACCESS_MESSAGE_KEY = "questionnaireAccessMessage";

async function requirePageSession() {
  const token = sessionStorage.getItem(PAGE_ACCESS_TOKEN_KEY);
  if (!token) {
    window.location.replace("/login");
    return null;
  }

  try {
    const response = await fetch("/api/access/session", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Access session expired.");
    const count = document.querySelector("#use-count");
    if (count) count.textContent = payload.total_uses;
    const usage = document.querySelector("#usage-count");
    if (usage) usage.setAttribute("aria-label", `Total uses ${payload.total_uses}`);
    const shell = document.querySelector("#app-shell");
    if (shell) shell.inert = false;
    return token;
  } catch (error) {
    sessionStorage.setItem(PAGE_ACCESS_MESSAGE_KEY, error.message);
    sessionStorage.removeItem(PAGE_ACCESS_TOKEN_KEY);
    window.location.replace("/login");
    return null;
  }
}