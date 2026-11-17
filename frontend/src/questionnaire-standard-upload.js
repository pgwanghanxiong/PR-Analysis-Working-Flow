const standardUploadForm = document.querySelector("#questionnaire-standard-upload-form");
const standardFileInput = document.querySelector("#questionnaire-standard-file");
const standardFileName = document.querySelector("#questionnaire-standard-file-name");
const standardUploadButton = document.querySelector("#questionnaire-standard-upload-button");
const standardUploadStatus = document.querySelector("#questionnaire-standard-upload-status");
const standardUploadSession = requirePageSession();

standardFileInput.addEventListener("change", () => {
  const file = standardFileInput.files[0];
  standardFileName.textContent = file?.name || "Choose CSV file";
  standardUploadButton.disabled = !file;
  standardUploadStatus.classList.remove("error");
  standardUploadStatus.textContent = file
    ? `${file.name} selected. File structure will be checked before saving.`
    : "Select a CSV file matching the questionnaire template.";
});

standardUploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!standardFileInput.files.length) return;

  const token = await standardUploadSession;
  if (!token) return;
  standardUploadButton.disabled = true;
  standardUploadStatus.classList.remove("error");
  standardUploadStatus.textContent = "Validating questionnaire template and uploading...";

  try {
    const response = await fetch("/api/questionnaire-build/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: new FormData(standardUploadForm),
    });
    const body = await response.json();
    if (response.status === 401) {
      sessionStorage.removeItem("questionnaireAccessToken");
      window.location.replace("/login");
      return;
    }
    if (!response.ok) throw new Error(body.detail || "The questionnaire standard upload failed.");
    standardUploadStatus.textContent = body.message || "Questionnaire template uploaded successfully.";
  } catch (error) {
    standardUploadStatus.textContent = error.message;
    standardUploadStatus.classList.add("error");
  } finally {
    standardUploadButton.disabled = !standardFileInput.files.length;
  }
});