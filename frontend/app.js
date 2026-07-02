const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
async function api(p, opts) {
  const res = await fetch(p, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || `Request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 2600);
}

const sevBadge = (s) =>
  `<span class="sev-${s} text-xs font-semibold px-2 py-0.5 rounded-full border">${esc(s)}</span>`;
const statusBadge = (s) =>
  `<span class="status-${s} text-xs font-semibold px-2 py-0.5 rounded-full border">${esc((s || "").replace("_", " "))}</span>`;
const sourceLabel = (t) =>
  ({ cms_bulletin: "CMS bulletin", payer_policy: "Payer policy", code_set: "Code set", contract: "Contract" }[t] || t);

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
function showTab(name) {
  $$(".tab-panel").forEach((p) => p.classList.add("hidden"));
  $(`#tab-${name}`).classList.remove("hidden");
  $$(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (name === "dashboard") loadDashboard();
  if (name === "documents") loadDocuments();
  if (name === "review") loadReview();
  if (name === "impact") loadImpact();
  if (name === "audit") loadAudit();
}
$$(".tab-btn").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
const PIPELINE_STEPS = [
  ["1", "Ingest & summarize", "Agent reads each bulletin, policy, code-set update, or contract and extracts codes, modifiers, limits, and dates."],
  ["2", "Detect changes", "Every new version is diffed against the prior one; changes are ranked by dollar / compliance impact."],
  ["3", "Draft executable edits", "Policy language is converted into structured, machine-runnable claim edits with pseudocode and SQL."],
  ["4", "Human sign-off", "Every draft routes to a subject-matter expert. Simulation and export require SME approval — agents augment, never replace."],
];

function renderEngineBadge(engine) {
  const badge = $("#engine-badge");
  const offline = !engine || engine.includes("offline");
  if (offline) {
    badge.textContent = "Agents: OFFLINE (no API key)";
    badge.className = "px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200";
  } else {
    badge.textContent = "Agents: LIVE · " + engine;
    badge.className = "px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-200";
  }
}

async function loadDashboard() {
  const s = await api("/api/stats");
  renderEngineBadge(s.engine);
  const cards = [
    ["Monitored policies", s.documents, "text-slate-800"],
    ["Versions processed", s.versions, "text-slate-800"],
    ["Edits drafted", s.rules_total, "text-brand-600"],
    ["Awaiting sign-off", s.actionable_pending ?? s.rules_pending, "text-amber-600"],
  ];
  $("#stat-cards").innerHTML = cards
    .map(
      ([label, val, cls]) => `
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-3xl font-bold ${cls}">${val}</div>
        <div class="text-xs text-slate-500 mt-1">${label}</div>
      </div>`
    )
    .join("");

  await renderDemoStatus();

  $("#pipeline-steps").innerHTML = PIPELINE_STEPS.map(
    ([n, t, d]) => `
    <li class="flex gap-3">
      <span class="h-6 w-6 shrink-0 rounded-full bg-brand-50 text-brand-600 grid place-items-center text-xs font-bold">${n}</span>
      <div><div class="font-medium">${t}</div><div class="text-slate-500">${d}</div></div>
    </li>`
  ).join("");

  const rules = await api("/api/rules?status=pending");
  const high = rules.filter((r) => r.severity === "high").slice(0, 6);
  $("#dash-pending").innerHTML = high.length
    ? high
        .map(
          (r) => `
        <button class="w-full text-left border border-slate-200 rounded-lg p-3 hover:bg-slate-50" onclick="openRule(${r.id})">
          <div class="flex items-center gap-2 mb-1">${sevBadge(r.severity)}<span class="text-xs text-slate-400">${esc(r.source_name || "")}</span></div>
          <div class="font-medium">${esc(r.title)}</div>
        </button>`
        )
        .join("")
    : `<p class="text-slate-400">No high-severity edits pending. 🎉</p>`;

  updateQueueCount();
}

async function updateQueueCount() {
  const s = await api("/api/stats");
  const el = $("#queue-count");
  const n = s.actionable_pending ?? s.rules_pending;
  el.innerHTML = n
    ? `<span class="bg-amber-100 text-amber-700 rounded-full px-2 py-0.5">${n}</span>`
    : "";
}

async function renderDemoStatus() {
  const el = $("#demo-status-panel");
  if (!el) return;
  let d;
  try {
    d = await api("/api/demo/status");
  } catch {
    el.innerHTML = "";
    return;
  }
  const checks = d.checks || {};
  const items = [
    ["Seeded policy corpus", checks.seeded_corpus],
    ["CMS MPFS pricing", checks.cms_mpfs_loaded],
    ["Sample claims loaded", checks.claims_generated],
    ["Impact simulated", checks.impact_simulated],
    ["Approved edits ready", checks.actionable_approved_edits],
    ["Live LLM agents", checks.live_llm],
  ];
  const ready = d.ready;
  el.innerHTML = `
    <div class="rounded-xl border p-4 ${ready ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}">
      <div class="flex flex-wrap items-center gap-3 mb-2">
        <span class="font-semibold text-sm">${ready ? "Demo ready" : "Demo needs preparation"}</span>
        <button id="dash-prepare-btn" class="ml-auto px-3 py-1.5 rounded-md bg-brand-600 text-white text-xs font-medium hover:bg-brand-700">Prepare now</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
        ${items
          .map(
            ([label, ok]) => `
          <div class="${ok ? "text-green-800" : "text-amber-800"}">
            ${ok ? "✓" : "○"} ${label}
          </div>`
          )
          .join("")}
      </div>
      ${
        d.schedule?.mode === "cms_mpfs"
          ? `<p class="text-xs mt-2 text-green-700">Medicare pricing: ${d.mpfs_codes?.toLocaleString()} codes${d.pprrvu_source ? ` (${esc(d.pprrvu_source)})` : ""}</p>`
          : `<p class="text-xs mt-2 text-amber-700">Upload <strong>PPRRVU*.txt</strong> on Ingest for Medicare pricing.</p>`
      }
    </div>`;
  $("#dash-prepare-btn")?.addEventListener("click", () => runPrepareDemo(false));
}

async function runPrepareDemo(reset) {
  try {
    const url = reset ? "/api/demo/prepare?reset=true" : "/api/demo/prepare";
    const res = await api(url, { method: "POST" });
    toast(
      res.status?.ready
        ? `Demo ready — $${res.total_dollars_caught.toFixed(2)} caught`
        : "Demo prepared — review checklist on Dashboard"
    );
    showTab("dashboard");
  } catch (e) {
    toast(e.message);
  }
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------
const kindBadge = (k) => {
  const label = k === "seed" ? "seed corpus" : "uploaded";
  const cls = k === "seed" ? "kind-seed" : "kind-policy";
  return `<span class="${cls} text-xs font-semibold px-2 py-0.5 rounded-full border">${label}</span>`;
};

function truncateText(s, max = 280) {
  const t = String(s ?? "");
  if (t.length <= max) return t;
  return t.slice(0, max) + "…";
}

async function loadDocuments() {
  const docs = await api("/api/documents?policies_only=true");
  $("#doc-list").innerHTML = docs.length
    ? docs
        .map(
          (d) => `
    <button class="w-full text-left bg-white border border-slate-200 rounded-lg p-3 hover:border-brand-600 doc-item" data-doc-id="${d.id}" onclick="openDoc(${d.id})">
      <div class="flex items-center justify-between gap-2 flex-wrap">
        <span class="text-xs text-slate-400">${esc(sourceLabel(d.source_type))}</span>
        <div class="flex gap-1">${kindBadge(d.kind)}${d.pending_rules ? `<span class="text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5">${d.pending_rules} pending</span>` : ""}</div>
      </div>
      <div class="font-medium text-sm mt-1 leading-snug">${esc(d.title)}</div>
      <div class="text-xs text-slate-500 mt-1">${esc(d.source_name)} · ${d.version_count} version(s)${d.latest_version ? ` · latest <strong>${esc(d.latest_version)}</strong>` : ""}</div>
      ${
        d.change_headline
          ? `<div class="text-xs mt-2 p-2 rounded bg-amber-50 text-amber-900 border border-amber-100 leading-snug">
              ${d.change_from && d.change_to ? `<span class="font-medium">${esc(d.change_from)} → ${esc(d.change_to)}:</span> ` : ""}
              ${esc(truncateText(d.change_headline, 120))}
              ${d.change_count ? `<span class="text-amber-700"> (${d.change_count} change${d.change_count === 1 ? "" : "s"})</span>` : ""}
            </div>`
          : d.version_count < 2
            ? `<div class="text-xs mt-2 text-slate-400">Upload a newer version to detect changes</div>`
            : ""
      }
    </button>`
        )
        .join("")
    : `<p class="text-sm text-slate-400">No policies yet.</p>`;
  if (docs.length) openDoc(docs[0].id);
}

function renderDiff(change, idx) {
  const id = `diff-${idx}`;
  const tag = (txt, cls) => `<span class="${cls} px-1 rounded">${esc(txt)}</span>`;
  let inner = "";
  if (change.change_type === "modified") {
    inner = `<div class="space-y-1">
      <div>${tag("− " + truncateText(change.old_text, 400), "diff-del")}</div>
      <div>${tag("+ " + truncateText(change.new_text, 400), "diff-add")}</div>
    </div>`;
  } else if (change.change_type === "added") {
    inner = tag("+ " + truncateText(change.new_text, 500), "diff-add");
  } else {
    inner = tag("− " + truncateText(change.old_text, 500), "diff-del");
  }
  const long =
    (change.old_text || "").length > 400 ||
    (change.new_text || "").length > 400 ||
    (change.impact_summary || "").length > 160;
  return `
    <div class="mb-3 pb-3 border-b border-slate-100 last:border-0 last:mb-0 last:pb-0">
      <div class="flex items-center gap-2 mb-1 flex-wrap">
        ${sevBadge(change.significance)}
        <span class="text-xs uppercase tracking-wide text-slate-400">${esc(change.change_type)}</span>
        <span class="text-xs text-slate-500 font-medium">${esc(change.section)}</span>
      </div>
      <p class="text-xs text-slate-600 mb-2">${esc(change.impact_summary)}</p>
      <div class="diff-block text-xs" id="${id}">${inner}<div class="diff-fade"></div></div>
      ${long ? `<button type="button" class="text-xs text-brand-600 mt-1 hover:underline" onclick="document.getElementById('${id}').classList.toggle('expanded')">Show full text</button>` : ""}
    </div>`;
}

function renderVersionTimeline(versions) {
  return versions
    .map(
      (v, i) => `
    <div class="version-card pl-3 py-3 ${i < versions.length - 1 ? "border-b border-slate-100" : ""}">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-sm font-semibold text-brand-700">${esc(v.version_label)}</span>
        ${v.effective_date ? `<span class="text-xs text-slate-400">effective ${esc(v.effective_date)}</span>` : ""}
        <span class="text-xs text-slate-400 ml-auto">${(v.text_length || 0).toLocaleString()} chars</span>
      </div>
      <p class="text-sm text-slate-700 leading-relaxed">${esc(truncateText(v.summary, 320))}</p>
      <div class="flex flex-wrap gap-1.5 mt-2">
        ${(v.key_points || []).slice(0, 6).map((k) => `<span class="text-xs bg-slate-100 text-slate-600 rounded px-2 py-0.5">${esc(truncateText(k, 80))}</span>`).join("")}
        ${(v.key_points || []).length > 6 ? `<span class="text-xs text-slate-400">+${v.key_points.length - 6} more</span>` : ""}
      </div>
    </div>`
    )
    .join("");
}

async function openDoc(id) {
  const d = await api(`/api/documents/${id}`);
  $$(".doc-item").forEach((el) => {
    const on = Number(el.dataset.docId) === id;
    el.classList.toggle("border-brand-600", on);
    el.classList.toggle("ring-2", on);
    el.classList.toggle("ring-brand-100", on);
  });

  const reports = d.change_reports
    .map(
      (r, ri) => `
      <div class="change-card border border-amber-200 bg-amber-50/50 rounded-lg p-4 mb-3">
        <div class="flex items-center gap-2 mb-2 flex-wrap">
          <span class="text-xs font-semibold uppercase tracking-wide text-amber-800">Version change</span>
          <span class="text-sm font-medium text-slate-800">${esc(r.from_label)} → ${esc(r.to_label)}</span>
        </div>
        <div class="text-sm font-medium text-slate-800 mb-3">${esc(r.headline)}</div>
        ${r.changes.length ? r.changes.map((c, ci) => renderDiff(c, ri * 100 + ci)).join("") : `<p class="text-xs text-slate-500">No line-level diffs extracted.</p>`}
      </div>`
    )
    .join("");

  const rules = d.rules
    .map(
      (r) => `
      <button class="w-full text-left border border-slate-200 rounded-lg p-3 hover:bg-slate-50 mb-2" onclick="openRule(${r.id})">
        <div class="flex items-center gap-2 mb-1">${sevBadge(r.severity)}${statusBadge(r.review_status)}
          <span class="text-xs text-slate-400 ml-auto">conf ${(r.confidence * 100).toFixed(0)}% · ${esc(r.edit_type)}</span></div>
        <div class="font-medium text-sm">${esc(r.title)}</div>
      </button>`
    )
    .join("");

  const versionHint =
    d.versions.length < 2
      ? `<div class="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-800">
          <strong>Tip:</strong> Upload an updated PDF for the same policy (e.g. 2025 then 2026 NCCI manual) to trigger change detection.
        </div>`
      : "";

  $("#doc-detail").innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="flex items-center gap-2 mb-1">${kindBadge(d.kind)}<span class="text-xs text-slate-400">${esc(sourceLabel(d.source_type))} · ${esc(d.source_name)}</span></div>
        <h2 class="font-semibold text-lg leading-snug">${esc(d.title)}</h2>
      </div>
      ${d.url ? `<a href="${esc(d.url)}" target="_blank" class="text-xs text-brand-600 hover:underline shrink-0">source ↗</a>` : ""}
    </div>
    <div class="mt-5">
      <h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Version history (${d.versions.length})</h3>
      <div class="border border-slate-200 rounded-lg bg-slate-50/30 px-3">${renderVersionTimeline(d.versions)}</div>
    </div>
    ${versionHint}
    ${d.change_reports.length ? `<div class="mt-5"><h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Detected changes</h3>${reports}</div>` : ""}
    ${d.rules.length ? `<div class="mt-5"><h3 class="text-xs uppercase tracking-wide text-slate-500 mb-2">Drafted edits (${d.rules.length})</h3>${rules}</div>` : `<div class="mt-5 text-xs text-slate-400">No executable edits drafted from this document yet.</div>`}
  `;
}

// ---------------------------------------------------------------------------
// Review queue + rule modal
// ---------------------------------------------------------------------------
async function loadReview() {
  const status = $("#review-filter").value;
  const rules = await api("/api/rules" + (status ? `?status=${status}` : ""));
  $("#review-list").innerHTML = rules.length
    ? rules.map(ruleCard).join("")
    : `<p class="text-slate-400 text-sm">No edits in this state.</p>`;
  updateQueueCount();
}
$("#review-filter").addEventListener("change", loadReview);

function ruleCard(r) {
  return `
  <div class="bg-white rounded-xl border border-slate-200 p-5">
    <div class="flex items-center gap-2 mb-2">
      ${sevBadge(r.severity)}${statusBadge(r.review_status)}
      <span class="text-xs text-slate-400">${esc(r.source_name || "")} · ${esc(r.version_label || "")}</span>
      <span class="text-xs text-slate-400 ml-auto">confidence ${(r.confidence * 100).toFixed(0)}% · ${esc(r.edit_type)}</span>
    </div>
    <h3 class="font-semibold">${esc(r.title)}</h3>
    <p class="text-sm text-slate-600 mt-1">${esc(r.rationale)}</p>
    <div class="mt-3 flex gap-2">
      <button class="px-3 py-1.5 rounded-md border border-slate-300 text-sm hover:bg-slate-50" onclick="openRule(${r.id})">Inspect edit</button>
      ${
        r.review_status === "pending"
          ? `<button class="px-3 py-1.5 rounded-md bg-green-600 text-white text-sm hover:bg-green-700" onclick="quickReview(${r.id},'approved')">Approve</button>
             <button class="px-3 py-1.5 rounded-md bg-red-600 text-white text-sm hover:bg-red-700" onclick="quickReview(${r.id},'rejected')">Reject</button>`
          : r.sme_name
          ? `<span class="text-xs text-slate-500 self-center">${esc(r.sme_name)} · ${esc(r.sme_notes || "")}</span>`
          : ""
      }
    </div>
  </div>`;
}

async function openRule(id) {
  const r = await api(`/api/rules/${id}`);
  const L = r.logic;
  const list = (arr) => (arr && arr.length ? arr.map((x) => `<code class="bg-slate-100 px-1 rounded">${esc(x)}</code>`).join(" ") : "—");
  $("#modal-body").innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div><div class="flex items-center gap-2 mb-1">${sevBadge(r.severity)}${statusBadge(r.review_status)}</div>
        <h2 class="text-lg font-semibold">${esc(r.title)}</h2></div>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
    </div>
    <p class="text-sm text-slate-600 mt-2">${esc(r.rationale)}</p>
    <div class="mt-3 p-3 bg-brand-50 border border-brand-100 rounded-lg text-sm">
      <div class="text-xs uppercase tracking-wide text-brand-700 mb-1">Citation (traceable to source)</div>
      <em class="text-slate-700">“${esc(r.citation)}”</em>
    </div>
    <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
      <div><div class="text-xs text-slate-500">Procedure codes</div>${list(L.when_procedure_codes)}</div>
      <div><div class="text-xs text-slate-500">When modifiers</div>${list(L.when_modifiers)}</div>
      <div><div class="text-xs text-slate-500">Unless modifiers</div>${list(L.unless_modifiers)}</div>
      <div><div class="text-xs text-slate-500">Action</div><code class="bg-slate-100 px-1 rounded">${esc(L.action)}</code></div>
      <div><div class="text-xs text-slate-500">Same DOS</div>${L.same_date_of_service ? "yes" : "no"}</div>
      <div><div class="text-xs text-slate-500">Max units</div>${L.max_units ?? "—"}</div>
    </div>
    <div class="mt-4">
      <div class="text-xs uppercase tracking-wide text-slate-500 mb-1">Executable logic (pseudocode)</div>
      <pre class="code">${esc(L.pseudocode)}</pre>
    </div>
    <div class="mt-3">
      <div class="text-xs uppercase tracking-wide text-slate-500 mb-1">SQL preview</div>
      <pre class="code">${esc(L.sql_preview)}</pre>
    </div>
    ${
      r.review_status === "pending"
        ? `<div class="mt-5 border-t border-slate-200 pt-4">
            <div class="text-xs uppercase tracking-wide text-slate-500 mb-2">Subject-matter expert sign-off</div>
            <div class="grid grid-cols-2 gap-2 mb-2">
              <input id="sme-name" placeholder="Your name" class="border border-slate-300 rounded-md px-2 py-1.5 text-sm" />
              <input id="sme-notes" placeholder="Notes (optional)" class="border border-slate-300 rounded-md px-2 py-1.5 text-sm" />
            </div>
            <div class="flex gap-2">
              <button class="px-3 py-1.5 rounded-md bg-green-600 text-white text-sm hover:bg-green-700" onclick="submitReview(${r.id},'approved')">Approve for simulation</button>
              <button class="px-3 py-1.5 rounded-md bg-amber-500 text-white text-sm hover:bg-amber-600" onclick="submitReview(${r.id},'changes_requested')">Request changes</button>
              <button class="px-3 py-1.5 rounded-md bg-red-600 text-white text-sm hover:bg-red-700" onclick="submitReview(${r.id},'rejected')">Reject</button>
            </div>
          </div>`
        : `<div class="mt-5 border-t border-slate-200 pt-4 text-sm text-slate-600">
            Reviewed by <strong>${esc(r.sme_name || "—")}</strong> · ${esc(r.reviewed_at || "")}<br>${esc(r.sme_notes || "")}
            ${r.review_status === "approved" ? `<div class="mt-2"><a class="text-brand-600 hover:underline text-xs" href="/api/rules/${r.id}/export?format=json" target="_blank">Export rule (JSON)</a></div>` : ""}
          </div>`
    }
  `;
  $("#modal").classList.remove("hidden");
}
function closeModal() {
  $("#modal").classList.add("hidden");
}
$("#modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") closeModal();
});

async function submitReview(id, decision) {
  const sme_name = ($("#sme-name")?.value || "").trim() || "SME";
  const sme_notes = ($("#sme-notes")?.value || "").trim();
  await api(`/api/rules/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, sme_name, sme_notes }),
  });
  closeModal();
  toast(`Edit ${decision.replace("_", " ")}`);
  loadReview();
  updateQueueCount();
}

async function quickReview(id, decision) {
  await api(`/api/rules/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, sme_name: "SME", sme_notes: "Quick review" }),
  });
  toast(`Edit ${decision}`);
  loadReview();
}

