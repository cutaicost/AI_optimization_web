import './styles.css';
import './landing.css';
import './advanced.css';
import './admin.css';
import { api } from './api.js';
import { demoPage, signupRequestPage, stopDemo, wireDemo } from './demo.js';
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
let liveTimer = null;
const routes = {
  public: new Set(['/', '/demo', '/book-demo', '/signup', '/register', '/login']),
  app: new Set(['/app', '/app/overview', '/app/usage', '/app/costs', '/app/models', '/app/model-pricing', '/app/live', '/app/forecasts', '/app/optimization', '/app/anomalies', '/app/budgets', '/app/import', '/app/scenario-lab', '/app/reports', '/app/integrations', '/app/profile']),
  admin: new Set(['/admin','/admin/members','/admin/organization','/admin/providers','/admin/membership','/admin/usage','/admin/budgets','/admin/pricing','/admin/data-privacy','/admin/security','/admin/audit','/admin/notifications','/admin/system','/admin/users']),
};
const canAdmin=user=>user?.role==='ADMIN'||['OWNER','ADMIN'].includes(user?.organization_role);
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
  return `<header class="public-nav"><div class="public-nav-inner"><a href="/" data-route class="brand">CutAIcost</a><nav aria-label="Public navigation"><a href="#product">Product</a><a href="/login" data-route>Sign In</a><a href="/signup" data-route class="button">Sign Up Request</a><a href="/book-demo" data-route class="button primary">Book a Consultation</a></nav></div></header>`;
}
async function landing() {
  let telemetry = null;
  try {
    const response = await fetch('/api/telemetry', {
      credentials: 'same-origin',
    });
    if (response.ok) telemetry = await response.json();
  } catch {}
  const status=telemetry?.status||'Not connected',available=status==='AVAILABLE',models=Array.isArray(telemetry?.models)?telemetry.models:[],latency=telemetry?.latency_ms;
  const preview=`<aside class="hero-preview" aria-label="Live platform status"><div class="preview-head"><div><p class="eyebrow">LIVE PLATFORM STATUS</p><h2>OpenAI</h2></div><span class="status-dot ${available?'available':''}">${available?'Available':esc(status)}</span></div><div class="preview-metrics"><div><span>Latency</span><strong>${latency==null?'—':`${number(latency)} ms`}</strong></div><div><span>Pricing records</span><strong>${number(models.length)}</strong></div><div><span>Catalog</span><strong>${models.length?'Verified':'No records'}</strong></div></div><div class="signal-preview" aria-label="Recent public provider signal"><div class="signal-grid"></div><svg viewBox="0 0 440 72" role="img" aria-label="Provider signal visualization"><polyline points="0,45 34,44 55,30 76,48 102,42 126,43 148,22 170,49 202,44 226,38 250,42 278,41 302,26 324,46 350,42 378,43 402,35 440,42"/></svg></div><div class="preview-foot"><span>Recent activity</span><span>Token spend</span><span>Latency</span><span>Model availability</span></div><p class="preview-note">${telemetry?'Public provider status only. No organization usage is exposed.':'Provider status is currently unavailable. No customer data is shown.'}</p></aside>`;
  return `${publicHeader()}<main id="main" class="landing-page"><section class="landing-container landing-hero"><div class="hero-copy"><p class="eyebrow">AI TELEMETRY & FINOPS</p><h1>Understand every token.<br><span>Optimize every decision.</span></h1><p class="lede">AI cost intelligence, live telemetry, model pricing, forecasting, and quality-constrained optimization in one secure platform.</p><div class="hero-actions"><a href="/book-demo" data-route class="button primary">Book a Consultation</a><a href="/signup" data-route class="button">Sign Up Request</a></div><p class="hero-note">Meet with our team or request private platform access.</p></div>${preview}</section><section id="product" class="landing-container primary-capabilities" aria-label="Primary platform capabilities">${[
    ['AI Cost Intelligence','Track token usage, pricing, budgets, and spend.'],['Live Telemetry','Observe model performance, latency, tokens, and cost signals.'],['Optimization','Identify cost opportunities while respecting quality requirements.']
  ].map(([title,text],index)=>`<article><span class="feature-number">0${index+1}</span><h2>${title}</h2><p>${text}</p></article>`).join('')}</section><section class="secondary-section"><div class="landing-container"><header class="section-intro"><p class="eyebrow">A COMPLETE OPERATING VIEW</p><h2>From usage signal to financial decision.</h2></header><div class="secondary-features">${[
    ['Forecasting','Model future exposure from observed trends.'],['Operational Signals','Surface anomalies and reliability evidence.'],['Enterprise Analytics','Maintain an auditable ownership-aware view.'],['Model Pricing','Compare maintained model economics.'],['Reports','Share clear operational assessments.'],['Budgets','Set accountable spend guardrails.']
  ].map(([title,text])=>`<article><h3>${title}</h3><p>${text}</p></article>`).join('')}</div></div></section><section class="landing-container demo-showcase"><div><p class="eyebrow">PLATFORM ACCESS</p><h2>Want access to the platform?</h2><p>Submit a Sign Up Request and we’ll contact you directly about onboarding, account setup, and how you plan to use CutAIcost.</p><p class="demo-proof">Submitting a request <span>does not automatically create an account.</span></p></div><a href="/signup" data-route class="button">Sign Up Request</a></section><section class="landing-container demo-showcase"><div><p class="eyebrow">OWNER-LED REVIEW</p><h2>Want to walk through it with us first?</h2><p>Book a consultation with a CutAICost owner to discuss your AI environment, costs, telemetry, forecasting, and optimization.</p></div><a href="/book-demo" data-route class="button primary">Book a Consultation</a></section></main><footer class="public-footer"><div class="landing-container">Private by design · Quality-constrained optimization · v0.2.0</div></footer>`;
}
function authPage(kind) {
  const register = kind === 'signup' || kind === 'register';
  return `${publicHeader()}<main id="main" class="auth-layout"><section class="auth-card"><p class="eyebrow">${register ? 'CREATE ACCOUNT' : 'WELCOME BACK'}</p><h1>${register ? 'Sign up for CutAIcost' : 'Sign in to your workspace'}</h1><form id="authForm">${register ? `<label>Full Name<input name="display_name" autocomplete="name" maxlength="100" required></label><label>Username<input name="username" autocomplete="username" minlength="3" maxlength="40" pattern="[A-Za-z0-9_.-]+" required></label><label>Email<input name="email" type="email" autocomplete="email" maxlength="320" required></label><label>Company / Organization <span>Optional</span><input name="organization" autocomplete="organization" maxlength="120"></label>` : `<label>Username or Email<input name="identity" autocomplete="username" maxlength="320" required autofocus></label>`}<label>Password<div class="password-field"><input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" ${register ? 'minlength="12"' : ''} maxlength="128" required><button type="button" data-toggle-password aria-label="Show password">Show</button></div></label>${register ? `<p class="help">Use 12+ characters with uppercase, lowercase, and a number.</p><label>Confirm Password<input name="confirm_password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></label>` : ''}<button class="button primary submit" type="submit">${register ? 'Sign Up' : 'Log In'}</button><p id="formStatus" role="alert" aria-live="polite"></p></form><p>${register ? 'Already have an account?' : 'New to CutAIcost?'} <a href="${register ? '/login' : '/signup'}" data-route>${register ? 'Log In' : 'Sign Up'}</a></p></section></main>`;
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
  return `<aside class="sidebar"><a href="/app/overview" data-route class="brand">CutAIcost</a><nav aria-label="Application navigation">${navItems.map(([label, path]) => `<a href="${path}" data-route ${location.pathname===path?'aria-current="page"':''}>${label}</a>`).join('')}${canAdmin(currentUser) ? `<a href="/admin" data-route ${location.pathname.startsWith('/admin')?'aria-current="page"':''}>Administration</a>` : ''}</nav><div class="account"><a href="/app/profile" data-route>${esc(currentUser.display_name)}</a><button data-logout>Log out</button></div></aside><main id="main" class="workspace">${content}</main>`;
}
const heading = (title, subtitle) => `<header class="page-head"><p class="eyebrow">${currentUser.organization ? esc(currentUser.organization) : 'YOUR WORKSPACE'}</p><h1>${title}</h1><p>${subtitle}</p></header>`;
const adminItems=[['Overview','/admin'],['Members','/admin/members'],['Organization','/admin/organization'],['Providers','/admin/providers'],['Membership','/admin/membership'],['Usage','/admin/usage'],['Budgets','/admin/budgets'],['Pricing','/admin/pricing'],['Data & Privacy','/admin/data-privacy'],['Security','/admin/security'],['Audit Log','/admin/audit'],['Notifications','/admin/notifications'],['System','/admin/system']];
const adminNav=()=>`<nav class="admin-nav" aria-label="Administration sections">${adminItems.map(([label,path])=>`<a href="${path}" data-route ${location.pathname===path?'aria-current="page"':''}>${label}</a>`).join('')}</nav>`;
const adminShell=(title,subtitle,content)=>shell(`${heading(title,subtitle)}${adminNav()}${content}`,true);
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
  const active=session?.status==='ACTIVE',items=snapshot.items||[],provider=connection?.provider||session?.provider||'OpenAI';
  return shell(`${heading('Live Telemetry', 'Real-time AI gateway usage, cost, latency, and request activity.')}<section class="telemetry-control"><div><span class="console-label">Live connection</span><div class="connection-line"><strong>${esc(humanize(provider))}</strong><span class="status-dot ${connection?.status==='CONNECTED'?'on':''}"></span><span>${esc(humanize(connection?.status||'Not connected'))}</span><span class="divider"></span><strong>Gateway</strong><span class="status-dot ${active?'live':''}"></span><span>${active?'Live':connection?'Ready':'Offline'}</span></div><div class="connection-meta">${connection?.masked_identifier?`<span>Key ${esc(connection.masked_identifier)}</span>`:'<span>No credential stored</span>'}<span>Mode: Gateway</span><span title="Credentials are encrypted server-side; plaintext is never returned. A provider key alone cannot reveal calls made directly to the provider.">Credentials encrypted server-side ⓘ</span></div></div><div class="session-clock"><span>Session</span><strong data-session-clock data-started="${esc(session?.started_at||'')}">${session?elapsedLabel(session):'—'}</strong>${session?.started_at?`<small>Started ${new Date(session.started_at).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})}</small>`:''}</div><div class="telemetry-actions">${connection?`${active?'<button class="button" data-live-stop>Stop Session</button>':'<button class="button primary live-primary" data-live-start>Start Live Telemetry</button>'}<button class="text-button" data-live-disconnect>Manage Connection</button>`:`<form id="liveConnect" class="live-connect"><input aria-label="OpenAI API Key" name="credential" type="password" autocomplete="off" placeholder="OpenAI API key" required><button class="button primary">Connect</button></form>`}<p id="liveStatus" role="status"></p></div><p class="gateway-note">Live request telemetry is captured through the CutAIcost Gateway. <span title="True per-request telemetry requires AI calls to be reported through the authenticated CutAIcost gateway endpoint. Provider billing snapshots are not presented as request telemetry.">ⓘ</span></p></section><div id="liveDashboard">${liveDashboard(session,metrics,items)}</div>`);
}
function elapsedLabel(session){const end=session.status==='ACTIVE'?Date.now():new Date(session.stopped_at||session.started_at).getTime(),seconds=Math.max(0,Math.floor((end-new Date(session.started_at).getTime())/1000));return [Math.floor(seconds/3600),Math.floor(seconds%3600/60),seconds%60].map(x=>String(x).padStart(2,'0')).join(':')}
function liveDashboard(session,metrics,items){const active=session?.status==='ACTIVE',requests=metrics.requests||0,input=items.reduce((sum,x)=>sum+(x.input_tokens||0),0),output=items.reduce((sum,x)=>sum+(x.output_tokens||0),0),failed=items.filter(x=>!['ok','success','observed'].includes(String(x.status).toLowerCase())).length,duration=session?.started_at?Math.max(1,(Date.now()-new Date(session.started_at).getTime())/60000):1,rpm=active?requests/duration:0,tpm=active?(metrics.tokens||0)/duration:0,spm=active?(metrics.session_spend||0)/duration:0;return `<section class="telemetry-kpis">${[['Requests',number(requests),'requests this session'],['Tokens',number(metrics.tokens||0),`${number(input)} input · ${number(output)} output`],['Session spend',money(metrics.session_spend||0),`${money(spm)} / min`],['Avg latency',metrics.average_latency_ms==null?'—':`${number(metrics.average_latency_ms)} ms`,metrics.average_latency_ms==null?'No samples yet':'gateway measured'],['Error rate',`${((metrics.error_rate||0)*100).toFixed(1)}%`,`${number(failed)} failed request${failed===1?'':'s'}`]].map(([label,value,note])=>`<article><header><span>${label}</span>${active?'<small><i></i> Live</small>':''}</header><strong>${value}</strong><p>${note}</p></article>`).join('')}</section><section class="live-activity"><header><div><span class="console-label">Live activity</span><h2>Gateway throughput</h2></div><small>Last 60 seconds</small></header>${items.length?`<div class="activity-values"><span><small>Requests / min</small><strong>${number(rpm.toFixed(1))}</strong></span><span><small>Tokens / min</small><strong>${number(Math.round(tpm))}</strong></span><span><small>Spend / min</small><strong>${money(spm)}</strong></span><span><small>Latency</small><strong>${metrics.average_latency_ms==null?'—':`${number(metrics.average_latency_ms)} ms`}</strong></span></div><div class="activity-strip" aria-label="Recent request activity">${items.slice(0,30).reverse().map(x=>`<i style="height:${Math.max(8,Math.min(100,(x.total_tokens||1)/Math.max(...items.map(y=>y.total_tokens||1))*100))}%" title="${esc(x.model)}: ${number(x.total_tokens)} tokens"></i>`).join('')}</div>`:`<div class="console-empty"><strong>${active?'Listening for requests':'No active session'}</strong><p>${active?'Gateway connected. Waiting for the first AI request...':'Start Live Telemetry to begin observing requests through the CutAIcost Gateway.'}</p></div>`}</section>${modelBreakdown(items)}<section class="recent-requests"><header><div><span class="console-label">Recent requests</span><h2>Observed gateway activity</h2></div><p id="liveUpdated">${session?.last_event_at?`Last update ${new Date(session.last_event_at).toLocaleString()}`:active?'Listening for requests':'No active session'}</p></header><div class="telemetry-table"><div class="telemetry-table-head"><span>Time</span><span>Provider / Model</span><span>Status</span><span>Input</span><span>Output</span><span>Cost</span><span>Latency</span></div><div id="liveFeed">${items.map(liveRow).join('')||`<div class="request-empty">${active?'Gateway connected. Waiting for the first AI request...':'Start a session to observe gateway requests.'}</div>`}</div></div></section>`}
function modelBreakdown(items){const models=new Map;for(const row of items){const key=`${row.provider}/${row.model}`,value=models.get(key)||{provider:row.provider,model:row.model,requests:0,cost:0};value.requests++;value.cost+=row.estimated_cost||0;models.set(key,value)}if(models.size<2)return '';return `<section class="session-models"><span class="console-label">Session models</span><div>${[...models.values()].sort((a,b)=>b.requests-a.requests).map(x=>`<article><span><strong>${esc(x.model)}</strong><small>${esc(humanize(x.provider))}</small></span><strong>${number(x.requests)} requests</strong><strong>${money(x.cost)}</strong></article>`).join('')}</div></section>`}
function liveRow(row){const status=humanize(row.status),details=[['Provider',humanize(row.provider)],['Model',row.model],['Input tokens',number(row.input_tokens||0)],row.cached_tokens!=null?['Cached input',number(row.cached_tokens)]:null,['Output tokens',number(row.output_tokens||0)],row.estimated_cost!=null?['Total cost',money(row.estimated_cost)]:null,row.latency_ms!=null?['Latency',`${number(row.latency_ms)} ms`]:null,['Status',status],['Timestamp',new Date(row.timestamp).toLocaleTimeString()]].filter(Boolean);return `<details class="request-row"><summary><span>${new Date(row.timestamp).toLocaleTimeString()}</span><span><strong>${esc(row.model)}</strong><small>${esc(humanize(row.provider))}</small></span><span class="request-status ${esc(String(row.status).toLowerCase())}">${esc(status)}</span><span>${number(row.input_tokens||0)}</span><span>${number(row.output_tokens||0)}</span><span>${row.estimated_cost==null?'—':money(row.estimated_cost)}</span><span>${row.latency_ms==null?'—':`${number(row.latency_ms)} ms`}</span></summary><div class="request-detail"><strong>Request details</strong><dl>${details.map(([label,value])=>`<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join('')}</dl></div></details>`}
async function pricingPage() {
  const data=await api('/pricing'),rawItems=Array.isArray(data?.items)?data.items:[],items=rawItems.map(row=>({...row,pricing_category:row?.pricing_category||'UNKNOWN',lifecycle:row?.lifecycle||'UNKNOWN'})),providers=Array.isArray(data?.providers)?data.providers:[],categories=Array.isArray(data?.categories)?data.categories:[...new Set(items.map(row=>row.pricing_category).filter(value=>value&&value!=='UNKNOWN'))].sort();window.pricingCatalog=items;
  const prioritized=items.filter(x=>x.status!=='UNKNOWN'||x.lifecycle==='CURRENT');
  return shell(`${heading('Model Pricing', 'Compare verified provider prices. Tiers constrain candidate selection; they do not claim quality equivalence. Token prices are USD per 1 million tokens.')}<section class="panel"><form id="pricingFilters" class="inline"><label>Search models<input name="q" type="search" placeholder="Provider or model name"></label><label>Provider<select name="provider"><option value="">All providers</option>${providers.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select></label><label>Category<select name="category"><option value="">All categories</option>${categories.map(x=>`<option value="${esc(x)}">${esc(x.replace('_',' & '))}</option>`).join('')}</select></label><label>Sort<select name="sort"><option value="name">Recommended order</option><option value="input">Input price</option><option value="output">Output price</option></select></label><label><input name="missing" type="checkbox"> Missing prices only</label><label><input name="show_all" type="checkbox"> Show all models</label></form></section><section class="model-catalog" aria-label="Model pricing catalog"><div class="model-catalog-head" aria-hidden="true"><span>Provider</span><span>Model</span><span>Input / 1M</span><span>Cached / 1M</span><span>Output / 1M</span><span>Checked</span><span>Status</span></div><div id="pricingTable">${pricingRows(prioritized)}</div></section>`);
}
async function adminPricingPage(){const history=await api('/admin/pricing'),page=await pricingPage(),last=history.items?.[0],success=history.last_successful_refresh,schedule=history.schedule||{};const control=`<section class="panel model-refresh"><div class="panel-heading"><div><p class="eyebrow">MODEL DATA REFRESH</p><h2>Pricing &amp; Model Information</h2><p>Validated provider catalog data is maintained automatically and can be reviewed manually.</p></div><span class="badge">${last?last.success?'Current':'Failed':'Never Run'}</span></div><dl class="diagnostics"><dt>Last attempted refresh</dt><dd>${last?new Date(last.timestamp).toLocaleString():'Never'}</dd><dt>Last successful refresh</dt><dd>${success?new Date(success).toLocaleString():'Never'}</dd><dt>Automatic refresh</dt><dd>${schedule.enabled?`Enabled · Daily at ${String(schedule.hour).padStart(2,'0')}:00`:'Disabled'}</dd><dt>Next scheduled refresh</dt><dd>${schedule.next_run?new Date(schedule.next_run).toLocaleString():'—'}</dd></dl><button class="button primary" data-pricing-preview>Refresh Model Data</button><div id="pricingResult" role="status"></div><dialog id="pricingDialog"><h2>Apply refreshed model data?</h2><div id="pricingPreview"></div><button class="button" data-pricing-cancel>Cancel</button> <button class="button primary" data-pricing-apply>Apply Refresh</button></dialog></section>`;return page.replace('<section class="panel"><form id="pricingFilters"',`${control}<section class="panel"><form id="pricingFilters"`)}
const priceCell=value=>value==null?'—':money(value);
const humanize=value=>String(value||'Unknown').toLowerCase().split('_').map(word=>word.charAt(0).toUpperCase()+word.slice(1)).join(' ');
const dateLabel=value=>value?new Date(value).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}):'Not checked';
function capabilityRow(profile){const skills=Array.isArray(profile?.skills)?profile.skills.slice(0,4):[];if(!skills.length)return '';return `<section class="model-skills" aria-label="Model Skills and Talents"><header><strong>Skills &amp; Talents</strong><span class="badge" title="${esc(profile.score_explanation)}">${esc(humanize(profile.rating_type))}</span><span class="evidence-info" title="${esc(profile.score_explanation)}" aria-label="Capability score information">ⓘ</span></header><div class="model-skill-row">${skills.map(skill=>{const evidence=skill.score==null?'No benchmark evidence entered.':`${humanize(skill.rating_type)}; ${skill.confidence} confidence; ${skill.evidence_count} evidence record${skill.evidence_count===1?'':'s'}; benchmarks: ${(skill.benchmarks||[]).join(', ')}; provider-reported: ${skill.provider_reported?'yes':'no'}; independent: ${skill.independent?'yes':'no'}; last reviewed: ${skill.last_reviewed?new Date(skill.last_reviewed).toLocaleDateString():'unknown'}.`;return `<div class="model-skill" title="${esc(evidence)}"><span>${esc(skill.skill)}</span><strong>${skill.score==null?'Not scored':`${number(skill.score)}/100`}</strong>${skill.score==null?'':`<span class="skill-bar" aria-hidden="true"><i style="width:${Math.max(0,Math.min(100,skill.score))}%"></i></span>`}<small>${esc(humanize(skill.confidence))} confidence</small></div>`}).join('')}</div></section>`}
function capabilityPills(row){const values=Array.isArray(row.capabilities)?[...row.capabilities]:[];if(values.includes('SEARCH_GROUNDED')&&!values.includes('REAL_TIME_INFORMATION'))values.push('REAL_TIME_INFORMATION');return values.map(value=>`<span>${esc(humanize(value))}</span>`).join('')||'<span>Not documented</span>'}
function additionalPricing(row){const fees=row.additional_dimensions?.request_fee_per_1000;if(!fees||typeof fees!=='object')return '';return `<section class="additional-pricing"><strong>Additional pricing</strong><span>Request fee / 1,000 requests</span><div>${['low','medium','high'].filter(level=>fees[level]!=null).map(level=>`<span><small>${esc(humanize(level))}</small><strong>${money(fees[level])}</strong></span>`).join('')}</div></section>`}
function pricingRows(items){return items.length?items.map(row=>{const checked=row.effective_at||row.last_pricing_review,source=typeof row.pricing_source==='string'&&/^https:\/\//.test(row.pricing_source)?row.pricing_source:null;return `<article class="model-intel"><details><summary class="model-primary"><span class="model-provider">${esc(row.provider)}</span><span class="model-identity"><strong>${esc(row.display_name||row.model)}</strong><small>${esc(row.model_family||humanize(row.pricing_category))}</small></span><span class="model-price"><small>Input / 1M</small><strong>${priceCell(row.input_price_per_1m)}</strong></span><span class="model-price"><small>Cached / 1M</small><strong>${priceCell(row.cached_input_price_per_1m)}</strong></span><span class="model-price"><small>Output / 1M</small><strong>${priceCell(row.output_price_per_1m)}</strong></span><span class="model-checked"><small>Last checked</small><strong>${esc(dateLabel(checked))}</strong></span><span class="badge">${esc(humanize(row.status))}</span></summary><div class="model-expanded">${capabilityRow(row.capability_profile)}<section class="model-metadata"><dl><dt>Model family</dt><dd>${esc(row.model_family||'Not documented')}</dd><dt>Category</dt><dd>${esc(humanize(row.pricing_category))}</dd><dt>Suitability tier</dt><dd>${row.quality_tier?number(row.quality_tier):'Not rated'}</dd></dl><div><div class="model-detail-line"><span>Key capabilities</span><div class="capability-pills">${capabilityPills(row)}</div></div><div class="model-detail-line"><span>Availability</span><strong>${esc(humanize(row.availability))}</strong></div><div class="model-detail-line"><span>Last price check</span><strong>${esc(dateLabel(checked))}</strong></div></div></section><details class="model-secondary"><summary>View pricing details</summary><div>${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">View pricing source ↗</a>`:'<span>Pricing source unavailable</span>'}${row.context_window?`<span>Context window: ${number(row.context_window)} tokens</span>`:''}${row.canonical_pricing_model?`<span>Pricing inherited from ${esc(row.canonical_pricing_model)}</span>`:''}${additionalPricing(row)}</div></details></div></details></article>`}).join(''):'<p class="empty">No catalog models match these filters.</p>'}
async function adminDashboard() {
  const control=await api('/admin/control/overview'),m=control.metrics,h=control.health,p=control.plan;
  return adminShell('Administration',`Organization control plane for ${control.organization.name}.`,`<section class="metrics">${[['Members',`${number(m.members)} / ${p.limits.member_limit==null?'Unlimited':number(p.limits.member_limit)}`],['Providers',`${number(m.providers)} / ${p.limits.provider_limit==null?'Unlimited':number(p.limits.provider_limit)}`],['Catalog models',m.catalog_models],['Active imports',m.active_imports],['Telemetry events',m.telemetry_events],['Current plan',p.id]].map(([l,v])=>`<article><span>${esc(l)}</span><strong>${esc(v)}</strong></article>`).join('')}</section><section class="provider-grid">${Object.entries(h).map(([name,status])=>`<article class="panel provider-card"><div><h2>${esc(name.replaceAll('_',' '))}</h2><span class="badge">${esc(status)}</span></div></article>`).join('')}</section>`);
  /* Legacy platform dashboard remains below while its controls are migrated. */
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
  return page.replace('</header>','</header>'+adminNav()).replace('<section class="panel form-panel"><h2>Telemetry data</h2>',`${pricingPanel}<section class="panel form-panel"><h2>Telemetry data</h2>`);
}
async function adminMembers(){const data=await api('/admin/control/members');return adminShell('Members','Manage organization membership and pending invitations.',`<section class="panel form-panel"><h2>Invite member</h2><form id="inviteForm" class="admin-action-form"><label>Email<input name="email" type="email" required></label><label>Role<select name="role"><option>ANALYST</option><option>VIEWER</option><option>ADMIN</option></select></label><button class="button primary">Create invitation</button><p class="help">Email delivery is not configured. The invitation becomes available for the matching registered identity.</p><p id="formStatus" role="status"></p></form></section><section class="panel table-wrap"><h2>Active members</h2><table><thead><tr><th>Member</th><th>Role</th><th>Status</th><th>Joined</th><th>Last active</th></tr></thead><tbody>${data.items.map(x=>`<tr><td>${esc(x.display_name)}<small>${esc(x.email)}</small></td><td>${esc(x.role)}</td><td><span class="badge">${esc(x.status)}</span></td><td>${new Date(x.joined_at).toLocaleDateString()}</td><td>${x.last_active_at?new Date(x.last_active_at).toLocaleString():'Unavailable'}</td></tr>`).join('')}</tbody></table></section><section class="panel"><h2>Invitations</h2>${data.invitations.length?data.invitations.map(x=>`<div class="admin-list-row"><span><strong>${esc(x.email)}</strong><small>${esc(x.role)} · expires ${new Date(x.expires_at).toLocaleDateString()}</small></span><span class="badge">${esc(x.status)}</span></div>`).join(''):'<p class="empty">No invitations.</p>'}</section>`)}
async function adminOrganization(){const data=await api('/admin/control/organization'),org=data.organization;return adminShell('Organization','Manage this SaaS account boundary.',`<section class="panel form-panel"><form id="organizationForm"><label>Organization name<input name="name" value="${esc(org.name)}" required maxlength="120"></label><label>Telemetry retention days<input name="retention_days" type="number" min="7" max="3650" value="${esc(org.settings?.retention_days||'')}"></label><button class="button primary">Save organization</button><p id="formStatus" role="status"></p></form><dl class="diagnostics"><dt>Organization ID</dt><dd>${esc(org.id)}</dd><dt>Status</dt><dd>${esc(org.status)}</dd><dt>Your role</dt><dd>${esc(org.role)}</dd></dl></section>`)}
async function adminMembership(){const data=await api('/admin/control/membership'),p=data.plan,u=data.usage,limit=k=>p.limits[k]==null?'Unlimited':number(p.limits[k]);return adminShell('Membership','Plan and entitlement foundation; payment processing is not enabled.',`<section class="metrics">${[['Current plan',p.id],['Plan status',p.status],['Members',`${number(u.members)} / ${limit('member_limit')}`],['Providers',`${number(u.providers)} / ${limit('provider_limit')}`],['Telemetry',`${number(u.telemetry_events)} / ${limit('telemetry_event_limit')}`],['Retention',p.limits.retention_days==null?'Unlimited':`${number(p.limits.retention_days)} days`]].map(([l,v])=>`<article><span>${esc(l)}</span><strong>${esc(v)}</strong></article>`).join('')}</section><section class="panel"><h2>Available features</h2><div class="tag-list">${p.features.map(x=>`<span class="badge">${esc(x.replaceAll('_',' '))}</span>`).join('')}</div><p class="help">Plan changes and checkout are intentionally unavailable in this release.</p></section>`)}
async function adminUsage(){const d=await api('/admin/control/usage');return adminShell('Usage','Actual organization activity and measurable plan consumption.',`<section class="metrics">${[['Telemetry events',d.telemetry_events],['Imports this month',d.imports_this_month],['Imported rows',d.total_imported_rows],['Provider connections',d.provider_connections],['Members',d.members],['Forecast runs',d.forecast_runs],['Simulation runs',d.simulation_runs]].map(([l,v])=>`<article><span>${l}</span><strong>${number(v)}</strong></article>`).join('')}</section>`)}
async function adminSecurity(){const d=await api('/admin/control/sessions');return adminShell('Security','Review hashed server-side sessions without exposing tokens.',`<section class="panel"><div class="panel-heading"><div><h2>Active sessions</h2><p>Device fingerprinting and geographic tracking are not collected.</p></div><button class="button" data-signout-others>Sign Out All Other Sessions</button></div>${d.items.map(x=>`<div class="admin-list-row"><span><strong>${esc(x.client_summary)}</strong><small>Created ${new Date(x.created_at).toLocaleString()} · expires ${new Date(x.expires_at).toLocaleString()}</small></span><span class="badge">${x.current?'CURRENT':'ACTIVE'}</span></div>`).join('')||'<p class="empty">No active sessions.</p>'}<p id="securityStatus" role="status"></p></section>`)}
async function adminNotifications(){const d=await api('/admin/control/notifications'),events=['budget_threshold','projected_budget','provider_invalid','import_failed','worker_unhealthy','pricing_stale','anomaly_detected','member_activity','critical_configuration'];return adminShell('Notifications','Store in-app notification preferences. Outbound channels are not configured.',`<section class="panel form-panel"><form id="notificationForm">${events.map(x=>`<label class="check-row"><input type="checkbox" name="${x}" ${d.preferences[x]?'checked':''}> ${esc(x.replaceAll('_',' '))}</label>`).join('')}<button class="button primary">Save preferences</button><p id="formStatus" role="status"></p></form></section>`)}
async function adminDataPrivacy(){const org=await api('/admin/control/organization');return adminShell('Data & Privacy','Organization data controls with destructive-action safeguards.',`<section class="panel"><h2>Data summary</h2><p>Retention policy: ${org.organization.settings?.retention_days?`${number(org.organization.settings.retention_days)} days`:'Plan default'}. Temporary import artifacts are removed after import cleanup.</p></section><section class="panel"><h2>Clear telemetry data</h2><p>Deletes telemetry, import history, derived forecasts, and live sessions. Preserves accounts, organization membership, provider configuration, budgets, integrations, and pricing configuration.</p><button class="button destructive" data-reset>Clear Telemetry Data</button><p id="resetStatus" role="status"></p></section><dialog id="clearTelemetryDialog"><h2>Clear telemetry data?</h2><p>This action cannot be undone. Derived forecasts will also be deleted.</p><button class="button" data-clear-cancel>Cancel</button> <button class="button destructive" data-clear-confirm>Clear Telemetry</button></dialog>`)}
async function adminProviders(){const data=await api('/providers'),supported=new Set((data.supported||[]).map(x=>x.provider));const names=['openai','anthropic','google','xai','mistral','deepseek','cohere','perplexity'];return adminShell('Providers','Persistent credentials are encrypted server-side and never returned to the browser.',`<section class="provider-grid">${names.map(name=>{const row=data.items.find(x=>x.provider===name),available=supported.has(name);return `<article class="panel provider-card"><div><h2>${esc(name)}</h2><span class="badge">${esc(row?.status||'NOT_CONNECTED')}</span></div><p>${row?.masked_identifier?`Credential ${esc(row.masked_identifier)}`:'No credential stored.'}</p><p class="help">${available?'Connection adapter available.':'Catalog supported; credential adapter unavailable.'}</p>${available&&name==='openai'?`<form id="openaiConnect"><label>${row?'Replace API Key':'API Key'}<input name="credential" type="password" autocomplete="off" required></label><button class="button primary">${row?'Replace':'Connect API Key'}</button></form>${row?'<button class="button" data-provider-validate>Test</button> <button class="button destructive" data-provider-disconnect>Remove</button>':''}`:''}</article>`}).join('')}</section><p id="providerStatus" role="status"></p>`)}
async function adminUsers() {
  const params = new URLSearchParams(location.search),
    q = params.get('q') || '',
    data = await api(`/admin/users?q=${encodeURIComponent(q)}`);
  return shell(`${heading('User Administration', 'Search, activate, deactivate, and assign roles.')}<section class="panel"><form id="userSearch" class="inline"><label>Search users<input name="q" value="${esc(q)}"></label><button class="button">Search</button></form><div class="table-wrap"><table><thead><tr><th>Profile</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Last login</th><th>Actions</th></tr></thead><tbody>${data.items.map((user) => `<tr><td><strong>${esc(user.display_name)}</strong><small>@${esc(user.username)}</small></td><td>${esc(user.email)}</td><td>${user.role}</td><td>${user.is_active ? 'Active' : 'Disabled'}</td><td>${new Date(user.created_at).toLocaleDateString()}</td><td>${user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td><td><button class="table-button" data-user-action="${user.id}" data-active="${!user.is_active}">${user.is_active ? 'Disable' : 'Enable'}</button><button class="table-button" data-user-role="${user.id}" data-role="${user.role === 'ADMIN' ? 'ANALYST' : 'ADMIN'}">Make ${user.role === 'ADMIN' ? 'Analyst' : 'Admin'}</button></td></tr>`).join('')}</tbody></table></div><p id="formStatus" role="alert"></p></section>`, true);
}
async function adminAudit() {
  const params=new URLSearchParams(location.search),q=params.get('q')||'',outcome=params.get('outcome')||'',data=await api(`/admin/control/audit?${params}`);
  return adminShell('Audit Log','Organization-scoped security and administrative events without sensitive values.',`<section class="panel"><form id="auditFilter" class="inline"><label>Search<input name="q" type="search" value="${esc(q)}"></label><label>Outcome<select name="outcome"><option value="">All</option><option ${outcome==='success'?'selected':''}>success</option><option ${outcome==='failure'?'selected':''}>failure</option></select></label><button class="button">Filter</button></form><div class="table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>Outcome</th><th>Resource</th></tr></thead><tbody>${data.items.map((row) => `<tr><td>${new Date(row.timestamp).toLocaleString()}</td><td>${esc(row.action)}</td><td><span class="badge">${esc(row.outcome)}</span></td><td>${esc(row.resource_type)}</td></tr>`).join('')}</tbody></table></div></section>`);
}
async function system() {
  const data = await api('/admin/control/system');
  return adminShell('System Diagnostics','Credential-free operational health for administrators.',`<section class="metrics">${[
      ['Queued', data.worker.queued],['Active',data.worker.running],['Failed last 24h',data.imports.failed_24h],['Catalog providers',data.pricing.providers],
    ]
      .map(([l, v]) => `<article><span>${l}</span><strong>${number(v)}</strong></article>`)
      .join('')}</section><section class="panel table-wrap"><h2>Workers</h2>${data.worker.instances.length ? `<table><thead><tr><th>Worker</th><th>Status</th><th>Current job</th><th>Last heartbeat</th></tr></thead><tbody>${data.worker.instances.map((w) => `<tr><td>${esc(w.worker_id)}</td><td><span class="badge">${esc(w.status)}</span></td><td>${esc(w.current_job_id || 'None')}</td><td>${new Date(w.last_heartbeat_at).toLocaleString()}</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No workers have registered. Worker status is unavailable.</p>'}</section><section class="panel"><dl class="diagnostics"><dt>API</dt><dd>${data.health.api}</dd><dt>Database</dt><dd>${data.health.database}</dd><dt>Telemetry pipeline</dt><dd>${data.health.telemetry_pipeline}</dd><dt>Pricing catalog</dt><dd>${data.health.pricing_catalog}</dd><dt>Storage</dt><dd>${data.health.storage}</dd><dt>Gateway</dt><dd>${data.health.gateway}</dd><dt>Oldest queued job</dt><dd>${data.worker.oldest_job_at ? new Date(data.worker.oldest_job_at).toLocaleString() : 'None'}</dd></dl></section>`,
  );
}
async function render() {
  const path = location.pathname;
  if(liveSource){liveSource.close();liveSource=null}
  if(liveTimer){clearInterval(liveTimer);liveTimer=null}
  stopDemo();
  app.innerHTML = '<main id="main" class="loading" role="status">Loading…</main>';
  if(path==='/book-demo'||path==='/demo'){currentUser=null;app.innerHTML=demoPage();wire();wireDemo();return}
  if(path==='/signup'||path==='/register'){currentUser=null;app.innerHTML=signupRequestPage();wire();wireDemo();return}
  try {
    currentUser = (await api('/auth/me')).user;
  } catch {
    currentUser = null;
  }
  if (routes.public.has(path)) {
    if (currentUser && path !== '/') return navigate(authenticatedHome(currentUser));
    app.innerHTML = path === '/' ? await landing() : authPage(path.slice(1)).replace('>Sign Up</a>','>Sign Up Request</a>');
    return wire();
  }
  if (!currentUser) return navigate('/login');
  if (routes.admin.has(path) && !canAdmin(currentUser)) return navigate('/app/overview');
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
    else if (path === '/admin/members') app.innerHTML = await adminMembers();
    else if (path === '/admin/organization') app.innerHTML = await adminOrganization();
    else if (path === '/admin/providers') app.innerHTML = await adminProviders();
    else if (path === '/admin/membership') app.innerHTML = await adminMembership();
    else if (path === '/admin/usage') app.innerHTML = await adminUsage();
    else if (path === '/admin/budgets') app.innerHTML = await budgetsPage();
    else if (path === '/admin/pricing') app.innerHTML = await adminPricingPage();
    else if (path === '/admin/data-privacy') app.innerHTML = await adminDataPrivacy();
    else if (path === '/admin/security') app.innerHTML = await adminSecurity();
    else if (path === '/admin/notifications') app.innerHTML = await adminNotifications();
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
  document.querySelector('#inviteForm')?.addEventListener('submit',event=>simpleSubmit(event,'/admin/control/invitations',x=>({...x,expires_days:7})));
  document.querySelector('#organizationForm')?.addEventListener('submit',event=>simpleSubmit(event,'/admin/control/organization',x=>({name:x.name,retention_days:x.retention_days?Number(x.retention_days):null}),'PATCH'));
  document.querySelector('#notificationForm')?.addEventListener('submit',event=>simpleSubmit(event,'/admin/control/notifications',x=>({preferences:Object.fromEntries(['budget_threshold','projected_budget','provider_invalid','import_failed','worker_unhealthy','pricing_stale','anomaly_detected','member_activity','critical_configuration'].map(key=>[key,key in x]))}),'PUT'));
  document.querySelector('#auditFilter')?.addEventListener('submit',event=>{event.preventDefault();const params=new URLSearchParams(new FormData(event.currentTarget));navigate(`/admin/audit?${params}`)});
  document.querySelector('[data-signout-others]')?.addEventListener('click',async()=>{const target=document.querySelector('#securityStatus');try{const result=await api('/admin/control/sessions/others',{method:'DELETE'});target.textContent=`Signed out ${number(result.revoked)} other sessions.`}catch(error){target.textContent=error.message}});
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
  if(location.pathname==='/app/live' && document.querySelector('[data-live-stop]')){startLiveStream();const clock=document.querySelector('[data-session-clock]'),started=clock?.dataset.started;liveTimer=setInterval(()=>{if(clock&&started)clock.textContent=elapsedLabel({started_at:started,status:'ACTIVE'})},1000)}
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
    if (location.pathname === '/signup' || location.pathname === '/register') {
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
  liveSource=new EventSource('/api/v1/live/stream');liveSource.addEventListener('telemetry',async()=>{const dashboard=document.querySelector('#liveDashboard');if(!dashboard)return;const snapshot=await api('/live/snapshot');dashboard.innerHTML=liveDashboard(snapshot.session,snapshot.metrics||{},snapshot.items||[])});liveSource.addEventListener('session',()=>render());
}
let pendingPricing=null;
async function previewPricing(){
  const refreshButton=document.querySelector('[data-pricing-preview]');refreshButton.disabled=true;refreshButton.setAttribute('aria-busy','true');
  const target=document.querySelector('#pricingResult');try{pendingPricing=await api('/admin/pricing/refresh',{method:'POST',body:JSON.stringify({provider:'openai',apply:false})});const increased=pendingPricing.changes.filter(x=>x.dimensions.some(d=>d.direction==='INCREASED')).length,decreased=pendingPricing.changes.filter(x=>x.dimensions.some(d=>d.direction==='DECREASED')).length;document.querySelector('#pricingPreview').innerHTML=`<p>OpenAI: ${number(pendingPricing.models_discovered)} discovered; ${number(pendingPricing.current_models)} current; ${number(pendingPricing.legacy_models)} legacy; ${number(pendingPricing.priced_models)} priced; ${number(pendingPricing.models_missing_pricing.length)} unknown; ${number(pendingPricing.new_models_discovered.length)} new; ${number(pendingPricing.models_removed_or_unavailable.length)} unavailable; ${number(pendingPricing.alias_resolved_models)} alias-resolved; ${number(pendingPricing.non_token_models)} non-token categories; ${number(increased)} increased; ${number(decreased)} decreased; ${number(pendingPricing.manual_overrides_protecting_effective_price.length)} protected by overrides.</p><p>Model source: ${esc(pendingPricing.model_catalog_source)}<br>Pricing source: ${esc(pendingPricing.pricing_source_label)}<br>Last pricing review: ${new Date(pendingPricing.last_pricing_review).toLocaleDateString()}</p>${pendingPricing.anomalies_requiring_review.length?'<p role="alert">Unusually large changes are flagged and require explicit confirmation.</p>':''}`;document.querySelector('#pricingDialog').showModal()}catch(error){target.textContent=error.message}
  refreshButton.disabled=false;refreshButton.removeAttribute('aria-busy');
}
async function applyPricing(){
  const target=document.querySelector('#pricingResult');try{const result=await api('/admin/pricing/refresh',{method:'POST',body:JSON.stringify({provider:'openai',apply:true,confirm_anomalies:Boolean(pendingPricing?.anomalies_requiring_review.length)})});document.querySelector('#pricingDialog').close();target.textContent=`Applied catalog refresh: ${number(result.models_changed)} changed, ${number(result.models_added)} added, ${number(result.models_unchanged)} unchanged.`}catch(error){target.textContent=error.message}
}
function filterPricing(event){const form=event.currentTarget,q=form.q.value.toLowerCase(),provider=form.provider.value,category=form.category.value,missing=form.missing.checked,showAll=form.show_all.checked,sort=form.sort.value;let items=window.pricingCatalog.filter(x=>(!q||`${x.provider} ${x.model} ${x.display_name||''}`.toLowerCase().includes(q))&&(!provider||x.provider===provider)&&(!category||x.pricing_category===category)&&(!missing||x.status==='UNKNOWN')&&(showAll||missing||x.status!=='UNKNOWN'||x.lifecycle==='CURRENT'));items.sort(sort==='input'?(a,b)=>(a.input_price_per_1m??Infinity)-(b.input_price_per_1m??Infinity):sort==='output'?(a,b)=>(a.output_price_per_1m??Infinity)-(b.output_price_per_1m??Infinity):(a,b)=>(a.status==='UNKNOWN')-(b.status==='UNKNOWN')||(a.lifecycle!=='CURRENT')-(b.lifecycle!=='CURRENT')||a.provider.localeCompare(b.provider)||a.model.localeCompare(b.model));document.querySelector('#pricingTable').innerHTML=pricingRows(items)}
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
async function simpleSubmit(event, path, transform = (x) => x, method = 'POST') {
  event.preventDefault();
  const status = event.currentTarget.querySelector('#formStatus'),
    data = transform(Object.fromEntries(new FormData(event.currentTarget)));
  try {
    await api(path, { method, body: JSON.stringify(data) });
    render();
  } catch (error) {
    status.textContent = error.message;
  }
}
render();
