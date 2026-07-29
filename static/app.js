const API = "/api";

const els = {
  navItems: document.querySelectorAll(".nav-item"),
  views: {
    queue: document.getElementById("view-queue"),
    history: document.getElementById("view-history"),
    detail: document.getElementById("view-detail"),
    searchResults: document.getElementById("view-search-results"),
    dashboard: document.getElementById("view-dashboard"),
    "new-incident": document.getElementById("view-new-incident"),
  },
  topbarEyebrow: document.getElementById("topbar-eyebrow"),
  topbarTitle: document.getElementById("topbar-title"),
  topbarStatus: document.getElementById("topbar-status"),
  kbMini: document.getElementById("kb-mini"),
  patternBanner: document.getElementById("pattern-banner"),
  queueBody: document.getElementById("queue-body"),
  queueEmpty: document.getElementById("queue-empty"),
  historyBody: document.getElementById("history-body"),
  detailCard: document.getElementById("detail-card"),
  slaCountdownContainer: document.getElementById("sla-countdown-container"),
  backToQueue: document.getElementById("back-to-queue"),
  globalSearchInput: document.getElementById("global-search-input"),
  searchResultsBody: document.getElementById("search-results-body"),
  dashboardTotalIncidents: document.getElementById("dashboard-total-incidents"),
  dashboardActiveIncidents: document.getElementById("dashboard-active-incidents"),
  dashboardResolvedIncidents: document.getElementById("dashboard-resolved-incidents"),
  dashboardSlaMet: document.getElementById("dashboard-sla-met"),
  dashboardPriorityChart: document.getElementById("dashboard-priority-chart")?.getContext("2d"),
  dashboardCategoryChart: document.getElementById("dashboard-category-chart")?.getContext("2d"),
  dashboardGroupChart: document.getElementById("dashboard-group-chart")?.getContext("2d"),
  dashboardLoading: document.getElementById("dashboard-loading"),
  dashboardError: document.getElementById("dashboard-error"),
};

let slaInterval = null;
let lastListView = "queue";

// To store chart instances and destroy them before re-rendering
const chartInstances = {};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function stateBadgeClass(stateValue) {
  return "badge badge-" + stateValue.replace(" ", "-");
}

function priorityBadgeClass(priority) {
  return "badge badge-" + priority;
}

async function getJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---------- navigation ----------

function showView(name) {
  Object.entries(els.views).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
  els.navItems.forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === name);
  });
  if (name === "queue" || name === "history") {
    lastListView = name;
  }

  if (name === "queue") {
    els.topbarEyebrow.textContent = "Production Support";
    els.topbarTitle.textContent = "Incident Queue";
    loadQueue();
    loadPatterns();
  } else if (name === "history") {
    els.topbarEyebrow.textContent = "Synapse Memory";
    els.topbarTitle.textContent = "Knowledge Base";
    loadHistory();
  } else if (name === "new-incident") {
    els.topbarEyebrow.textContent = "Service Desk";
    els.topbarTitle.textContent = "Create New Incident";
    prepareNewIncidentForm();
  } else if (name === "dashboard") {
    els.topbarEyebrow.textContent = "Leadership Overview";
    els.topbarTitle.textContent = "Incident Dashboard";
    loadDashboard();
  }
}

els.navItems.forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});
els.backToQueue.addEventListener("click", () => {
  const viewName = lastListView === "history" ? "Knowledge Base" : "queue";
  showView(lastListView);
});

// ---------- stats / kb counter ----------

async function loadStats() {
  try {
    const stats = await getJSON(`${API}/stats`);
    els.kbMini.textContent = `Knowledge base: ${stats.kb_size} incidents`;
    if (!stats.kb_ready) {
      els.topbarStatus.textContent = "Synapse's memory isn't connected — check the API key.";
      els.topbarStatus.classList.add("error");
    } else {
      els.topbarStatus.textContent = "";
      els.topbarStatus.classList.remove("error");
    }
  } catch (e) {
    els.kbMini.textContent = "Knowledge base: unavailable";
  }
}

