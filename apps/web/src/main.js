import './styles.css';
import './advanced.css';
import { api } from './api.js';
const app = document.querySelector('#app');
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const money = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
  });
const number = (value) => Number(value || 0).toLocaleString();
let currentUser = null;
let liveSource = null;
const routes = {
  public: new Set(['/', '/login', '/register']),
  app: new Set(['/app', '/app/overview', '/app/usage', '/app/costs', '/app/models', '/app/model-pricing', '/app/live', '/app/forecasts', '/app/optimization', '/app/anomalies', '/app/budgets', '/app/import', '/app/scenario-lab', '/app/reports', '/app/integrations', '/app/profile']),
  admin: new Set(['/admin', '/admin/users', '/admin/audit', '/admin/system']),
};
const authenticatedHome = (user) => (user.must_change_password ? '/app/profile' : user.role === 'ADMIN' ? '/admin' : '/app/overview');
function navigate(path) {
  history.pushState({}, '', path);
  render();
}
window.addEventListener('popstate', render);
document.addEventListener('click', (event) => {
  const link = event.target.closest('a[data-route]');
  if (link) {
    event.preventDefault();
    navigate(link.getAttribute('href'));
  }
});
function publicHeader() {
  return `<header class="public-nav"><a href="/" data-route class="brand">AI Optimization Tool</a><nav aria-label="Public navigation"><a href="/login" data-route>Sign In</a><a href="/register" data-route class="button primary">Create Profile</a></nav></header>`;
}
async function landing() {
  let telemetry = null;
  try {
    const response = await fetch('/api/telemetry', {
      credentials: 'same-origin',
    });
    if (response.ok) telemetry = await response.json();
  } catch {}
  const live = telemetry ? `<section class="panel"><h2>OpenAI provider telemetry</h2><p><span class="badge">${esc(telemetry.source)}</span> ${esc(telemetry.status)}${telemetry.latency_ms === null ? '' : ` · ${number(telemetry.latency_ms)} ms`}</p><p>${telemetry.models.length ? `${number(telemetry.models.length)} authoritative pricing records; model availability is reported only when observed.` : 'No authoritative pricing records available.'} Organization usage is not available with a project API key.</p></section>` : '';
  return `${publicHeader()}<main id="main"><section class="hero"><p class="eyebrow">AI TELEMETRY & FINOPS</p><h1>Understand every token.<br><span>Optimize every decision.</span></h1><p class="lede">A secure operating view for AI usage, spend, model performance, forecasts, anomalies, and quality-constrained optimization.</p><div class="hero-actions"><a href="/login" data-route class="button primary">Sign In</a><a href="/register" data-route class="button">Create Profile</a></div></section>${live}<section class="feature-grid" aria-label="Platform capabilities">${[
    ['Usage intelligence', 'Attribute token volume across applications and models.'],
    ['Cost control', 'Track spend, budgets, and unit economics.'],
    ['Forecasting', 'Plan capacity and financial exposure from observed history.'],
    ['Optimization', 'Find defensible opportunities without assuming quality equivalence.'],
    ['Operational signals', 'Surface anomalies and model reliability evidence.'],
    ['Enterprise analytics', 'Build an auditable, ownership-aware view of AI operations.'],
  ]
    .map(([title, text]) => `<article><h2>${title}</h2><p>${text}</p></article>`)
    .join('')}</section></main><footer class="public-footer">Private by design · Multi-user web foundation · v0.2.0</footer>`;
}
function authPage(kind) {
  const register = kind === 'register';
  return `${publicHeader()}<main id="main" class="auth-layout"><section class="auth-card"><p class="eyebrow">${register ? 'CREATE PROFILE' : 'WELCOME BACK'}</p><h1>${register ? 'Start understanding your AI operations' : 'Sign in to your workspace'}</h1><form id="authForm">${register ? `<label>Display Name<input name="display_name" autocomplete="name" maxlength="100" required></label><label>Username<input name="username" autocomplete="username" minlength="3" maxlength="40" pattern="[A-Za-z0-9_.-]+" required></label><label>Email<input name="email" type="email" autocomplete="email" maxlength="320" required></label><label>Organization <span>Optional</span><input name="organization" maxlength="120"></label><label>Job Title <span>Optional</span><input name="job_title" maxlength="120"></label>` : `<label>Username or Email<input name="identity" autocomplete="username" maxlength="320" required autofocus></label>`}<label>Password<div class="password-field"><input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" ${register ? 'minlength="12"' : ''} maxlength="128" required><button type="button" data-toggle-password aria-label="Show password">Show</button></div></label>${register ? `<p class="help">Use 12+ characters with uppercase, lowercase, and a number.</p><label>Confirm Password<input name="confirm_password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label>` : ''}<button class="button primary submit" type="submit">${register ? 'Create Profile' : 'Sign In'}</button><p id="formStatus" role="alert" aria-live="polite"></p></form><p>${register ? 'Already registered?' : 'New here?'} <a href="${register ? '/login' : '/register'}" data-route>${register ? 'Sign In' : 'Create Profile'}</a></p></section></main>`;
}
const navItems = [
  ['Overview', '/app/overview'],
  ['Usage', '/app/usage'],
  ['Costs', '/app/costs'],
  ['Models', '/app/models'],
  ['Model Pricing', '/app/model-pricing'],
  ['Live Telemetry', '/app/live'],
  ['Forecasts', '/app/forecasts'],
  ['Optimization', '/app/optimization'],
  ['Anomalies', '/app/anomalies'],
  ['Budgets', '/app/budgets'],
  ['Import Data', '/app/import'],
  ['Scenario Lab', '/app/scenario-lab'],
  ['Reports', '/app/reports'],
  ['Integrations', '/app/integrations'],
];
function shell(content, admin = false) {
  return `<aside class="sidebar"><a href="/app/overview" data-route class="brand">AI Optimization Tool</a><nav aria-label="Application navigation">${navItems.map(([label, path]) => `<a href="${path}" data-route>${label}</a>`).join('')}${currentUser.role === 'ADMIN' ? '<a href="/admin" data-route>Administration</a>' : ''}</nav><div class="account"><a href="/app/profile" data-route>${esc(currentUser.display_name)}</a><button data-logout>Log out</button></div></aside><main id="main" class="workspace">${content}</main>`;
}
const heading = (title, subtitle) => `<header class="page-head"><p class="eyebrow">${currentUser.organization ? esc(currentUser.organization) : 'YOUR WORKSPACE'}</p><h1>${title}</h1><p>${subtitle}</p></header>`;
async function overview() {
  const data = await api('/overview'),
    source = data.live ? 'LIVE' : Object.keys(data.provenance || {}).includes('IMPORTED') ? 'IMPORTED' : 'HISTORICAL';
  return shell(
    `${heading('Overview', 'Your private AI telemetry, spend, and model activity.')}<p><span class="badge">${source}</span> Data provenance</p><section class="metrics">${[
      ['Requests', number(data.requests)],
      ['Tokens', number(data.tokens)],
      ['Attributed spend', money(data.spend)],
      ['Models used', number(data.models_used)],
    ]
      .map(([label, value]) => `<article><span>${label}</span><strong>${value}</strong></article>`)
      .join('')}</section>${data.requests ? `<section class="panel"><h2>Top models</h2><table><thead><tr><th>Model</th><th>Requests</th></tr></thead><tbody>${data.models.map((row) => `<tr><td>${esc(row.name)}</td><td>${number(row.requests)}</td></tr>`).join('')}</tbody></table></section>` : '<section class="panel empty-state"><h2>No telemetry imported yet</h2><p>Import a CSV, JSON, or JSONL file to populate your private analytics.</p><a class="button primary" href="/app/import" data-route>Import Telemetry</a></section>'}`,
  );
}
const metricCards = (items) => `<section class="metrics">${items.map(([label, value]) => `<article><span>${esc(label)}</span><strong>${esc(value)}</strong></article>`).join('')}</section>`;
const breakdown = (title, items, format = number) => `<section class="panel"><h2>${title}</h2>${items.length ? `<table><thead><tr><th>Name</th><th>Value</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.name)}</td><td>${format(item.value)}</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No telemetry imported yet.</p>'}</section>`;
async function usage() {
  const data = await api('/usage');
  return shell(
    `${heading('Usage', 'Owner-scoped request and token activity.')}${metricCards([
      ['Requests', number(data.requests)],
      ['Total tokens', number(data.total_tokens)],
      ['Input tokens', number(data.input_tokens)],
      ['Output tokens', number(data.output_tokens)],
    ])}<div class="analytics-grid">${breakdown('By application', data.applications)}${breakdown('By provider', data.providers)}${breakdown('By model', data.models)}</div>`,
  );
}
async function costs() {
  const data = await api('/costs');
  return shell(
    `${heading('Costs', 'Recorded and independently calculated spend remain distinct.')}<p><span class="badge">${esc(data.cost_basis)}</span> Cost basis</p>${metricCards([
      ['Attributed spend', money(data.total_spend)],
      ['Provider/imported', data.provider_recorded_spend === null ? 'Unknown' : money(data.provider_recorded_spend)],
      ['Calculated', data.calculated_spend === null ? 'Unknown' : money(data.calculated_spend)],
      ['Average per request', money(data.average_per_request)],
    ])}<div class="analytics-grid">${breakdown('By application', data.applications, money)}${breakdown('By provider', data.providers, money)}${breakdown('By model', data.models, money)}</div>`,
  );
}
async function modelsPage() {
  const data = await api('/models');
  return shell(`${heading('Models', 'Model-level workload, token, cost, and latency analytics.')}<section class="panel table-wrap">${data.items.length ? `<table><thead><tr><th>Model</th><th>Provider</th><th>Requests</th><th>Tokens</th><th>Cost</th><th>Latency</th><th>Share</th></tr></thead><tbody>${data.items.map((row) => `<tr><td>${esc(row.model)}</td><td>${esc(row.provider)}</td><td>${number(row.requests)}</td><td>${number(row.tokens)}</td><td>${money(row.cost)}</td><td>${number(row.latency_ms)} ms</td><td>${(row.share * 100).toFixed(1)}%</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No telemetry imported yet.</p>'}</section>`);
}
async function importPage() {
  const history = await api('/import/history');
  return shell(`${heading('Import Telemetry', 'Secure server-side streaming for CSV, JSON, and JSONL files up to 500 MB.')}<section class="panel form-panel"><form id="importForm"><label class="drop-zone">Choose telemetry file<input name="file" type="file" accept=".csv,.json,.jsonl" required></label><p class="help">Files are streamed to private temporary storage, validated, and removed after completion or cancellation.</p><button class="button primary" type="submit">Analyze File</button><p id="importStatus" role="status" aria-live="polite"></p><div id="mapping"></div></form></section><section class="panel"><h2>Import history</h2>${history.items.length ? `<table><thead><tr><th>Filename</th><th>Started</th><th>Rows</th><th>Status</th></tr></thead><tbody>${history.items.map((row) => `<tr><td>${esc(row.filename)}</td><td>${new Date(row.created_at).toLocaleString()}</td><td>${number(row.inserted_rows)} / ${number(row.total_rows)}</td><td><span class="badge">${esc(row.status)}</span></td></tr>`).join('')}</tbody></table>` : '<p class="empty">No imports yet.</p>'}</section>`);
}
function profile() {
  return shell(`${heading('Profile', 'Manage your account details and security.')}<section class="panel form-panel"><form id="profileForm"><label>Username<input value="${esc(currentUser.username)}" disabled></label><label>Display Name<input name="display_name" value="${esc(currentUser.display_name)}" maxlength="100" required></label><label>Email<input name="email" type="email" value="${esc(currentUser.email)}" required></label><label>Organization<input name="organization" value="${esc(currentUser.organization || '')}" maxlength="120"></label><label>Job Title<input name="job_title" value="${esc(currentUser.job_title || '')}" maxlength="120"></label><button class="button primary">Save profile</button><p id="formStatus" role="status"></p></form></section><section class="panel form-panel"><h2>Change Password</h2><form id="passwordForm"><label>Current Password<input name="current_password" type="password" autocomplete="current-password" required></label><label>New Password<input name="new_password" type="password" autocomplete="new-password" minlength="12" required></label><button class="button">Change Password</button><p id="passwordStatus" role="alert"></p></form></section><section class="panel form-panel"><h2>Telemetry data</h2><p>Remove only telemetry and analytics owned by your account.</p><button class="button" type="button" data-reset>Clear My Telemetry Data</button><p id="resetStatus" role="status"></p></section><dialog id="clearTelemetryDialog"><h2>Clear your telemetry data?</h2><p>This permanently deletes telemetry and analytics associated with your account. Your account, provider connections, budgets, settings, and configuration will remain.</p><button class="button" type="button" data-clear-cancel>Cancel</button> <button class="button" type="button" data-clear-confirm>Clear Telemetry</button></dialog>`);
}
async function livePage() {
  const [status, snapshot] = await Promise.all([api('/live/status'), api('/live/snapshot')]), connection=status.connection, session=status.session, metrics=snapshot.metrics || {};
  return shell(`${heading('Live Telemetry', 'Owner-scoped gateway observations from calls reported to CutAIcost.')}<section class="panel form-panel"><h2>Provider connection</h2><p><span class="badge">${esc(connection?.status||'NOT_CONNECTED')}</span>${connection?.masked_identifier?` ${esc(connection.masked_identifier)}`:' No credential stored'}</p>${connection?`<button class="button" data-live-disconnect>Disconnect Provider</button>`:`<form id="liveConnect"><label>OpenAI API Key<input name="credential" type="password" autocomplete="off" required></label><button class="button primary">Connect Provider</button></form>`}<p class="help">Encrypted server-side; plaintext is never returned. A key validates access but cannot reveal calls made directly to OpenAI.</p><p id="liveStatus" role="status"></p></section><section class="panel"><h2>Gateway session</h2><p><span class="badge">${esc(session?.status||'NOT_STARTED')}</span> Mode: GATEWAY</p><p>True per-request telemetry requires AI calls to be reported through the authenticated CutAIcost gateway telemetry endpoint. Provider billing snapshots are not presented as request telemetry.</p>${session?.status==='ACTIVE'?'<button class="button" data-live-stop>Stop Live Telemetry</button>':connection?'<button class="button primary" data-live-start>Start Live Telemetry</button>':''}</section>${metricCards([['Requests',number(metrics.requests)],['Tokens',number(metrics.tokens)],['Session spend',money(metrics.session_spend)],['Average latency',metrics.average_latency_ms==null?'Unknown':`${number(metrics.average_latency_ms)} ms`],['Error rate',`${((metrics.error_rate||0)*100).toFixed(1)}%`]])}<section class="panel table-wrap"><h2>Recent observed requests</h2><p id="liveUpdated">${session?.last_event_at?`Last update ${new Date(session.last_event_at).toLocaleString()}`:'Waiting for gateway events'}</p><table><thead><tr><th>Time</th><th>Provider / model</th><th>Status</th><th>Tokens</th><th>Estimated cost</th><th>Latency</th></tr></thead><tbody id="liveFeed">${(snapshot.items||[]).map(liveRow).join('')||'<tr><td colspan="6">No gateway requests observed in this session.</td></tr>'}</tbody></table></section>`);
}
function liveRow(row){return `<tr><td>${new Date(row.timestamp).toLocaleTimeString()}</td><td>${esc(row.provider)} / ${esc(row.model)}</td><td>${esc(row.status)}</td><td>${number(row.total_tokens)}</td><td>${row.estimated_cost==null?'Unknown':money(row.estimated_cost)}</td><td>${row.latency_ms==null?'Unknown':`${number(row.latency_ms)} ms`}</td></tr>`}
async function pricingPage() {
  const data=await api('/pricing');window.pricingCatalog=data.items;
  const prioritized=data.items.filter(x=>x.status!=='UNKNOWN'||x.lifecycle==='CURRENT');
  return shell(`${heading('Model Pricing', 'Current and priced models first. Token prices are USD per 1 million tokens.')}<section class="panel"><form id="pricingFilters" class="inline"><label>Search models<input name="q" type="search" placeholder="Model name"></label><label>Provider<select name="provider"><option value="">All providers</option>${data.providers.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select></label><label>Category<select name="category"><option value="">All categories</option>${data.categories.map(x=>`<option value="${esc(x)}">${esc(x.replace('_',' & '))}</option>`).join('')}</select></label><label>Sort<select name="sort"><option value="name">Recommended order</option><option value="input">Input price</option><option value="output">Output price</option></select></label><label><input name="missing" type="checkbox"> Missing prices only</label><label><input name="show_all" type="checkbox"> Show all models</label></form></section><section class="panel table-wrap"><table><thead><tr><th>Provider</th><th>Model</th><th>Input / 1M</th><th>Cached input / 1M</th><th>Output / 1M</th><th>Updated</th><th>Status</th></tr></thead><tbody id="pricingTable">${pricingRows(prioritized)}</tbody></table></section>`);
}
const priceCell=value=>value==null?'—':money(value);
function pricingRows(items){return items.length?items.map(row=>`<tr><td>${esc(row.provider)}</td><td><details><summary>${esc(row.display_name||row.model)}</summary><p>Category: ${esc(row.pricing_category)}<br>Lifecycle: ${esc(row.lifecycle)}<br>Availability: ${esc(row.availability)}<br>Model source: ${esc(row.catalog_source||'Unknown')}<br>Pricing source: ${esc(row.pricing_source||'Unknown')}${row.canonical_pricing_model?`<br>Pricing inherited from canonical model: ${esc(row.canonical_pricing_model)}`:''}<br>Last pricing review: ${row.last_pricing_review?new Date(row.last_pricing_review).toLocaleDateString():'Unknown'}<br>Freshness policy: stale after ${number(row.stale_after_days)} days${row.manual_override_active?`<br>Underlying catalog: ${priceCell(row.catalog_input_price_per_1m)} input / ${priceCell(row.catalog_output_price_per_1m)} output (${esc(row.base_status)})`:''}${Object.keys(row.additional_dimensions||{}).length?`<br>Additional dimensions: ${esc(JSON.stringify(row.additional_dimensions))}`:''}</p></details></td><td>${row.pricing_category==='TEXT_REASONING'?priceCell(row.input_price_per_1m):'See details'}</td><td>${row.pricing_category==='TEXT_REASONING'?priceCell(row.cached_input_price_per_1m):'—'}</td><td>${row.pricing_category==='TEXT_REASONING'?priceCell(row.output_price_per_1m):'See details'}</td><td>${row.effective_at?new Date(row.effective_at).toLocaleDateString():'—'}</td><td><span class="badge">${esc(row.status)}</span></td></tr>`).join(''):'<tr><td colspan="7">No catalog models match these filters.</td></tr>'}
async function adminDashboard() {
  const [data, providers, pricing] = await Promise.all([api('/admin/summary'), api('/providers'), api('/admin/pricing')]),
    openai = providers.items.find((x) => x.provider === 'openai'),
    pricingPanel=`<section class="panel form-panel"><h2>Pricing catalog</h2><p>OpenAI credential: <span class="badge">${esc(pricing.providers[0].credential_status)}</span>${pricing.providers[0].masked_identifier?` ${esc(pricing.providers[0].masked_identifier)}`:''}</p><p>Model catalog source: OpenAI Authenticated API.<br>Pricing source: ${esc(pricing.providers[0].pricing_source_label)}.<br>The model API does not return token prices. Manual user overrides always take precedence.</p><p>Last pricing review: ${new Date(pricing.providers[0].last_pricing_review).toLocaleString()}<br>Last model discovery: ${pricing.providers[0].last_model_discovery?new Date(pricing.providers[0].last_model_discovery).toLocaleString():'Never'}<br>Prices become stale after ${number(pricing.providers[0].stale_after_days)} days without review.</p><button class="button primary" data-pricing-preview ${pricing.providers[0].credential_status==='NOT_CONFIGURED'?'disabled':''}>Sync Models & Pricing Catalog</button><div id="pricingResult"></div><dialog id="pricingDialog"><h2>Apply model and pricing catalog changes?</h2><div id="pricingPreview"></div><button class="button" data-pricing-cancel>Cancel</button> <button class="button primary" data-pricing-apply>Apply Catalog</button></dialog></section>`;
  const page=shell(
    `${heading('Administration', 'Users, system health, security activity, and provider credentials.')}<section class="metrics">${[
      ['Total users', data.users.total],
      ['Active users', data.users.active],
      ['Disabled users', data.users.disabled],
      ['Admin users', data.users.admins],
      ['Audit events', data.audit_events],
    ]
      .map(([l, v]) => `<article><span>${l}</span><strong>${number(v)}</strong></article>`)
      .join('')}</section><section class="panel form-panel"><h2>AI Providers</h2><h3>OpenAI</h3><p><span class="badge">${esc(openai?.status || 'NOT_CONNECTED')}</span>${openai?.masked_identifier ? ` Credential ${esc(openai.masked_identifier)}` : ' No credential stored'}</p>${openai ? `<p>Last successful connection: ${openai.last_successful_connection_at ? new Date(openai.last_successful_connection_at).toLocaleString() : 'Never'}<br>Last telemetry refresh: ${openai.last_telemetry_refresh_at ? new Date(openai.last_telemetry_refresh_at).toLocaleString() : 'Never'}${openai.last_latency_ms === null ? '' : `<br>Connection latency: ${number(openai.last_latency_ms)} ms`}</p><button class="button" data-provider-validate>Test Connection</button> <button class="button" data-provider-models>Refresh Models</button> <button class="button" data-provider-disconnect>Remove</button>` : ''}<form id="openaiConnect"><label>${openai ? 'Replace API Key' : 'OpenAI API Key'}<input name="credential" type="password" autocomplete="off" required></label><button class="button primary">${openai ? 'Replace API Key' : 'Connect OpenAI'}</button></form><p class="help">The key is encrypted server-side and never returned to this browser. Billing usage requires a separate OpenAI organization Admin API key and is not collected here.</p><div id="providerModels"></div><p id="providerStatus" role="status"></p></section><section class="panel form-panel"><h2>Telemetry data</h2><p>Clear imported telemetry, import history, and derived forecasts while preserving users and configuration.</p><button class="button" type="button" data-reset>Clear Telemetry Data</button><p id="resetStatus" role="status"></p></section><dialog id="clearTelemetryDialog"><h2>Clear telemetry data?</h2><p>This will permanently delete imported telemetry and derived telemetry records. Application settings, users, integrations, budgets, and configuration will not be removed.</p><button class="button" type="button" data-clear-cancel>Cancel</button> <button class="button" type="button" data-clear-confirm>Clear Telemetry</button></dialog><section class="panel admin-links"><a href="/admin/users" data-route>Manage users</a><a href="/admin/audit" data-route>Review audit log</a><a href="/admin/system" data-route>System diagnostics</a></section>`,
    true,
  );
  return page.replace('<section class="panel form-panel"><h2>Telemetry data</h2>',`${pricingPanel}<section class="panel form-panel"><h2>Telemetry data</h2>`);
}
async function adminUsers() {
  const params = new URLSearchParams(location.search),
    q = params.get('q') || '',
    data = await api(`/admin/users?q=${encodeURIComponent(q)}`);
  return shell(`${heading('User Administration', 'Search, activate, deactivate, and assign roles.')}<section class="panel"><form id="userSearch" class="inline"><label>Search users<input name="q" value="${esc(q)}"></label><button class="button">Search</button></form><div class="table-wrap"><table><thead><tr><th>Profile</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Last login</th><th>Actions</th></tr></thead><tbody>${data.items.map((user) => `<tr><td><strong>${esc(user.display_name)}</strong><small>@${esc(user.username)}</small></td><td>${esc(user.email)}</td><td>${user.role}</td><td>${user.is_active ? 'Active' : 'Disabled'}</td><td>${new Date(user.created_at).toLocaleDateString()}</td><td>${user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td><td><button class="table-button" data-user-action="${user.id}" data-active="${!user.is_active}">${user.is_active ? 'Disable' : 'Enable'}</button><button class="table-button" data-user-role="${user.id}" data-role="${user.role === 'ADMIN' ? 'ANALYST' : 'ADMIN'}">Make ${user.role === 'ADMIN' ? 'Analyst' : 'Admin'}</button></td></tr>`).join('')}</tbody></table></div><p id="formStatus" role="alert"></p></section>`, true);
}
async function adminAudit() {
  const data = await api('/admin/audit');
  return shell(`${heading('Audit Log', 'Security and administrative events without credentials or password data.')}<section class="panel table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>Outcome</th><th>Resource</th></tr></thead><tbody>${data.items.map((row) => `<tr><td>${new Date(row.timestamp).toLocaleString()}</td><td>${esc(row.action)}</td><td>${esc(row.outcome)}</td><td>${esc(row.resource_type)}</td></tr>`).join('')}</tbody></table></section>`, true);
}
async function system() {
  const data = await api('/admin/system');
  return shell(
    `${heading('System Diagnostics', 'Credential-free operational health for administrators.')}<section class="metrics">${[
      ['Queued', data.worker.queued],
      ['Active', data.worker.running],
      ['Cancelling', data.worker.cancelling],
      ['Failed', data.imports.failed],
    ]
      .map(([l, v]) => `<article><span>${l}</span><strong>${number(v)}</strong></article>`)
      .join('')}</section><section class="panel"><h2>Workers</h2>${data.worker.instances.length ? `<table><thead><tr><th>Worker</th><th>Status</th><th>Current job</th><th>Last heartbeat</th><th>Version</th></tr></thead><tbody>${data.worker.instances.map((w) => `<tr><td>${esc(w.hostname)}</td><td><span class="badge">${esc(w.status)}</span></td><td>${esc(w.current_job_id || 'None')}</td><td>${new Date(w.last_heartbeat_at).toLocaleString()}</td><td>${esc(w.version)}</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No workers have registered.</p>'}</section><section class="panel"><dl class="diagnostics"><dt>Application version</dt><dd>${data.application_version}</dd><dt>Database</dt><dd>${data.database}</dd><dt>Migration</dt><dd>${data.migration}</dd><dt>Telemetry rows</dt><dd>${number(data.telemetry_rows)}</dd><dt>Forecast runs</dt><dd>${number(data.forecast_runs)}</dd><dt>Oldest queued job</dt><dd>${data.worker.oldest_job_at ? new Date(data.worker.oldest_job_at).toLocaleString() : 'None'}</dd><dt>Uptime</dt><dd>${number(data.uptime_seconds)} seconds</dd></dl></section>`,
    true,
  );
}
async function render() {
  const path = location.pathname;
  if(liveSource){liveSource.close();liveSource=null}
  app.innerHTML = '<main id="main" class="loading" role="status">Loading…</main>';
  try {
    currentUser = (await api('/auth/me')).user;
  } catch {
    currentUser = null;
  }
  if (routes.public.has(path)) {
    if (currentUser && path !== '/') return navigate(authenticatedHome(currentUser));
    app.innerHTML = path === '/' ? await landing() : authPage(path.slice(1));
    return wire();
  }
  if (!currentUser) return navigate('/login');
  if (routes.admin.has(path) && currentUser.role !== 'ADMIN') return navigate('/app/overview');
  try {
    if (path === '/app' || path === '/app/overview') app.innerHTML = await overview();
    else if (path === '/app/usage') app.innerHTML = await usage();
    else if (path === '/app/costs') app.innerHTML = await costs();
    else if (path === '/app/models') app.innerHTML = await modelsPage();
    else if (path === '/app/model-pricing') app.innerHTML = await pricingPage();
    else if (path === '/app/live') app.innerHTML = await livePage();
    else if (path === '/app/forecasts') app.innerHTML = await forecastsPage();
    else if (path === '/app/optimization') app.innerHTML = await optimizationPage();
    else if (path === '/app/anomalies') app.innerHTML = await anomaliesPage();
    else if (path === '/app/budgets') app.innerHTML = await budgetsPage();
    else if (path === '/app/import') app.innerHTML = await importPage();
    else if (path === '/app/scenario-lab') app.innerHTML = await scenariosPage();
    else if (path === '/app/reports') app.innerHTML = reportsPage();
    else if (path === '/app/integrations') app.innerHTML = await integrationsPage();
    else if (path === '/app/profile') app.innerHTML = profile();
    else if (path === '/admin') app.innerHTML = await adminDashboard();
    else if (path === '/admin/users') app.innerHTML = await adminUsers();
    else if (path === '/admin/audit') app.innerHTML = await adminAudit();
    else if (path === '/admin/system') app.innerHTML = await system();
    else return navigate('/app/overview');
    wire();
  } catch (error) {
    app.innerHTML = `<main id="main" class="error"><h1>Unable to load this page</h1><p>${esc(error.message)}</p><button class="button" onclick="location.reload()">Retry</button></main>`;
  }
}
function wire() {
  document.querySelector('[data-toggle-password]')?.addEventListener('click', (event) => {
    const input = event.currentTarget.previousElementSibling,
      show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    event.currentTarget.textContent = show ? 'Hide' : 'Show';
    event.currentTarget.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });
  document.querySelector('#authForm')?.addEventListener('submit', authSubmit);
  document.querySelector('[data-logout]')?.addEventListener('click', async () => {
    await api('/auth/logout', { method: 'POST' });
    currentUser = null;
    navigate('/');
  });
  document.querySelector('[data-reset]')?.addEventListener('click',()=>document.querySelector('#clearTelemetryDialog')?.showModal());
  document.querySelector('[data-clear-cancel]')?.addEventListener('click',()=>document.querySelector('#clearTelemetryDialog')?.close());
  document.querySelector('[data-clear-confirm]')?.addEventListener('click',resetTelemetry);
  document.querySelector('#profileForm')?.addEventListener('submit', profileSubmit);
  document.querySelector('#passwordForm')?.addEventListener('submit', passwordSubmit);
  document.querySelector('#importForm')?.addEventListener('submit', importSubmit);
  document.querySelector('#forecastForm')?.addEventListener('submit', (event) => simpleSubmit(event, `/forecasts?metric=${event.currentTarget.metric.value}&horizon=${event.currentTarget.horizon.value}`));
  document.querySelector('#budgetForm')?.addEventListener('submit', (event) =>
    simpleSubmit(event, '/budgets', (x) => ({
      ...x,
      monthly_amount: Number(x.monthly_amount),
      warning_threshold: Number(x.warning_threshold),
      is_active: true,
    })),
  );
  document.querySelector('#scenarioForm')?.addEventListener('submit', (event) => simpleSubmit(event, '/scenarios', (x) => Object.fromEntries(Object.entries(x).map(([k, v]) => [k, k === 'name' ? v : Number(v)]))));
  document.querySelector('#integrationForm')?.addEventListener('submit', (event) => simpleSubmit(event, '/integrations', (x) => Object.fromEntries(Object.entries(x).filter(([, v]) => v !== ''))));
  document.querySelector('#openaiConnect')?.addEventListener('submit', connectOpenAI);
  document.querySelector('[data-provider-validate]')?.addEventListener('click', () => providerAction('validate'));
  document.querySelector('[data-provider-disconnect]')?.addEventListener('click', () => providerAction('', 'DELETE'));
  document.querySelector('[data-provider-models]')?.addEventListener('click', () => providerModels());
  document.querySelector('#liveConnect')?.addEventListener('submit', connectOpenAI);
  document.querySelector('[data-live-disconnect]')?.addEventListener('click', () => providerAction('', 'DELETE'));
  document.querySelector('[data-live-start]')?.addEventListener('click', () => liveAction('start'));
  document.querySelector('[data-live-stop]')?.addEventListener('click', () => liveAction('stop'));
  document.querySelector('[data-pricing-preview]')?.addEventListener('click', previewPricing);
  document.querySelector('[data-pricing-cancel]')?.addEventListener('click',()=>document.querySelector('#pricingDialog')?.close());
  document.querySelector('[data-pricing-apply]')?.addEventListener('click',applyPricing);
  document.querySelector('#pricingFilters')?.addEventListener('input',filterPricing);
  if(location.pathname==='/app/live' && document.querySelector('[data-live-stop]'))startLiveStream();
  document.querySelector('#userSearch')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const q = new FormData(event.currentTarget).get('q');
    history.replaceState({}, '', `/admin/users?q=${encodeURIComponent(q)}`);
    adminUsers();
  });
  document.querySelectorAll('[data-user-action]').forEach(
    (button) =>
      (button.onclick = () =>
        updateUser(button.dataset.userAction, {
          is_active: button.dataset.active === 'true',
        })),
  );
  document.querySelectorAll('[data-user-role]').forEach((button) => (button.onclick = () => updateUser(button.dataset.userRole, { role: button.dataset.role })));
}
async function authSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget,
    status = form.querySelector('#formStatus'),
    button = form.querySelector('button[type=submit]'),
    data = Object.fromEntries(new FormData(form));
  button.disabled = true;
  status.textContent = '';
  try {
    if (location.pathname === '/register') {
      await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      navigate('/login');
    } else {
      const result = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      currentUser = result.user;
      navigate(result.redirect_to || authenticatedHome(result.user));
    }
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
  }
}
async function profileSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  data.preferences = currentUser.preferences || {};
  const status = event.currentTarget.querySelector('#formStatus');
  try {
    currentUser = (await api('/profile', { method: 'PATCH', body: JSON.stringify(data) })).user;
    status.textContent = 'Profile saved.';
  } catch (error) {
    status.textContent = error.message;
  }
}
async function passwordSubmit(event) {
  event.preventDefault();
  const status = event.currentTarget.querySelector('#passwordStatus');
  try {
    await api('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))),
    });
    status.textContent = 'Password changed. Please sign in again.';
    setTimeout(() => navigate('/login'), 700);
  } catch (error) {
    status.textContent = error.message;
  }
}
async function updateUser(id, change) {
  if (!confirm(change.is_active === false ? 'Disable this user?' : 'Apply this role or status change?')) return;
  const status = document.querySelector('#formStatus');
  try {
    await api(`/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(change),
    });
    render();
  } catch (error) {
    status.textContent = error.message;
  }
}
async function resetTelemetry() {
  const status = document.querySelector('#resetStatus');
  try {
    const result = await api('/telemetry', { method: 'DELETE' });
    document.querySelector('#clearTelemetryDialog')?.close();
    status.textContent = `Cleared ${number(result.deleted)} telemetry rows and ${number(result.imports_deleted)} import records.`;
  } catch (error) {
    status.textContent = error.message;
  }
}
async function liveAction(action){
  const status=document.querySelector('#liveStatus');try{await api(`/live/${action}`,{method:'POST'});render()}catch(error){if(status)status.textContent=error.message}
}
function startLiveStream(){
  liveSource=new EventSource('/api/v1/live/stream');liveSource.addEventListener('telemetry',(event)=>{const row=JSON.parse(event.data),feed=document.querySelector('#liveFeed');if(!feed)return;if(feed.querySelector('[colspan]'))feed.innerHTML='';feed.insertAdjacentHTML('afterbegin',liveRow(row));document.querySelector('#liveUpdated').textContent=`Last update ${new Date(row.timestamp).toLocaleString()}`});liveSource.addEventListener('session',()=>render());
}
let pendingPricing=null;
async function previewPricing(){
  const target=document.querySelector('#pricingResult');try{pendingPricing=await api('/admin/pricing/refresh',{method:'POST',body:JSON.stringify({provider:'openai',apply:false})});const increased=pendingPricing.changes.filter(x=>x.dimensions.some(d=>d.direction==='INCREASED')).length,decreased=pendingPricing.changes.filter(x=>x.dimensions.some(d=>d.direction==='DECREASED')).length;document.querySelector('#pricingPreview').innerHTML=`<p>OpenAI: ${number(pendingPricing.models_discovered)} discovered; ${number(pendingPricing.current_models)} current; ${number(pendingPricing.legacy_models)} legacy; ${number(pendingPricing.priced_models)} priced; ${number(pendingPricing.models_missing_pricing.length)} unknown; ${number(pendingPricing.new_models_discovered.length)} new; ${number(pendingPricing.models_removed_or_unavailable.length)} unavailable; ${number(pendingPricing.alias_resolved_models)} alias-resolved; ${number(pendingPricing.non_token_models)} non-token categories; ${number(increased)} increased; ${number(decreased)} decreased; ${number(pendingPricing.manual_overrides_protecting_effective_price.length)} protected by overrides.</p><p>Model source: ${esc(pendingPricing.model_catalog_source)}<br>Pricing source: ${esc(pendingPricing.pricing_source_label)}<br>Last pricing review: ${new Date(pendingPricing.last_pricing_review).toLocaleDateString()}</p>${pendingPricing.anomalies_requiring_review.length?'<p role="alert">Unusually large changes are flagged and require explicit confirmation.</p>':''}`;document.querySelector('#pricingDialog').showModal()}catch(error){target.textContent=error.message}
}
async function applyPricing(){
  const target=document.querySelector('#pricingResult');try{const result=await api('/admin/pricing/refresh',{method:'POST',body:JSON.stringify({provider:'openai',apply:true,confirm_anomalies:Boolean(pendingPricing?.anomalies_requiring_review.length)})});document.querySelector('#pricingDialog').close();target.textContent=`Applied catalog refresh: ${number(result.models_changed)} changed, ${number(result.models_added)} added, ${number(result.models_unchanged)} unchanged.`}catch(error){target.textContent=error.message}
}
function filterPricing(event){const form=event.currentTarget,q=form.q.value.toLowerCase(),provider=form.provider.value,category=form.category.value,missing=form.missing.checked,showAll=form.show_all.checked,sort=form.sort.value;let items=window.pricingCatalog.filter(x=>(!q||x.model.toLowerCase().includes(q))&&(!provider||x.provider===provider)&&(!category||x.pricing_category===category)&&(!missing||x.status==='UNKNOWN')&&(showAll||missing||x.status!=='UNKNOWN'||x.lifecycle==='CURRENT'));items.sort(sort==='input'?(a,b)=>(a.input_price_per_1m??Infinity)-(b.input_price_per_1m??Infinity):sort==='output'?(a,b)=>(a.output_price_per_1m??Infinity)-(b.output_price_per_1m??Infinity):(a,b)=>(a.status==='UNKNOWN')-(b.status==='UNKNOWN')||(a.lifecycle!=='CURRENT')-(b.lifecycle!=='CURRENT')||a.model.localeCompare(b.model));document.querySelector('#pricingTable').innerHTML=pricingRows(items)}
async function importSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget,
    file = form.file.files[0],
    status = form.querySelector('#importStatus'),
    button = form.querySelector('button[type=submit]');
  if (!file) return;
  button.disabled = true;
  status.textContent = 'Uploading and analyzing…';
  try {
    const format = file.name.toLowerCase().endsWith('.csv') ? 'csv' : file.name.toLowerCase().endsWith('.jsonl') ? 'jsonl' : 'json';
    const started = await api('/import/start', {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        format,
      }),
    });
    const id = started.import.id,
      data = new FormData();
    data.append('file', file);
    await api(`/import/${id}/upload`, { method: 'POST', body: data });
    const analyzed = await api(`/import/${id}/analyze`, { method: 'POST' }),
      mapping = analyzed.suggested_mapping;
    status.textContent = `Detected ${number(analyzed.import.total_rows)} rows. Review the mapping before import.`;
    const area = form.querySelector('#mapping');
    area.innerHTML = `<h2>Column mapping</h2>${analyzed.columns.map((column) => `<label>${esc(column)}<select data-column="${esc(column)}"><option value="">Ignore</option>${['timestamp', 'application', 'provider', 'model', 'input_tokens', 'output_tokens', 'total_tokens', 'estimated_cost', 'duration_ms'].map((target) => `<option value="${target}" ${mapping[column] === target ? 'selected' : ''}>${target}</option>`).join('')}</select></label>`).join('')}<button type="button" class="button primary" id="commitImport">Import telemetry</button>`;
    area.querySelector('#commitImport').onclick = async () => {
      const selected = {};
      area.querySelectorAll('select').forEach((input) => {
        if (input.value) selected[input.dataset.column] = input.value;
      });
      status.textContent = 'Queueing import…';
      try {
        await api(`/import/${id}/commit`, {
          method: 'POST',
          body: JSON.stringify({ mapping: selected }),
        });
        status.textContent = 'Import queued. A worker will process it safely in the background.';
      } catch (error) {
        status.textContent = error.message;
      }
    };
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
  }
}
async function forecastsPage() {
  const data = await api('/forecasts/runs');
  return shell(`${heading('Forecasts', 'Historical statistical projections from your telemetry.')}<section class="panel"><form id="forecastForm" class="inline"><label>Metric<select name="metric"><option value="spend">Spend</option><option value="tokens">Tokens</option><option value="requests">Requests</option></select></label><label>Horizon<select name="horizon"><option value="30">30 days</option><option value="90">90 days</option></select></label><button class="button primary">Generate forecast</button><p id="formStatus" role="status"></p></form></section><section class="panel"><h2>Forecast runs</h2>${data.items.length ? data.items.map((x) => `<p><strong>${esc(x.result.metric)}</strong> — ${number(x.result.horizon_days)} days — expected ${x.result.metric === 'spend' ? money(x.result.summary.expected) : number(x.result.summary.expected)}</p>`).join('') : '<p class="empty">Not enough telemetry to generate a forecast.</p>'}</section>`);
}
async function optimizationPage() {
  const data = await api('/optimization');
  return shell(`${heading('Optimization', 'Prioritized, traceable observations without invented savings.')}<section class="panel"><h2>${number(data.summary.count)} opportunities</h2>${data.recommendations.length ? data.recommendations.map((x) => `<p><strong>${esc(x.issue)}</strong> — ${esc(x.application)} / ${esc(x.model)} — ${money(x.current_spend)}<br>${esc(x.basis)}</p>`).join('') : '<p class="empty">No evidence-backed optimization opportunities detected.</p>'}</section>`);
}
async function anomaliesPage() {
  const data = await api('/anomalies');
  return shell(`${heading('Anomalies', 'Deterministic deviations from your observed baseline.')}<section class="panel">${data.items.length ? `<table><thead><tr><th>Severity</th><th>Metric</th><th>Observed</th><th>Baseline</th><th>Time</th></tr></thead><tbody>${data.items.map((x) => `<tr><td><span class="badge">${esc(x.severity)}</span></td><td>${esc(x.metric)}</td><td>${number(x.observed)}</td><td>${number(x.baseline)}</td><td>${esc(x.time)}</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No anomalies detected with sufficient history.</p>'}<p>${esc(data.method)}</p></section>`);
}
async function budgetsPage() {
  const data = await api('/budgets');
  return shell(`${heading('Budgets', 'Track monthly spend against explicit limits.')}<section class="panel form-panel"><form id="budgetForm"><label>Name<input name="name" required></label><label>Monthly amount<input name="monthly_amount" type="number" min="0.01" step="0.01" required></label><label>Warning threshold (%)<input name="warning_threshold" type="number" min="1" max="100" value="80" required></label><input name="period" value="monthly" type="hidden"><button class="button primary">Create budget</button><p id="formStatus" role="status"></p></form></section><section class="panel"><h2>Current budgets</h2>${data.items.length ? data.items.map((x) => `<p><strong>${esc(x.name)}</strong> — ${money(x.spent)} of ${money(x.amount)} — <span class="badge">${esc(x.state)}</span></p>`).join('') : '<p class="empty">No budgets configured.</p>'}</section>`);
}
async function scenariosPage() {
  const data = await api('/scenarios');
  return shell(
    `${heading('Scenario Lab', 'Calculate costs from explicit assumptions.')}<section class="panel form-panel"><form id="scenarioForm">${[
      ['name', 'Name', 'text'],
      ['monthly_requests', 'Monthly requests', 'number'],
      ['input_tokens_per_request', 'Input tokens per request', 'number'],
      ['output_tokens_per_request', 'Output tokens per request', 'number'],
      ['input_price_per_million', 'Input price per million', 'number'],
      ['output_price_per_million', 'Output price per million', 'number'],
    ]
      .map(([name, label, type]) => `<label>${label}<input name="${name}" type="${type}" min="0" step="any" required></label>`)
      .join('')}<button class="button primary">Run scenario</button><p id="formStatus" role="status"></p></form></section><section class="panel"><h2>Saved scenarios</h2>${data.items.length ? data.items.map((x) => `<p><strong>${esc(x.parameters.name)}</strong> — ${money(x.result.monthly_cost)} monthly</p>`).join('') : '<p class="empty">No scenarios run yet.</p>'}</section>`,
  );
}
function reportsPage() {
  return shell(`${heading('Reports', 'Export an owner-scoped executive summary.')}<section class="panel"><h2>Executive report</h2><p>Observed usage, costs, and models. CSV cells are protected against formula injection.</p><a class="button" href="/api/v1/reports/executive" target="_blank">Open JSON</a> <a class="button primary" href="/api/v1/reports/executive.csv">Download CSV</a></section>`);
}
async function integrationsPage() {
  const data = await api('/integrations');
  return shell(`${heading('Integrations', 'Operational integrations and provider status.')}<section class="panel"><h2>AI providers</h2><p>Provider credentials are managed by administrators from the Administration page.</p></section>${currentUser.role === 'ADMIN' ? `<section class="panel form-panel"><h2>Environment-backed integration</h2><form id="integrationForm"><label>Name<input name="name" required></label><label>Kind<input name="kind" pattern="[a-z0-9_.-]+" required></label><label>Endpoint<input name="endpoint" type="url"></label><label>Credential environment variable<input name="secret_env_name" pattern="[A-Z][A-Z0-9_]*"></label><button class="button primary">Configure integration</button><p id="formStatus" role="status"></p></form></section>` : ''}<section class="panel"><h2>Configured operational integrations</h2>${data.items.length ? data.items.map((x) => `<p><strong>${esc(x.name)}</strong> — ${esc(x.kind)} — credential ${x.credential_configured ? 'configured' : 'not configured'}</p>`).join('') : '<p class="empty">No operational integrations configured.</p>'}</section>`);
}
async function connectOpenAI(event) {
  event.preventDefault();
  const input = event.currentTarget.credential,
    status = document.querySelector('#providerStatus');
  try {
    await api('/providers/openai/connect', {
      method: 'POST',
      body: JSON.stringify({ credential: input.value }),
    });
    input.value = '';
    render();
  } catch (error) {
    input.value = '';
    status.textContent = error.message;
  }
}
async function providerAction(suffix, method = 'POST') {
  const status = document.querySelector('#providerStatus');
  try {
    await api(`/providers/openai${suffix ? '/' + suffix : ''}`, { method });
    render();
  } catch (error) {
    status.textContent = error.message;
  }
}
async function providerModels() {
  const status = document.querySelector('#providerStatus');
  try {
    const data = await api('/providers/openai/models'),
      target = document.querySelector('#providerModels');
    target.innerHTML = `<p>${number(data.items.length)} models visible to this credential. Capability, context, quality, and pricing remain unknown unless independently verified.</p>`;
  } catch (error) {
    status.textContent = error.message;
  }
}
async function simpleSubmit(event, path, transform = (x) => x) {
  event.preventDefault();
  const status = event.currentTarget.querySelector('#formStatus'),
    data = transform(Object.fromEntries(new FormData(event.currentTarget)));
  try {
    await api(path, { method: 'POST', body: JSON.stringify(data) });
    render();
  } catch (error) {
    status.textContent = error.message;
  }
}
render();
