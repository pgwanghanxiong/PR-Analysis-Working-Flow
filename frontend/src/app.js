const ACCESS_TOKEN_KEY = "questionnaireAccessToken";
const ACCESS_MESSAGE_KEY = "questionnaireAccessMessage";
const appShell = document.querySelector("#app-shell");
const uploadForm = document.querySelector("#upload-form");
const uploadButton = document.querySelector("#upload-button");
const analysisForm = document.querySelector("#analysis-form");
const fileInput = document.querySelector("#csv-file");
const fileName = document.querySelector("#file-name");
const uploadStatus = document.querySelector("#upload-status");
const studySelect = document.querySelector("#existing-study");
const uploadStudyName = document.querySelector("#upload-study-name");
const studiesStatus = document.querySelector("#studies-status");
const refreshStudiesButton = document.querySelector("#refresh-studies");
const runButton = document.querySelector("#run-button");
const statusMessage = document.querySelector("#status");
const results = document.querySelector("#results");
let accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

async function restoreAccess() {
  if (!accessToken) {
    redirectToLogin();
    return;
  }

  try {
    const response = await fetch("/api/access/session", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Access session expired. Please confirm your details again.");
    }
    updateUsageCount(payload.total_uses);
    appShell.inert = false;
    void loadStudies();
  } catch (error) {
    redirectToLogin(error.message);
  }
}

function updateUsageCount(totalUses) {
  document.querySelector("#use-count").textContent = totalUses;
  document.querySelector("#usage-count").setAttribute("aria-label", `Total uses ${totalUses}`);
}

function redirectToLogin(message = "") {
  if (message) sessionStorage.setItem(ACCESS_MESSAGE_KEY, message);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  window.location.replace("/login");
}

void restoreAccess();

fileInput.addEventListener("change", () => {
  const selectedFile = fileInput.files[0];
  fileName.textContent = selectedFile?.name || "Choose CSV file";
  uploadStatus.classList.remove("error");
  updateUploadStatus();
  uploadButton.disabled = !selectedFile;
});

studySelect.addEventListener("change", () => {
  updateRunButton();
});

uploadStudyName.addEventListener("input", () => {
  updateUploadStatus();
});

refreshStudiesButton.addEventListener("click", () => {
  void loadStudies();
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) return;

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
      redirectToLogin(body.detail || "Confirm your email and business unit to continue.");
      return;
    }
    if (!response.ok) throw new Error(body.detail || "The PostgreSQL upload failed.");
    uploadStatus.textContent = body.message;
    uploadStatus.classList.remove("error");
    await loadStudies(body.study_names.length === 1 ? body.study_names[0] : "");
  } catch (error) {
    uploadStatus.textContent = error.message;
    uploadStatus.classList.add("error");
  } finally {
    uploadButton.disabled = !fileInput.files.length;
  }
});

analysisForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const studyName = studySelect.value.trim();
  if (!studyName) return;

  runButton.disabled = true;
  statusMessage.classList.remove("error");
  statusMessage.textContent = `Loading "${studyName}" from PostgreSQL and calculating product comparisons...`;
  results.hidden = true;

  try {
    const formData = new FormData();
    formData.set("study_name", studyName);
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData,
    });
    const body = await response.json();
    if (response.status === 401) {
      redirectToLogin(body.detail || "Confirm your email and business unit to continue.");
      return;
    }
    if (!response.ok) throw new Error(body.detail || "The analysis request failed.");
    renderReport(body.report, body.validation, body.artifacts);
    statusMessage.textContent = `Analysis complete · ${body.validation.input_rows} input rows · ${body.validation.analysis_rows} pairwise tests`;
    results.hidden = false;
  } catch (error) {
    statusMessage.textContent = error.message;
    statusMessage.classList.add("error");
  } finally {
    updateRunButton();
  }
});