// ---------------------------------------------------------------------------
// Ingest
// ---------------------------------------------------------------------------
const EXAMPLE = {
  source_type: "cms_bulletin",
  source_name: "CMS NCCI Policy Manual",
  title: "Chapter I — General Correct Coding Policies: Modifier 59 and X{EPSU}",
  version_label: "v2026",
  effective_date: "2026-01-01",
  raw_text:
    "SECTION F. PTP EDIT 11055/11720\nCPT 11055 (paring of corn/callus) is a column-two code to 11720 (debridement of nails). When billed on the same date of service, the column-two code is denied unless modifier XS (separate structure) is appended; modifier 59 alone is no longer sufficient to bypass this edit.\n\nSECTION G. NEW EDIT 17000/11102\nCPT 11102 is a column-two code to 17000. The column-two code is denied unless modifier XU is appended.",
};

$("#ingest-example").addEventListener("click", () => {
  const f = $("#ingest-form");
  for (const [k, v] of Object.entries(EXAMPLE)) if (f[k]) f[k].value = v;
});

$("#ingest-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    source_type: f.source_type.value,
    source_name: f.source_name.value,
    title: f.title.value,
    version_label: f.version_label.value,
    effective_date: f.effective_date.value || null,
    raw_text: f.raw_text.value,
  };
  $("#ingest-output").innerHTML = `<p class="text-slate-400">Running pipeline…</p>`;
  const res = await api("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  renderIngestOutput(res);
  updateQueueCount();
  toast("Pipeline complete");
});

