const ACCESS_TOKEN_KEY = "questionnaireAccessToken";
const ACCESS_MESSAGE_KEY = "questionnaireAccessMessage";
const appShell = document.querySelector("#app-shell");
const form = document.querySelector("#analysis-form");
const fileInput = document.querySelector("#csv-file");
const fileName = document.querySelector("#file-name");
const uploadStatus = document.querySelector("#upload-status");
const studySelect = document.querySelector("#existing-study");
const manualStudy = document.querySelector("#study-name");
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
  fileName.textContent = selectedFile?.name || "Choose raw CSV";
  uploadStatus.textContent = selectedFile ? `${selectedFile.name} selected.` : "Select a CSV that follows the raw input template.";
  uploadStatus.classList.remove("error");
  updateRunButton();
});

studySelect.addEventListener("change", () => {
  if (studySelect.value) manualStudy.value = "";
  updateRunButton();
});

manualStudy.addEventListener("input", () => {
  if (manualStudy.value.trim()) studySelect.value = "";
  updateRunButton();
});

refreshStudiesButton.addEventListener("click", () => {
  void loadStudies();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const studyName = (studySelect.value || manualStudy.value).trim();
  if (!fileInput.files.length || !studyName) return;

  runButton.disabled = true;
  statusMessage.classList.remove("error");
  statusMessage.textContent = "Validating schema and calculating product comparisons...";
  results.hidden = true;

  try {
    const formData = new FormData(form);
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

async function loadStudies() {
  refreshStudiesButton.disabled = true;
  studiesStatus.classList.remove("error");
  studiesStatus.textContent = "Loading Study Names from the database...";
  studySelect.replaceChildren(option("Loading studies...", ""));
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

    studySelect.replaceChildren(option("Select an existing Study Name", ""));
    for (const studyName of payload.study_names) {
      studySelect.append(option(studyName, studyName));
    }
    studySelect.disabled = payload.study_names.length === 0;
    studiesStatus.textContent = payload.message;
  } catch (error) {
    studySelect.replaceChildren(option("Database Study Names unavailable", ""));
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
  runButton.disabled = !fileInput.files.length || !(studySelect.value.trim() || manualStudy.value.trim());
}

function renderReport(report, validation, artifacts) {
  const table = document.querySelector("#report-table");
  const head = table.querySelector("thead");
  const body = table.querySelector("tbody");
  head.replaceChildren();
  body.replaceChildren();

  const firstRow = document.createElement("tr");
  for (let index = 0; index < 3; index += 1) {
    firstRow.append(cell("th", report.products[index]?.name || "", "product-head"));
  }
  firstRow.append(cell("th", ""), cell("th", ""), cell("th", ""), cell("th", ""));
  head.append(firstRow);

  const secondRow = document.createElement("tr");
  for (let index = 0; index < 3; index += 1) {
    secondRow.append(cell("th", report.products[index]?.abbreviation || ""));
  }
  secondRow.append(cell("th", ""), cell("th", ""), cell("th", ""), cell("th", ""));
  head.append(secondRow);

  const labelsRow = document.createElement("tr");
  for (let index = 0; index < 3; index += 1) {
    const product = report.products[index];
    labelsRow.append(cell("th", product ? `N = ${product.sample_size}` : ""));
  }
  labelsRow.append(cell("th", "Time Point"), cell("th", ""), cell("th", "DQ Question"), cell("th", "Chinese Description"));
  head.append(labelsRow);

  for (const row of report.rows) {
    const tableRow = document.createElement("tr");
    for (let index = 0; index < 3; index += 1) {
      tableRow.append(cell("td", row.product_values[index]?.display || ""));
    }
    tableRow.append(cell("td", row.day), cell("td", ""), cell("td", row.question), cell("td", row.chinese_description || ""));
    body.append(tableRow);
  }

  document.querySelector("#database-status").textContent = validation.database.message;
  document.querySelector("#database-status").classList.toggle("loaded", validation.database.status === "loaded");
  document.querySelector("#download-report").href = artifacts.business_report;
  document.querySelector("#download-database").href = artifacts.database_ingestion;
  document.querySelector("#download-log").href = artifacts.validation_log;
  document.querySelector("#report-caption").textContent = `${report.rows.length} question/time rows · significance threshold p < 0.05 · markers list products with a significant pairwise difference`;
}

function cell(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}