async function loadStudies(preferredStudyName = "") {
  refreshStudiesButton.disabled = true;
  studiesStatus.classList.remove("error");
  studiesStatus.textContent = "Loading existing Study Names...";
  studySelect.replaceChildren(option("Loading Study Names...", ""));
  studySelect.disabled = true;

  try {
    const response = await fetch("/api/studies", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const payload = await response.json();
    if (response.status === 401) {
      redirectToLogin(payload.detail || "Confirm your email and business unit to continue.");
      return;
    }
    if (!response.ok) throw new Error(payload.detail || "Could not load Study Names.");

    studySelect.replaceChildren(option("Select an uploaded Study Name", ""));
    for (const studyName of payload.study_names) {
      studySelect.append(option(studyName, studyName));
    }
    studySelect.disabled = payload.study_names.length === 0;
    if (preferredStudyName && payload.study_names.includes(preferredStudyName)) {
      studySelect.value = preferredStudyName;
    }
    studiesStatus.textContent = payload.message;
  } catch (error) {
    studySelect.replaceChildren(option("Existing Study Names unavailable", ""));
    studySelect.disabled = true;
    studiesStatus.textContent = error.message;
    studiesStatus.classList.add("error");
  } finally {
    refreshStudiesButton.disabled = false;
    updateRunButton();
  }
}

function option(label, value) {
  const element = document.createElement("option");
  element.textContent = label;
  element.value = value;
  return element;
}

function updateRunButton() {
  runButton.disabled = !studySelect.value.trim();
}

function updateUploadStatus() {
  const selectedFile = fileInput.files[0];
  if (selectedFile && uploadStudyName.value.trim()) {
    uploadStatus.textContent = `${selectedFile.name} selected. Wide format will be saved as "${uploadStudyName.value.trim()}".`;
  } else if (selectedFile) {
    uploadStatus.textContent = `${selectedFile.name} selected. Enter a Study Name if this is Wide format.`;
  } else {
    uploadStatus.textContent = "Select a CSV and provide its Study Name.";
  }
}

function renderReport(report, validation, artifacts) {
  const table = document.querySelector("#report-table");
  const columnGroup = table.querySelector("colgroup");
  const head = table.querySelector("thead");
  const body = table.querySelector("tbody");
  const productCount = report.products.length;
  columnGroup.replaceChildren();
  head.replaceChildren();
  body.replaceChildren();

  columnGroup.append(column("question-column"), column("time-column"));
  for (let index = 0; index < productCount; index += 1) {
    columnGroup.append(column("product-column"));
  }
  table.style.minWidth = `${300 + 95 + productCount * 125}px`;

  const firstRow = document.createElement("tr");
  firstRow.append(cell("th", ""), cell("th", ""));
  for (const product of report.products) {
    firstRow.append(cell("th", product.name, "product-head"));
  }
  head.append(firstRow);

  const secondRow = document.createElement("tr");
  secondRow.append(cell("th", ""), cell("th", ""));
  for (const product of report.products) {
    secondRow.append(cell("th", product.abbreviation));
  }
  head.append(secondRow);

  const labelsRow = document.createElement("tr");
  labelsRow.append(cell("th", "DQ Question"), cell("th", "Time Point"));
  for (const product of report.products) {
    labelsRow.append(cell("th", `N = ${product.sample_size}`));
  }
  head.append(labelsRow);

  for (const row of report.rows) {
    const tableRow = document.createElement("tr");
    tableRow.append(cell("td", row.question, "question-value"), cell("td", row.day, "time-value"));
    for (const productValue of row.product_values) {
      tableRow.append(cell("td", productValue.display || "", "product-value"));
    }
    body.append(tableRow);
  }

  document.querySelector("#database-status").textContent = validation.database.message;
  document.querySelector("#database-status").classList.toggle("loaded", validation.database.status === "loaded");
  document.querySelector("#download-report").href = artifacts.business_report;
  document.querySelector("#download-database").href = artifacts.database_ingestion;
  document.querySelector("#download-log").href = artifacts.validation_log;
  document.querySelector("#report-caption").textContent = `${report.rows.length} question/time rows · significance threshold p < 0.05 · markers list products with a significant pairwise difference`;
}

function column(className) {
  const element = document.createElement("col");
  element.className = className;
  return element;
}

function cell(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}