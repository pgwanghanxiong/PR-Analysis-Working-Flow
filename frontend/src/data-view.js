const viewStudy = document.querySelector("#view-study");
const refreshViewStudies = document.querySelector("#refresh-view-studies");
const dataViewStatus = document.querySelector("#data-view-status");
const dataViewResults = document.querySelector("#data-view-results");
const dataViewCount = document.querySelector("#data-view-count");
const dataViewTable = document.querySelector("#data-view-table");
const dataViewScroller = document.querySelector("#data-view-results .table-scroll");
const viewSession = requirePageSession();
let currentRequest = 0;

window.addEventListener("resize", updateDataViewViewport);

viewStudy.addEventListener("change", () => {
  void loadStudyData(viewStudy.value);
});

refreshViewStudies.addEventListener("click", () => {
  void loadViewStudies();
});

async function loadViewStudies() {
  const token = await viewSession;
  if (!token) return;
  currentRequest += 1;
  refreshViewStudies.disabled = true;
  viewStudy.disabled = true;
  dataViewResults.hidden = true;
  dataViewCount.textContent = "";
  dataViewStatus.classList.remove("error");
  dataViewStatus.textContent = "Loading Study Names...";

  try {
    const response = await fetch("/api/studies", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const payload = await response.json();
    if (response.status === 401) {
      sessionStorage.removeItem("questionnaireAccessToken");
      window.location.replace("/login");
      return;
    }
    if (!response.ok) throw new Error(payload.detail || "Could not load Study Names.");
    viewStudy.replaceChildren(new Option("Select a Study Name", ""));
    for (const studyName of payload.study_names) {
      viewStudy.append(new Option(studyName, studyName));
    }
    viewStudy.disabled = payload.study_names.length === 0;
    dataViewStatus.textContent = payload.study_names.length ? "" : "No Study Names found.";
  } catch (error) {
    viewStudy.replaceChildren(new Option("Study Names unavailable", ""));
    dataViewStatus.textContent = error.message;
    dataViewStatus.classList.add("error");
  } finally {
    refreshViewStudies.disabled = false;
  }
}

async function loadStudyData(studyName) {
  const requestId = ++currentRequest;
  dataViewResults.hidden = true;
  dataViewCount.textContent = "";
  dataViewStatus.classList.remove("error");
  if (!studyName) {
    dataViewStatus.textContent = "";
    return;
  }
  dataViewStatus.textContent = "Loading study responses...";

  try {
    const token = await viewSession;
    if (!token) return;
    const params = new URLSearchParams({ study_name: studyName });
    const response = await fetch(`/api/questionnaire-data?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const payload = await response.json();
    if (requestId !== currentRequest) return;
    if (response.status === 401) {
      sessionStorage.removeItem("questionnaireAccessToken");
      window.location.replace("/login");
      return;
    }
    if (!response.ok) throw new Error(payload.detail || "Could not load study responses.");
    dataViewResults.hidden = false;
    renderDataView(payload);
    dataViewCount.textContent = `${payload.rows.length} rows · ${payload.columns.length - 4} questions`;
    dataViewStatus.textContent = payload.duplicate_cells
      ? `${payload.duplicate_cells} cells contain multiple recorded values.`
      : "";
    updateDataViewViewport();
  } catch (error) {
    if (requestId !== currentRequest) return;
    dataViewStatus.textContent = error.message;
    dataViewStatus.classList.add("error");
  }
}

function renderDataView(payload) {
  const columnGroup = dataViewTable.querySelector("colgroup");
  const header = dataViewTable.querySelector("thead");
  const body = dataViewTable.querySelector("tbody");
  const headerRow = document.createElement("tr");
  columnGroup.replaceChildren();
  for (const [columnIndex, label] of payload.columns.entries()) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.title = label;
    const characters = Array.from(label);
    const characterLimit = columnIndex === 1 ? 12 : columnIndex >= 4 ? 15 : null;
    cell.textContent = characterLimit !== null && characters.length > characterLimit
      ? `${characters.slice(0, characterLimit).join("")}...`
      : label;
    headerRow.append(cell);
  }
  header.replaceChildren(headerRow);

  const fragment = document.createDocumentFragment();
  for (const values of payload.rows) {
    const row = document.createElement("tr");
    for (const [columnIndex, value] of values.entries()) {
      const cell = document.createElement("td");
      cell.textContent = Array.isArray(value) ? value.join(", ") : String(value);
      if (columnIndex >= 4) {
        cell.className = "dq-value";
        cell.title = cell.textContent;
      } else if (columnIndex === 1) {
        cell.title = cell.textContent;
      }
      row.append(cell);
    }
    fragment.append(row);
  }
  body.replaceChildren(fragment);

  const sampleCell = body.querySelector("td");
  const style = sampleCell ? getComputedStyle(sampleCell) : getComputedStyle(dataViewTable);
  const context = document.createElement("canvas").getContext("2d");
  context.font = style.font || `${style.fontSize} ${style.fontFamily}`;
  const horizontalPadding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 2;
  const identityWidths = payload.columns.slice(0, 4).map((_, columnIndex) => {
    let widest = 0;
    for (const row of payload.rows) {
      const value = row[columnIndex];
      const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
      widest = Math.max(widest, context.measureText(text).width);
    }
    return Math.max(24, Math.ceil(widest + horizontalPadding));
  });
  const headerStyle = getComputedStyle(headerRow.querySelector("th"));
  context.font = headerStyle.font || `${headerStyle.fontSize} ${headerStyle.fontFamily}`;
  if (headerRow.cells.length > 1) {
    identityWidths[1] = Math.max(24, Math.ceil(context.measureText(headerRow.cells[1].textContent).width + horizontalPadding));
  }
  const dqHeaders = Array.from(headerRow.cells).slice(4);
  const dqWidth = Math.max(24, ...dqHeaders.map(cell => Math.ceil(context.measureText(cell.textContent).width + horizontalPadding)));
  const widths = [...identityWidths, ...dqHeaders.map(() => dqWidth)];
  for (const width of widths) {
    const column = document.createElement("col");
    column.style.width = `${width}px`;
    columnGroup.append(column);
  }
  dataViewTable.style.width = `${widths.reduce((sum, width) => sum + width, 0)}px`;
}

function updateDataViewViewport() {
  if (dataViewResults.hidden) return;
  const top = Math.max(0, dataViewScroller.getBoundingClientRect().top);
  dataViewScroller.style.maxHeight = `${Math.max(120, window.innerHeight - top - 24)}px`;
}

void loadViewStudies();