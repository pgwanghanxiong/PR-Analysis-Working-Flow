const buildStatus = document.querySelector("#questionnaire-build-status");
const buildCount = document.querySelector("#questionnaire-build-count");
const buildScroll = document.querySelector("#questionnaire-build-scroll");
const buildTable = document.querySelector("#questionnaire-build-table");
const buildColumnGroup = buildTable.querySelector("colgroup");
const visitActionsCell = document.querySelector("#visit-actions-cell");
const visitSummary = document.querySelector("#visit-summary");
const addVisitButton = document.querySelector("#add-visit");
const visitDialog = document.querySelector("#visit-dialog");
const visitForm = document.querySelector("#visit-form");
const visitNameInput = document.querySelector("#visit-name");
const visitDialogStatus = document.querySelector("#visit-dialog-status");
const cancelVisitButton = document.querySelector("#cancel-visit");
const createQuestionnaireButton = document.querySelector("#questionnaire-create-button");
const createQuestionnaireStatus = document.querySelector("#questionnaire-create-status");
const downloadQuestionnaireExcelButton = document.querySelector("#download-questionnaire-excel");
const buildSession = requirePageSession();
let questionnairePayload = null;
let visitColumns = [];
let questionnaireExcelPayload = null;

addVisitButton.addEventListener("click", () => {
  visitNameInput.value = "";
  visitDialogStatus.hidden = true;
  visitDialog.showModal();
  visitNameInput.focus();
});

cancelVisitButton.addEventListener("click", () => visitDialog.close());
createQuestionnaireButton.addEventListener("click", createQuestionnairePreview);
downloadQuestionnaireExcelButton.addEventListener("click", downloadQuestionnaireExcel);

visitForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = visitNameInput.value.trim();
  if (!name) return;
  if (visitColumns.some(column => column.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
    visitDialogStatus.textContent = "A Visit / Widget with this name already exists.";
    visitDialogStatus.hidden = false;
    return;
  }

  visitColumns.push({
    name,
    selectedIds: new Set(questionnairePayload.rows.map(row => String(row[0]))),
  });
  visitDialog.close();
  renderQuestionnaireTable(questionnairePayload);
});