function renderIngestOutput(res) {
  const cr = res.change_report;
  const changes = cr
    ? `<div class="mt-4 p-4 rounded-lg border border-amber-200 bg-amber-50/60">
        <div class="text-xs uppercase tracking-wide text-amber-800 font-semibold mb-1">Change detection</div>
        ${cr.from_label && cr.to_label ? `<div class="text-sm font-medium text-slate-800 mb-1">${esc(cr.from_label)} → ${esc(cr.to_label)}</div>` : ""}
        <div class="text-sm font-medium text-slate-800">${esc(cr.headline)}</div>
        <div class="text-xs text-amber-800 mt-1">${cr.changes.length} change(s) detected</div>
        ${
          cr.changes.length
            ? `<div class="mt-3 space-y-2">${cr.changes.slice(0, 4).map((c, i) => renderDiff(c, 900 + i)).join("")}</div>`
            : ""
        }
      </div>`
    : `<div class="mt-4 p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-800">
        First version of this document — upload an updated version later to diff against it.
      </div>`;
  const rules = (res.draft_rules || [])
    .filter((r) => !/^Monitor policy:/i.test(r.title || ""))
    .map(
      (r) => `
      <button class="w-full text-left border border-slate-200 rounded-lg p-3 hover:bg-slate-50 mb-2" onclick="openRule(${r.id})">
        <div class="flex items-center gap-2 mb-1">${sevBadge(r.severity)}<span class="text-xs text-slate-400 ml-auto">conf ${(r.confidence * 100).toFixed(0)}%</span></div>
        <div class="font-medium text-sm">${esc(r.title)}</div>
      </button>`
    )
    .join("");
  $("#ingest-output").innerHTML = `
    <div class="text-xs uppercase tracking-wide text-slate-500 mb-1">Summary</div>
    <p class="text-sm text-slate-700 leading-relaxed">${esc(truncateText(res.summary, 600))}</p>
    <div class="flex flex-wrap gap-1.5 mt-2">${(res.key_points || []).slice(0, 8).map((k) => `<span class="text-xs bg-slate-100 text-slate-600 rounded px-2 py-0.5">${esc(truncateText(k, 100))}</span>`).join("")}</div>
    ${changes}
    <div class="mt-4"><div class="text-xs uppercase tracking-wide text-slate-500 mb-1">Drafted edits → SME queue (${(res.draft_rules || []).length})</div>${rules || '<span class="text-xs text-slate-400">none</span>'}</div>
    <button type="button" class="mt-4 text-sm text-brand-600 hover:underline" onclick="showTab('documents')">View in Policies & Changes →</button>
  `;
}

