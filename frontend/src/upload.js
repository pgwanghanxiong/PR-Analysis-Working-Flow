const uploadForm = document.querySelector("#upload-form");
const uploadButton = document.querySelector("#upload-button");
const fileInput = document.querySelector("#csv-file");
const fileName = document.querySelector("#file-name");
const studyNameInput = document.querySelector("#upload-study-name");
const uploadStatus = document.querySelector("#upload-status");
const accessTokenPromise = requirePageSession();

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "Choose CSV file";
  updateUploadStatus();
  uploadButton.disabled = !fileInput.files.length;
});

studyNameInput.addEventListener("input", updateUploadStatus);

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;

  const accessToken = await accessTokenPromise;
  if (!accessToken) return;
  uploadButton.disabled = true;
  uploadStatus.classList.remove("error");
  uploadStatus.textContent = "Validating format and saving rows to PostgreSQL...";

  try {
    const response = await fetch("/api/uploads", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: new FormData(uploadForm),
    });
    const body = await response.json();
    if (response.status === 401) {
      window.location.replace("/login");
      return;
    }
    if (!response.ok) throw new Error(body.detail || "The PostgreSQL upload failed.");
    uploadStatus.textContent = body.message;
  } catch (error) {
    uploadStatus.textContent = error.message;
    uploadStatus.classList.add("error");
  } finally {
    uploadButton.disabled = !fileInput.files.length;
  }
});

function updateUploadStatus() {
  const selectedFile = fileInput.files[0];
  if (selectedFile && studyNameInput.value.trim()) {
    uploadStatus.textContent = `${selectedFile.name} selected. Wide format will be saved as "${studyNameInput.value.trim()}".`;
  } else if (selectedFile) {
    uploadStatus.textContent = `${selectedFile.name} selected. Enter a Study Name if this is Wide format.`;
  } else {
    uploadStatus.textContent = "Select a CSV and provide its Study Name.";
  }
}