// ---------- queue view ----------

async function loadQueue() {
  els.queueBody.innerHTML = `<tr><td colspan="6" class="cell-muted">Loading…</td></tr>`;
  try {
    const incidents = await getJSON(`${API}/incidents/queue`);
    if (incidents.length === 0) {
      els.queueBody.innerHTML = "";
      els.queueEmpty.hidden = false;
      return;
    }
    els.queueEmpty.hidden = true;
    els.queueBody.innerHTML = incidents.map((i) => `
      <tr class="clickable" data-number="${i.number}">
        <td class="cell-number">${i.number}</td>
        <td>${i.short_description}</td>
        <td><span class="${priorityBadgeClass(i.priority)}">${i.priority}</span></td>
        <td><span class="${stateBadgeClass(i.state)}">${i.state}</span></td>
        <td class="cell-muted">${i.assignment_group}</td>
        <td class="cell-muted">${fmtDate(i.opened_at)}</td>
      </tr>
    `).join("");

    els.queueBody.querySelectorAll("tr.clickable").forEach((row) => {
      row.addEventListener("click", () => openDetail(row.dataset.number));
    });
  } catch (e) {
    els.queueBody.innerHTML = `<tr><td colspan="6" class="cell-muted">Couldn't load the queue: ${e.message}</td></tr>`;
  }
  loadStats();
}

async function loadPatterns() {
  els.patternBanner.hidden = true;
  try {
    const data = await getJSON(`${API}/patterns`);
    if (!data.groups || data.groups.length === 0) return;
    els.patternBanner.innerHTML = data.groups.map((g) => `
      <div class="pattern-group">
        <strong>&#9889; Pattern detected</strong> across ${g.incident_numbers.join(", ")} —
        ${g.explanation}
      </div>
    `).join("");
    els.patternBanner.hidden = false;
  } catch (e) {
    // Silently skip the banner if pattern detection isn't available.
  }
}

// ---------- history view ----------

async function loadHistory() {
  els.historyBody.innerHTML = `<tr><td colspan="5" class="cell-muted">Loading…</td></tr>`;
  try {
    const incidents = await getJSON(`${API}/incidents/history`);
    els.historyBody.innerHTML = incidents.map((i) => `
      <tr class="clickable" data-number="${i.number}">
        <td class="cell-number">${i.number}</td>
        <td>${i.short_description}</td>
        <td class="cell-muted">${i.category}</td>
        <td class="cell-muted">${i.resolved_by || "—"}</td>
        <td class="cell-muted">${fmtDate(i.resolved_at)}</td>
      </tr>
    `).join("");

    els.historyBody.querySelectorAll("tr.clickable").forEach((row) => {
      row.addEventListener("click", () => openDetail(row.dataset.number));
    });
  } catch (e) {
    els.historyBody.innerHTML = `<tr><td colspan="5" class="cell-muted">Couldn't load history: ${e.message}</td></tr>`;
  }
  loadStats();
}

// ---------- detail view ----------