// ---------------------------------------------------------------------------
// Upload + mock policy
// ---------------------------------------------------------------------------
const fileInput = $("#file-input");
const dropzone = $("#dropzone");

async function uploadFile(file) {
  $("#upload-status").innerHTML = `<span class="text-slate-500">Extracting & running pipeline…</span>`;
  const fd = new FormData();
  fd.append("file", file);
  const params = new URLSearchParams({
    source_name: "Uploaded document",
    version_label: "uploaded",
    title: file.name,
  });
  try {
    const res = await fetch(`/api/upload?${params}`, { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || String(d)).join("; ")
        : detail || `Upload failed (${res.status})`;
      throw new Error(msg);
    }
    const data = await res.json();
    if (data.upload_type === "fee_schedule") {
      $("#upload-status").innerHTML = `<span class="text-green-600">✓ Loaded CMS fee schedule from “${esc(file.name)}” — ${data.codes_loaded} code(s), CF ${data.conversion_factor}.</span>`;
      toast("Medicare fee schedule loaded — regenerate claims for updated pricing");
      return;
    }
    const verNote = data.change_report
      ? `Change detected: ${data.change_report.headline.slice(0, 80)}…`
      : data.normalized
        ? "First version stored — upload the next year’s manual to diff."
        : "";
    $("#upload-status").innerHTML = `<span class="text-green-600">✓ Ingested “${esc(file.name)}” — ${data.draft_rules.length} edit(s) drafted.${verNote ? ` ${esc(verNote)}` : ""}</span>`;
    renderIngestOutput(data);
    updateQueueCount();
    toast(data.change_report ? "Policy ingested — changes detected" : "Policy ingested");
  } catch (e) {
    $("#upload-status").innerHTML = `<span class="text-red-600">${esc(e.message)}</span>`;
  }
}