async function loadQuestionnaireDefinitions() {
  const token = await buildSession;
  if (!token) return;
  buildStatus.textContent = "Loading questionnaire definitions...";
  buildStatus.classList.remove("error");

  try {
    const response = await fetch("/api/questionnaire-build", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const payload = await response.json();
    if (response.status === 401) {
      sessionStorage.removeItem("questionnaireAccessToken");
      window.location.replace("/login");
      return;
    }
    if (!response.ok) throw new Error(payload.detail || "Could not load questionnaire definitions.");

  questionnairePayload = payload;
  buildScroll.hidden = payload.count === 0;
  renderQuestionnaireTable(payload);
    buildCount.textContent = `${payload.count} questions`;
    buildStatus.textContent = payload.count ? "" : "No questionnaire definitions found.";
  } catch (error) {
    buildStatus.textContent = error.message;
    buildStatus.classList.add("error");
  }
}

function renderQuestionnaireTable(payload) {
  const header = buildTable.querySelector("thead");
  const body = buildTable.querySelector("tbody");
  const baseWidths = [68, 90, 130, 140, 280, 280, 340];
  const visitWidths = getVisitColumnWidths();
  const columnWidths = [...baseWidths, ...visitWidths];
  buildColumnGroup.replaceChildren();
  for (const width of columnWidths) {
    const column = document.createElement("col");
    column.style.width = `${width}px`;
    buildColumnGroup.append(column);
  }
  const totalWidth = columnWidths.reduce((sum, width) => sum + width, 0);
  buildTable.style.width = `${Math.max(totalWidth, buildScroll.clientWidth)}px`;

  const headerRow = document.createElement("tr");
  for (const columnName of payload.columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = columnName;
    cell.title = columnName;
    headerRow.append(cell);
  }
  for (const visit of visitColumns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = visit.name;
    cell.title = visit.name;
    headerRow.append(cell);
  }
  header.replaceChildren(headerRow);

  const rows = document.createDocumentFragment();
  for (const [rowIndex, values] of payload.rows.entries()) {
    const row = document.createElement("tr");
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value == null ? "" : String(value);
      row.append(cell);
    }
    const rowId = String(values[0]);
    for (const [visitIndex, visit] of visitColumns.entries()) {
      const cell = document.createElement("td");
      cell.className = "visit-selection-cell";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = visit.selectedIds.has(rowId);
      checkbox.setAttribute("aria-label", `Include ${values[4] || values[3]} in ${visit.name}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) visit.selectedIds.add(rowId);
        else visit.selectedIds.delete(rowId);
        updateVisitSummary();
      });
      cell.append(checkbox);
      row.append(cell);
    }
    rows.append(row);
  }
  body.replaceChildren(rows);
  visitActionsCell.colSpan = payload.columns.length + visitColumns.length;
  updateVisitSummary();
}

function getVisitColumnWidths() {
  if (!visitColumns.length) return [];
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  context.font = "700 11px Segoe UI, sans-serif";
  return visitColumns.map(visit => Math.max(144, Math.ceil(context.measureText(visit.name).width + 44)));
}

function updateVisitSummary() {
  const totalSelections = visitColumns.reduce((count, visit) => count + visit.selectedIds.size, 0);
  visitSummary.textContent = visitColumns.length
    ? `${visitColumns.length} Visit column(s) · ${totalSelections} question selections · changes are temporary until this page reloads.`
    : "Visit selections are temporary and reset when this page reloads.";
  createQuestionnaireButton.disabled = totalSelections === 0;
  createQuestionnaireStatus.classList.remove("error");
}

function createQuestionnairePreview() {
  if (!questionnairePayload) return;
  const selectedVisits = visitColumns
    .map((visit, index) => ({ ...visit, index, label: formatVisitLabel(visit.name) }))
    .sort(compareVisits);
  const totalSelections = selectedVisits.reduce((count, visit) => count + visit.selectedIds.size, 0);
  if (!selectedVisits.length || !totalSelections) {
    createQuestionnaireStatus.textContent = "Add a Visit and select at least one question before creating the preview.";
    createQuestionnaireStatus.classList.add("error");
    return;
  }

  const columnIndex = Object.fromEntries(questionnairePayload.columns.map((name, index) => [name, index]));
  questionnaireExcelPayload = {
    visits: selectedVisits.map(visit => ({
      name: visit.label,
      questions: questionnairePayload.rows
        .filter(row => visit.selectedIds.has(String(row[0])))
        .map(row => ({
          question_code: row[columnIndex["Variable Code"]] || "",
          question: [row[columnIndex["English Question"]], row[columnIndex["Chinese Question"]]]
            .filter(value => value != null && String(value).trim())
            .map(String)
            .join("\n"),
          answer: row[columnIndex.Options] || "",
        })),
    })),
  };
  downloadQuestionnaireExcelButton.hidden = false;
  downloadQuestionnaireExcelButton.disabled = false;

  const groups = selectedVisits.map((visit) => {
    const questions = questionnairePayload.rows.filter(row => visit.selectedIds.has(String(row[0])));
    const questionMarkup = questions.length
      ? questions.map(row => {
        const code = row[columnIndex["Variable Code"]];
        const english = row[columnIndex["English Question"]];
        const chinese = row[columnIndex["Chinese Question"]];
        const options = row[columnIndex.Options];
        return `<article class="question">
          ${code ? `<p class="code">${escapeHtml(code)}</p>` : ""}
          ${english ? `<h3>${escapeHtml(english)}</h3>` : ""}
          ${chinese ? `<p class="chinese">${escapeHtml(chinese)}</p>` : ""}
          ${options ? `<pre>${escapeHtml(options)}</pre>` : ""}
        </article>`;
      }).join("")
      : '<p class="empty">No questions selected for this Visit.</p>';
    return `<section class="visit"><h2>${escapeHtml(visit.label)}</h2>${questionMarkup}</section>`;
  }).join("");

  const previewWindow = window.open("", "_blank");
  if (!previewWindow) {
    createQuestionnaireStatus.textContent = "Allow pop-ups to open the generated questionnaire preview.";
    createQuestionnaireStatus.classList.add("error");
    return;
  }
  previewWindow.document.open();
  previewWindow.document.write(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Questionnaire Preview</title><style>
*{box-sizing:border-box}body{max-width:980px;margin:0 auto;padding:32px 20px;color:#19332f;font:16px/1.6 Arial,sans-serif;background:#f2f6f3}
h1{font-family:Georgia,serif;font-size:32px}.visit{margin:28px 0;padding-top:12px;border-top:2px solid #087f70}.visit h2{color:#086558;font-family:Georgia,serif}
.question{margin:14px 0;padding:16px;background:white;border:1px solid #d7e1dc;border-radius:4px}.question h3{margin:4px 0;font-size:18px}.code{color:#087f70;font-size:12px;font-weight:bold}.chinese{color:#52645f}pre{white-space:pre-wrap;font:inherit}.empty{color:#647773}
</style></head><body><h1>Questionnaire</h1>${groups}</body></html>`);
  previewWindow.document.close();
  createQuestionnaireStatus.textContent = "Questionnaire preview opened in a new tab.";
  createQuestionnaireStatus.classList.remove("error");
}

async function downloadQuestionnaireExcel() {
  if (!questionnaireExcelPayload) return;
  downloadQuestionnaireExcelButton.disabled = true;
  createQuestionnaireStatus.classList.remove("error");
  createQuestionnaireStatus.textContent = "Preparing Excel file...";

  try {
    const token = await buildSession;
    if (!token) return;
    const response = await fetch("/api/questionnaire-build/export", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(questionnaireExcelPayload),
    });
    if (response.status === 401) {
      sessionStorage.removeItem("questionnaireAccessToken");
      window.location.replace("/login");
      return;
    }
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Could not export the Excel file.");
    }
    const fileUrl = URL.createObjectURL(await response.blob());
    const downloadLink = document.createElement("a");
    downloadLink.href = fileUrl;
    downloadLink.download = "questionnaire.xlsx";
    document.body.append(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    setTimeout(() => URL.revokeObjectURL(fileUrl), 1000);
    createQuestionnaireStatus.textContent = "Excel file downloaded.";
  } catch (error) {
    createQuestionnaireStatus.textContent = error.message;
    createQuestionnaireStatus.classList.add("error");
  } finally {
    downloadQuestionnaireExcelButton.disabled = false;
  }
}

function formatVisitLabel(name) {
  const normalized = name.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  if (/^screening$/i.test(normalized)) return "Screening";
  const numberWords = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
  };
  const match = normalized.match(/^(?:day\s*|d\s*)(\d+|one|two|three|four|five|six|seven|eight|nine|ten)$/i);
  if (!match) return normalized;
  const day = /^\d+$/.test(match[1]) ? Number(match[1]) : numberWords[match[1].toLowerCase()];
  return `D${day}`;
}

function compareVisits(left, right) {
  const leftOrder = visitOrder(left.label, left.index);
  const rightOrder = visitOrder(right.label, right.index);
  return leftOrder[0] - rightOrder[0] || leftOrder[1] - rightOrder[1] || left.index - right.index;
}

function visitOrder(label, index) {
  if (label === "Screening") return [0, 0, index];
  const day = label.match(/^D(\d+)$/i);
  if (day) return [1, Number(day[1]), index];
  return [2, index, index];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

void loadQuestionnaireDefinitions();