async function openDetail(number) {
  const viewName = lastListView === "history" ? "Knowledge Base" : "queue";
  els.backToQueue.textContent = `← Back to ${viewName}`;

  showViewRaw("detail");
  els.topbarEyebrow.textContent = "Incident";
  els.topbarTitle.textContent = number;
  els.slaCountdownContainer.innerHTML = "";
  els.detailCard.innerHTML = `<p class="spinner-text">Loading incident…</p>`;

  let incident;
  try {
    incident = await getJSON(`${API}/incidents/${number}`);
  } catch (e) {
    els.detailCard.innerHTML = `<p class="spinner-text">Couldn't load incident: ${e.message}</p>`;
    return;
  }

  if (slaInterval) clearInterval(slaInterval);

  if (incident.sla_due && (incident.state === "New" || incident.state === "In Progress")) {
    const slaDueDate = new Date(incident.sla_due);
    const countdownEl = document.createElement("div");
    countdownEl.className = "sla-countdown";
    els.slaCountdownContainer.appendChild(countdownEl);

    const updateSla = () => {
      const now = new Date();
      const diff = slaDueDate.getTime() - now.getTime();

      if (diff <= 0) {
        countdownEl.textContent = "SLA Breached";
        countdownEl.classList.add("is-breached");
        clearInterval(slaInterval);
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      const pad = (num) => String(num).padStart(2, '0');

      countdownEl.textContent = `Time to SLA: ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
      countdownEl.classList.remove("is-breached");
    };

    updateSla();
    slaInterval = setInterval(updateSla, 1000);
  } else {
    if (slaInterval) clearInterval(slaInterval);
    els.slaCountdownContainer.innerHTML = "";
  }

  renderDetail(incident);
}

function showViewRaw(name) {
  Object.entries(els.views).forEach(([key, el]) => {
    el.hidden = key !== name;
  });
  els.navItems.forEach((btn) => btn.classList.remove("is-active"));
}

function renderDetail(incident) {
  const isActive = incident.state === "New" || incident.state === "In Progress";

  els.detailCard.innerHTML = `
    <div class="detail-header">
      <span class="detail-number">${incident.number}</span>
      <span class="${priorityBadgeClass(incident.priority)}">${incident.priority}</span>
      <span class="${stateBadgeClass(incident.state)}">${incident.state}</span>
    </div>
    <div class="detail-short">${incident.short_description}</div>

    <div class="meta-grid">
      <div><div class="meta-item-label">Category</div><div class="meta-item-value">${incident.category}</div></div>
      <div><div class="meta-item-label">Assignment group</div><div class="meta-item-value">${incident.assignment_group}</div></div>
      <div><div class="meta-item-label">Opened</div><div class="meta-item-value">${fmtDate(incident.opened_at)}</div></div>
      <div><div class="meta-item-label">SLA due</div><div class="meta-item-value">${fmtDate(incident.sla_due)}</div></div>
    </div>

    <div class="desc-card">${incident.description}</div>

    ${isActive ? `
      <button class="ask-button" id="ask-synapse-btn">Ask Synapse</button>
      <div id="synapse-result"></div>
    ` : `
      <div class="synapse-card">
        <div class="synapse-card-title">&#129504; Resolved</div>
        <div class="synapse-plan">${incident.close_notes || ""}</div>
        <div class="match-chip-row"><span class="match-chip">Resolved by<span> ${incident.resolved_by || "—"}</span></span></div>
      </div>
    `}
  `;

  if (isActive) {
    document.getElementById("ask-synapse-btn").addEventListener("click", () => askSynapse(incident));
  }
}

async function askSynapse(incident) {
  const btn = document.getElementById("ask-synapse-btn");
  const resultEl = document.getElementById("synapse-result");
  btn.disabled = true;
  btn.textContent = "Synapse is checking its memory…";
  resultEl.innerHTML = "";

  try {
    const result = await getJSON(`${API}/incidents/${incident.number}/suggest`, { method: "POST" });

    if (!result.confident) {
      resultEl.innerHTML = `
        <div class="no-match-card">
          No strong precedent found in Synapse's memory. This looks like a new pattern —
          once this incident is resolved, Synapse will remember it for next time.
        </div>
      `;
    } else {
      const chips = result.matches.map((m) => `
        <span class="match-chip">${m.number}<span> · ${(m.score * 100).toFixed(0)}% match</span></span>
      `).join("");

      resultEl.innerHTML = `
        <div class="synapse-card">
          <div class="synapse-card-title">&#129504; Suggested Action Plan</div>
          <div class="synapse-plan">${result.suggestion}</div>
          <div class="match-chip-row">${chips}</div>
        </div>
        <div class="resolve-card">
          <div class="resolve-title">Resolve this incident</div>
          <div class="form-grid">
            <label for="resolved-by">Resolved by</label>
            <input id="resolved-by" type="text" placeholder="Your name" />
            <label for="close-notes" class="field-full-width">What was the actual fix?</label>
            <textarea id="close-notes" rows="3" class="field-full-width">${result.suggestion ? result.suggestion.split("\n").slice(0, 3).join(" ") : ""}</textarea>
          </div>
          <button class="resolve-button" id="resolve-btn">Save to Synapse's memory</button>
          <div id="resolve-outcome"></div>
        </div>
      `;
      document.getElementById("resolve-btn").addEventListener("click", () => resolveIncident(incident.number));
    }
  } catch (e) {
    resultEl.innerHTML = `<div class="no-match-card">Synapse couldn't reach the model: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask Synapse";
  }
}

async function resolveIncident(number) {
  const closeNotes = document.getElementById("close-notes").value.trim();
  const resolvedBy = document.getElementById("resolved-by").value.trim();
  const outcomeEl = document.getElementById("resolve-outcome");
  const btn = document.getElementById("resolve-btn");

  if (!closeNotes || !resolvedBy) {
    outcomeEl.innerHTML = `<div class="no-match-card">Add both a resolution note and your name first.</div>`;
    return;
  }

  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    await getJSON(`${API}/incidents/${number}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ close_notes: closeNotes, resolved_by: resolvedBy }),
    });
    outcomeEl.innerHTML = `
      <div class="resolved-banner">
        Saved. Synapse's memory just grew — the next similar incident, on any team, resolves faster.
      </div>
    `;
    loadStats();
  } catch (e) {
    outcomeEl.innerHTML = `<div class="no-match-card">Couldn't save: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Save to Synapse's memory";
  }
}

// ---------- new incident view ----------

async function prepareNewIncidentForm() {
  document.getElementById("create-outcome").innerHTML = "";
  document.getElementById("new-short-description").value = "";
  document.getElementById("new-description").value = "";
  document.getElementById("create-incident-btn").disabled = false;

  try {
    const options = await getJSON(`${API}/meta/form-options`);
    const groupSelect = document.getElementById("new-assignment-group");
    const categorySelect = document.getElementById("new-category");

    groupSelect.innerHTML = options.assignment_groups
      .map(g => `<option>${g}</option>`)
      .join("");

    categorySelect.innerHTML = options.categories
      .map(c => `<option>${c}</option>`)
      .join("");

  } catch (e) {
    document.getElementById("create-outcome").innerHTML =
      `<div class="no-match-card">Couldn't load form options: ${e.message}</div>`;
  }
}

async function createIncident() {
  const btn = document.getElementById("create-incident-btn");
  const outcomeEl = document.getElementById("create-outcome");

  const incidentData = {
    short_description: document.getElementById("new-short-description").value.trim(),
    description: document.getElementById("new-description").value.trim(),
    priority: document.getElementById("new-priority").value,
    assignment_group: document.getElementById("new-assignment-group").value,
    category: document.getElementById("new-category").value,
    opened_by: "Arka Pathak", // Hardcoded from header
  };

  if (!incidentData.short_description || !incidentData.description) {
    outcomeEl.innerHTML = `<div class="no-match-card">Short description and Description are required.</div>`;
    return;
  }

  btn.disabled = true;
  btn.textContent = "Creating...";
  outcomeEl.innerHTML = "";

  try {
    const newIncident = await getJSON(`${API}/incidents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(incidentData),
    });
    outcomeEl.innerHTML = `
      <div class="resolved-banner">
        Successfully created incident ${newIncident.number}. Navigating back to queue...
      </div>
    `;
    setTimeout(() => {
      showView("queue");
    }, 2000);
  } catch (e) {
    outcomeEl.innerHTML = `<div class="no-match-card">Couldn't create incident: ${e.message}</div>`;
    btn.disabled = false;
    btn.textContent = "Create Incident";
  }
}

document.getElementById("create-incident-btn").addEventListener("click", createIncident);

// ---------- global search ----------

async function performSearch() {
  const query = els.globalSearchInput.value.trim();
  if (query.length < 3) {
    els.searchResultsBody.innerHTML = `<tr><td colspan="3" class="cell-muted">Enter at least 3 characters to search.</td></tr>`;
    showViewRaw("searchResults");
    els.topbarEyebrow.textContent = "Search";
    els.topbarTitle.textContent = "Global Search";
    return;
  }

  showViewRaw("searchResults");
  els.topbarEyebrow.textContent = "Search Results";
  els.topbarTitle.textContent = `Results for "${query}"`;
  els.searchResultsBody.innerHTML = `<tr><td colspan="3" class="cell-muted">Searching...</td></tr>`;

  try {
    const incidents = await getJSON(`${API}/search?q=${encodeURIComponent(query)}`);
    if (incidents.length === 0) {
      els.searchResultsBody.innerHTML = `<tr><td colspan="3" class="cell-muted">No incidents found matching your query.</td></tr>`;
      return;
    }
    els.searchResultsBody.innerHTML = incidents.map((i) => `
      <tr class="clickable" data-number="${i.number}">
        <td class="cell-number">${i.number}</td>
        <td>${i.short_description}</td>
        <td><span class="${stateBadgeClass(i.state)}">${i.state}</span></td>
      </tr>
    `).join("");

    els.searchResultsBody.querySelectorAll("tr.clickable").forEach((row) => {
      row.addEventListener("click", () => openDetail(row.dataset.number));
    });
  } catch (e) {
    els.searchResultsBody.innerHTML = `<tr><td colspan="3" class="cell-muted">Search failed: ${e.message}</td></tr>`;
  }
}

els.globalSearchInput.addEventListener("search", performSearch);

// ---------- dashboard view ----------

const MCD_RED = "#da291c";
const MCD_YELLOW = "#ffc72c";
const CHART_COLORS = [MCD_RED, MCD_YELLOW, "#3d3d3d", "#6b7280", "#9ca3af"];

async function loadDashboard() {
  els.dashboardLoading.hidden = false;
  els.dashboardError.hidden = true;
  try {
    const data = await getJSON(`${API}/dashboard-stats`);
    els.dashboardLoading.hidden = true;

    els.dashboardTotalIncidents.textContent = data.total_incidents;
    els.dashboardActiveIncidents.textContent = data.active_incidents; els.dashboardActiveIncidents.classList.add("mcd-red");
    els.dashboardResolvedIncidents.textContent = data.resolved_incidents;
    els.dashboardSlaMet.textContent = `${data.sla_met_percentage}%`;

    renderPieChart(els.dashboardPriorityChart, 'dashboard-priority-chart', "Incidents by Priority", data.incidents_by_priority);
    renderVerticalBarChart(els.dashboardCategoryChart, 'dashboard-category-chart', "Incidents by Category", data.incidents_by_category);
    renderVerticalBarChart(els.dashboardGroupChart, 'dashboard-group-chart', "Incidents by Assignment Group", data.incidents_by_assignment_group);

  } catch (e) {
    els.dashboardLoading.hidden = true;
    els.dashboardError.textContent = `Couldn't load dashboard data: ${e.message}`;
    els.dashboardError.hidden = false;
  }
}

function renderPieChart(ctx, chartId, title, data) {
  if (chartInstances[chartId]) {
    chartInstances[chartId].destroy();
  }
  chartInstances[chartId] = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: Object.keys(data),
      datasets: [{
        label: title,
        data: Object.values(data),
        backgroundColor: CHART_COLORS,
        borderColor: '#fff',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
        },
      }
    }
  });
}

function renderVerticalBarChart(ctx, chartId, title, data) {
  if (chartInstances[chartId]) {
    chartInstances[chartId].destroy();
  }
  chartInstances[chartId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(data),
      datasets: [{
        label: title,
        data: Object.values(data),
        backgroundColor: MCD_RED,
        borderColor: MCD_YELLOW,
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        },
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });
}

// ---------- init ----------

showView("queue");