if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
  });
  ["dragover", "dragenter"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add("border-brand-600", "bg-brand-50");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove("border-brand-600", "bg-brand-50");
    })
  );
  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
  });
}

$("#gen-mock-btn")?.addEventListener("click", async () => {
  $("#mock-status").textContent = "Generating & running pipeline on v1 + v2…";
  const data = await api("/api/mock/policy", { method: "POST" });
  $("#mock-status").innerHTML = `<span class="text-green-600">✓ Created “${esc(data.title)}” (${data.versions_loaded} versions).</span>`;
  renderIngestOutput(data.latest);
  updateQueueCount();
  toast("Mock policy generated");
});

// ---------------------------------------------------------------------------
// Impact / Dollars Caught
// ---------------------------------------------------------------------------
const simResults = {}; // rule_id -> result
let impactSchedule = { mode: "mock" };
let dollarLabel = "illustrative dollars caught";

function isActionableRule(r) {
  return !/^Monitor policy:/i.test(r.title || "");
}

function sortImpactRules(rules) {
  return [...rules].sort((a, b) => {
    const ah = simResults[a.id]?.flagged_count || 0;
    const bh = simResults[b.id]?.flagged_count || 0;
    if (bh !== ah) return bh - ah;
    const aa = isActionableRule(a) ? 0 : 1;
    const ba = isActionableRule(b) ? 0 : 1;
    if (aa !== ba) return aa - ba;
    if (a.review_status === "approved" && b.review_status !== "approved") return -1;
    if (b.review_status === "approved" && a.review_status !== "approved") return 1;
    return a.id - b.id;
  });
}

function renderImpactBanner() {
  const el = $("#impact-banner");
  if (!el) return;
  if (impactSchedule.mode === "cms_mpfs") {
    el.className = "bg-green-50 border border-green-200 rounded-lg px-4 py-2 text-xs text-green-800 mb-4";
    el.innerHTML =
      `Pricing: <strong>CMS Medicare Physician Fee Schedule</strong> — ` +
      `${impactSchedule.codes?.toLocaleString() || impactSchedule.codes} codes` +
      (impactSchedule.source_label ? ` from <em>${esc(impactSchedule.source_label)}</em>` : "") +
      `. Simulation runs approved edits against <strong>synthetic claims</strong> (no PHI).`;
  } else {
    el.className = "bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-xs text-amber-800 mb-4";
    el.innerHTML =
      `Simulation runs approved edits against <strong>synthetic claims</strong> (no PHI). ` +
      `Upload a <strong>PPRRVU*.txt</strong> file from <a class="underline" href="https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files" target="_blank" rel="noopener">CMS MPFS</a> for Medicare pricing.`;
  }
}

async function loadImpact() {
  let impact;
  try {
    impact = await api("/api/impact");
  } catch {
    impact = { claim_lines: 0, claims: 0, simulations: {}, schedule: { mode: "mock" } };
  }

  impactSchedule = impact.schedule || { mode: "mock" };
  dollarLabel = impactSchedule.mode === "cms_mpfs" ? "Medicare $ caught" : "illustrative dollars caught";
  renderImpactBanner();

  Object.keys(simResults).forEach((k) => delete simResults[k]);
  Object.entries(impact.simulations || {}).forEach(([id, res]) => {
    simResults[Number(id)] = res;
  });

  const statParts = [];
  if (impact.claim_lines) {
    statParts.push(`${impact.claims} sample claims · ${impact.claim_lines} lines`);
  } else {
    statParts.push("No sample claims yet — click Generate sample claims");
  }
  if (impact.rules_approved) statParts.push(`${impact.rules_approved} approved edits`);
  $("#claims-stat").textContent = statParts.join(" · ");

  // Auto-simulate when claims exist but nothing has been run yet
  if (impact.claim_lines > 0 && impact.rules_approved > 0 && !impact.simulated) {
    try {
      await api("/api/impact/simulate-all", { method: "POST" });
      return loadImpact();
    } catch (e) {
      toast(e.message);
    }
  }

  renderImpactSummary(impact);
  const rules = await api("/api/rules");
  const ordered = sortImpactRules(rules);
  const actionable = ordered.filter(isActionableRule);
  const monitor = ordered.filter((r) => !isActionableRule(r));

  let html = "";
  if (actionable.length) {
    html += actionable.map(impactCard).join("");
  } else if (!ordered.length) {
    html = `<p class="text-slate-400 text-sm">No edits yet — ingest a policy PDF or use the seeded corpus.</p>`;
  }
  if (monitor.length) {
    html += `<details class="mt-4 bg-white rounded-xl border border-slate-200 p-4">
      <summary class="text-sm font-medium cursor-pointer text-slate-600">${monitor.length} monitor-only edit(s) from CMS data uploads (no claim matches)</summary>
      <div class="space-y-4 mt-4">${monitor.map(impactCard).join("")}</div>
    </details>`;
  }
  $("#impact-list").innerHTML = html;
}

function impactCard(r) {
  const res = simResults[r.id];
  const pending = r.review_status !== "approved";
  return `
  <div class="bg-white rounded-xl border border-slate-200 p-5 ${pending ? "opacity-80" : ""}">
    <div class="flex items-center gap-2 mb-1 flex-wrap">
      ${sevBadge(r.severity)}${statusBadge(r.review_status)}
      <span class="text-xs text-slate-400">${esc(r.source_name || "")}</span>
      <button class="ml-auto px-3 py-1.5 rounded-md bg-brand-600 text-white text-xs hover:bg-brand-700 ${pending ? "hidden" : ""}" onclick="simulate(${r.id})">Simulate against claims</button>
      ${!pending ? `<a class="px-3 py-1.5 rounded-md border border-slate-300 text-xs hover:bg-slate-50" href="/api/rules/${r.id}/export?format=json" target="_blank">Export JSON</a>` : ""}
    </div>
    <h3 class="font-semibold text-sm">${esc(r.title)}</h3>
    ${res ? renderSimResult(res) : `<p class="text-xs text-slate-400 mt-2">${pending ? "Approve this edit to include in bulk simulation." : "Not simulated yet."}</p>`}
  </div>`;
}

function renderSimResult(res) {
  const rows = res.flagged
    .map(
      (f) => `
      <tr class="border-t border-slate-100">
        <td class="px-2 py-1 font-mono">${esc(f.claim_id)}-${f.line_no}</td>
        <td class="px-2 py-1 font-mono">${esc(f.procedure_code)}</td>
        <td class="px-2 py-1">${esc((f.modifiers || []).join(",") || "—")}</td>
        <td class="px-2 py-1 text-right">${f.units}</td>
        <td class="px-2 py-1 text-right">$${f.dollars.toFixed(2)}</td>
        <td class="px-2 py-1 text-slate-500">${esc(f.reason)}</td>
      </tr>`
    )
    .join("");
  return `
    <div class="mt-3 p-3 bg-slate-50 rounded-lg">
      <div class="flex flex-wrap items-center gap-4 mb-2 text-sm">
        <span><strong class="text-brand-600 text-lg">$${res.dollars_caught.toFixed(2)}</strong> ${dollarLabel}</span>
        <span class="text-slate-500">${res.flagged_count} line(s) flagged of ${res.claims_lines_evaluated} evaluated</span>
      </div>
      <p class="text-xs text-slate-500 mb-2">${esc(res.interpretation)}</p>
      ${
        res.flagged.length
          ? `<div class="overflow-auto"><table class="w-full text-xs">
              <thead class="text-slate-400 text-left"><tr>
                <th class="px-2 py-1">Claim-line</th><th class="px-2 py-1">Code</th><th class="px-2 py-1">Mods</th>
                <th class="px-2 py-1 text-right">Units</th><th class="px-2 py-1 text-right">$ at risk</th><th class="px-2 py-1">Reason</th>
              </tr></thead><tbody>${rows}</tbody></table></div>`
          : `<p class="text-xs text-slate-400">No claims matched this edit.</p>`
      }
    </div>`;
}

async function simulate(ruleId) {
  try {
    const res = await api(`/api/rules/${ruleId}/simulate`, { method: "POST" });
    simResults[ruleId] = res;
    const rules = await api("/api/rules");
    const ordered = sortImpactRules(rules);
    const actionable = ordered.filter(isActionableRule);
    const monitor = ordered.filter((r) => !isActionableRule(r));
    let html = actionable.map(impactCard).join("");
    if (monitor.length) {
      html += `<details class="mt-4 bg-white rounded-xl border border-slate-200 p-4" open>
        <summary class="text-sm font-medium cursor-pointer text-slate-600">${monitor.length} monitor-only edit(s)</summary>
        <div class="space-y-4 mt-4">${monitor.map(impactCard).join("")}</div>
      </details>`;
    }
    $("#impact-list").innerHTML = html;
    const impact = await api("/api/impact");
    renderImpactSummary(impact);
  } catch (e) {
    toast(e.message);
  }
}

function renderImpactSummary(impact) {
  const results = Object.values(simResults);
  const totalDollars = impact?.total_dollars_caught ?? results.reduce((s, r) => s + r.dollars_caught, 0);
  const totalFlagged = results.reduce((s, r) => s + r.flagged_count, 0);
  const withHits = impact?.rules_with_hits ?? results.filter((r) => r.flagged_count > 0).length;
  const dollarCardLabel = impactSchedule.mode === "cms_mpfs" ? "Medicare $ caught" : "Illustrative $ caught";
  const cards = [
    ["Edits simulated", impact?.simulated ?? results.length, "text-slate-800"],
    ["Edits with hits", withHits, "text-amber-600"],
    [dollarCardLabel, "$" + Number(totalDollars).toFixed(2), "text-green-600"],
    ["Claim lines flagged", totalFlagged, "text-brand-600"],
  ];
  $("#impact-summary").innerHTML = cards
    .map(
      ([label, val, cls]) => `
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-2xl font-bold ${cls}">${val}</div>
        <div class="text-xs text-slate-500 mt-1">${label}</div>
      </div>`
    )
    .join("");
}

$("#gen-claims-btn")?.addEventListener("click", async () => {
  try {
    const res = await api("/api/claims/generate", { method: "POST" });
    toast(`Generated ${res.claim_lines} claim lines`);
    Object.keys(simResults).forEach((k) => delete simResults[k]);
    await loadImpact();
    if (res.claim_lines) {
      await api("/api/impact/simulate-all", { method: "POST" });
      await loadImpact();
      toast("Claims generated and simulations run");
    }
  } catch (e) {
    toast(e.message);
  }
});

$("#sim-all-btn")?.addEventListener("click", async () => {
  try {
    const res = await api("/api/impact/simulate-all", { method: "POST" });
    await loadImpact();
    toast(`Simulated ${res.simulated} edits — ${res.rules_with_hits} with hits, $${res.total_dollars_caught.toFixed(2)} caught`);
  } catch (e) {
    toast(e.message);
  }
});

$("#import-mpfs-btn")?.addEventListener("click", async () => {
  try {
    const res = await api("/api/fee-schedule/import", { method: "POST" });
    toast(`Loaded ${res.codes_loaded} Medicare rates from ${res.source}`);
    await loadImpact();
  } catch (e) {
    toast(e.message);
  }
});

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------
async function loadAudit() {
  const rows = await api("/api/audit");
  $("#audit-rows").innerHTML = rows
    .map(
      (r) => `
    <tr class="border-t border-slate-100">
      <td class="px-4 py-2 text-xs text-slate-500 whitespace-nowrap">${esc(r.created_at.replace("T", " ").slice(0, 19))}</td>
      <td class="px-4 py-2 text-xs"><code class="bg-slate-100 px-1 rounded">${esc(r.actor)}</code></td>
      <td class="px-4 py-2 text-xs font-medium">${esc(r.action)}</td>
      <td class="px-4 py-2 text-xs text-slate-600">${esc(r.detail)}</td>
    </tr>`
    )
    .join("");
}

// ---------------------------------------------------------------------------
// Demo prepare / reset
// ---------------------------------------------------------------------------
$("#prepare-demo-btn")?.addEventListener("click", () => runPrepareDemo(false));

$("#reseed-btn")?.addEventListener("click", async () => {
  if (!confirm("Full reset to clean seed corpus and re-prepare demo?")) return;
  await runPrepareDemo(true);
});

// init
showTab("dashboard");
