import './request.css';

const clean = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const csrf = () => document.cookie.split('; ').find((row) => row.startsWith('aiopt_csrf='))?.split('=').slice(1).join('=') || '';

// Old registration links and direct /register visits now enter the approval flow.
if (location.pathname === '/register') history.replaceState({}, '', '/demo#access');

function protectPublicSurface() {
  document.querySelectorAll('a[href="/register"]').forEach((link) => { link.setAttribute('href', '/demo#access'); link.textContent = 'Request Access'; });
  document.querySelectorAll('a[href="/demo"]').forEach((link) => { if (!link.classList.contains('brand')) link.textContent = 'Book a Demo'; });
  const showcase = document.querySelector('.demo-showcase');
  if (showcase && !showcase.dataset.privateDemoCopy) {
    showcase.dataset.privateDemoCopy = 'true';
    const eyebrow = showcase.querySelector('.eyebrow'), heading = showcase.querySelector('h2'), paragraphs = showcase.querySelectorAll('p');
    if (eyebrow) eyebrow.textContent = 'PRIVATE PRODUCT DEMONSTRATION';
    if (heading) heading.textContent = 'See CutAIcost in a guided session.';
    if (paragraphs[1]) paragraphs[1].textContent = 'Product demonstrations are available by request. The working dashboard and internal workflows are not exposed publicly.';
    if (paragraphs[2]) paragraphs[2].textContent = 'Private walkthrough · Access by approval';
  }
}

let ticketLoading = false;
async function ticketApi(path = '', options = {}) {
  const method = options.method || 'GET';
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(method === 'GET' ? {} : { 'X-CSRF-Token': decodeURIComponent(csrf()) }) };
  const response = await fetch(`/api/v1/platform/request-tickets${path}`, { ...options, headers, credentials: 'same-origin' });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Unable to load request tickets.');
  return payload;
}

function ticketRows(items) {
  return items.map((ticket) => `<article class="admin-ticket" data-ticket-id="${clean(ticket.id)}">
    <button class="admin-ticket-summary" type="button" data-ticket-open="${clean(ticket.id)}" aria-expanded="false">
      <span><strong>${clean(ticket.ticket_number)}</strong><small>${clean(ticket.request_type)} · ${clean(ticket.name || 'Unknown')} · ${clean(ticket.company || 'No company')}</small></span>
      <span><span class="badge ticket-status-${clean(ticket.status).toLowerCase()}">${clean(ticket.status)}</span><small>${new Date(ticket.created_at).toLocaleString()}</small></span>
    </button>
    <div class="admin-ticket-detail" data-ticket-detail="${clean(ticket.id)}" hidden>
      <dl class="ticket-details">
        <dt>Name</dt><dd>${clean(ticket.name || '—')}</dd>
        <dt>Email</dt><dd><a href="mailto:${clean(ticket.email || '')}">${clean(ticket.email || '—')}</a></dd>
        <dt>Company</dt><dd>${clean(ticket.company || '—')}</dd>
        <dt>Role</dt><dd>${clean(ticket.role || '—')}</dd>
        <dt>Monthly AI spend</dt><dd>${clean(ticket.ai_spend_range || 'Not provided')}</dd>
        <dt>Preferred contact</dt><dd>${clean(ticket.preferred_contact || 'Email')}</dd>
        <dt>Providers</dt><dd>${clean(ticket.providers || 'Not provided')}</dd>
        <dt>Goals / request</dt><dd class="ticket-goals">${clean(ticket.goals || '—')}</dd>
      </dl>
      <form class="ticket-update-form" data-ticket-update="${clean(ticket.id)}">
        <label>Status<select name="status">${['NEW','CONTACTED','QUALIFIED','SCHEDULED','APPROVED','DENIED','CLOSED'].map((value) => `<option value="${value}" ${ticket.status === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
        <label>Admin Notes<textarea name="admin_notes" maxlength="3000" rows="4" placeholder="Internal notes only">${clean(ticket.admin_notes || '')}</textarea></label>
        <button class="button primary" type="submit">Save Ticket</button>
        <p class="ticket-update-status" role="status"></p>
      </form>
    </div>
  </article>`).join('');
}

async function enhanceAdminTickets() {
  if (location.pathname !== '/admin' || ticketLoading) return;
  const workspace = document.querySelector('.workspace');
  if (!workspace || workspace.querySelector('[data-request-tickets]')) return;
  ticketLoading = true;
  try {
    const data = await ticketApi();
    const adminLink = document.querySelector('.sidebar a[href="/admin"]');
    if (adminLink && data.new_count) {
      adminLink.innerHTML = `Administration <span class="ticket-nav-count" aria-label="${data.new_count} new requests">${data.new_count}</span>`;
    }
    const adminNav = workspace.querySelector('.admin-nav');
    if (adminNav) {
      const badge = document.createElement('span');
      badge.className = 'admin-nav-ticket-alert';
      badge.textContent = data.new_count ? `${data.new_count} new request${data.new_count === 1 ? '' : 's'}` : 'No new requests';
      adminNav.insertAdjacentElement('afterend', badge);
    }
    const section = document.createElement('section');
    section.className = 'panel request-ticket-panel';
    section.dataset.requestTickets = 'true';
    section.innerHTML = `<div class="panel-heading"><div><p class="eyebrow">INCOMING REQUESTS</p><h2>Demo & Access Tickets</h2><p>New demo and account-access requests appear here for platform administrators.</p></div><div class="ticket-counts"><strong>${data.new_count}</strong><span>New</span><small>${data.total} total</small></div></div><div class="ticket-filters"><button class="table-button" data-ticket-filter="ALL">All</button><button class="table-button" data-ticket-filter="NEW">New</button><button class="table-button" data-ticket-filter="DEMO">Demo</button><button class="table-button" data-ticket-filter="ACCESS">Access</button></div><div class="ticket-list">${data.items.length ? ticketRows(data.items) : '<p class="empty">No demo or access requests yet.</p>'}</div>`;
    const navAnchor = workspace.querySelector('.admin-nav');
    if (navAnchor) navAnchor.insertAdjacentElement('afterend', section); else workspace.prepend(section);
  } catch (error) {
    // Organization admins are intentionally denied; only platform admins see lead tickets.
    if (!/403|administrator|Authentication/i.test(error.message)) console.warn('Request tickets unavailable:', error.message);
  } finally {
    ticketLoading = false;
  }
}

const publicObserver = new MutationObserver(() => { protectPublicSurface(); enhanceAdminTickets(); });
if (document.body) publicObserver.observe(document.body, { childList: true, subtree: true });

document.addEventListener('click', (event) => {
  const signup = event.target.closest('a[href="/register"], a[href="/demo#access"]');
  if (signup) {
    event.preventDefault(); event.stopImmediatePropagation(); history.pushState({}, '', '/demo#access'); window.dispatchEvent(new PopStateEvent('popstate')); return;
  }
  const opener = event.target.closest('[data-ticket-open]');
  if (opener) {
    const detail = document.querySelector(`[data-ticket-detail="${CSS.escape(opener.dataset.ticketOpen)}"]`);
    if (detail) { detail.hidden = !detail.hidden; opener.setAttribute('aria-expanded', String(!detail.hidden)); }
    return;
  }
  const filter = event.target.closest('[data-ticket-filter]');
  if (filter) {
    const value = filter.dataset.ticketFilter;
    document.querySelectorAll('.admin-ticket').forEach((row) => {
      const text = row.textContent || '';
      row.hidden = value !== 'ALL' && !text.includes(value);
    });
  }
}, true);

document.addEventListener('submit', async (event) => {
  const form = event.target.closest('[data-ticket-update]');
  if (!form) return;
  event.preventDefault(); event.stopImmediatePropagation();
  const status = form.querySelector('.ticket-update-status');
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true; status.textContent = 'Saving…';
  try {
    const data = Object.fromEntries(new FormData(form));
    await ticketApi(`/${encodeURIComponent(form.dataset.ticketUpdate)}`, { method: 'PATCH', body: JSON.stringify(data) });
    status.textContent = 'Ticket updated.';
    const panel = document.querySelector('[data-request-tickets]');
    panel?.remove();
    document.querySelector('.admin-nav-ticket-alert')?.remove();
    await enhanceAdminTickets();
  } catch (error) {
    status.textContent = error.message; button.disabled = false;
  }
}, true);

const demoHeader = () => `<header class="demo-nav request-nav"><a href="/" data-route class="brand">CutAIcost</a><nav><a href="/" data-route>Back to Home</a><a href="/login" data-route>Sign In</a></nav></header>`;
const field = (label, input) => `<label>${clean(label)}${input}</label>`;
function requestForm(type) {
  const isDemo = type === 'DEMO';
  return `<form class="request-form" data-public-request="${type}"><input type="hidden" name="request_type" value="${type}"><input class="request-honeypot" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="request-form-grid">${field('Name', '<input name="name" autocomplete="name" maxlength="100" required>')}${field('Work Email', '<input name="email" type="email" autocomplete="email" maxlength="320" required>')}${field('Company', '<input name="company" autocomplete="organization" maxlength="120" required>')}${field('Role / Job Title', '<input name="role" autocomplete="organization-title" maxlength="120" required>')}${field('Approximate Monthly AI Spend', '<select name="ai_spend_range" required><option value="">Select a range</option><option>Under $1,000</option><option>$1,000–$10,000</option><option>$10,000–$50,000</option><option>$50,000–$250,000</option><option>$250,000+</option></select>')}${field('Preferred Contact', '<select name="preferred_contact" required><option>Email</option><option>Phone / video call</option></select>')}</div>${field('AI Providers Currently Used', '<input name="providers" maxlength="300" placeholder="OpenAI, Anthropic, Gemini, etc." required>')}${field(isDemo ? 'What would you like to review with us?' : 'What are you hoping to use CutAIcost for?', '<textarea name="goals" maxlength="1500" rows="5" required></textarea>')}<button class="button primary request-submit" type="submit">${isDemo ? 'Request a Demo' : 'Request Access'}</button><p class="request-status" role="status" aria-live="polite"></p></form>`;
}
export function demoPage() { return `${demoHeader()}<main id="main" class="request-shell"><section class="request-hero"><p class="eyebrow">PRIVATE PRODUCT ACCESS</p><h1>See CutAIcost with us.</h1><p>We do not expose the working product, dashboards, or internal workflows through a public demo. Tell us what you are evaluating and we will follow up for a private walkthrough or account access.</p><div class="request-trust"><span>Private walkthrough</span><span>No public dashboard</span><span>Access by approval</span></div></section><section class="request-options" aria-label="Demo and access requests"><article class="request-card" id="book-demo"><p class="eyebrow">BOOK A DEMO</p><h2>Request a private demonstration</h2><p>Meet with us for a guided overview tailored to your organization. No customer credentials or production telemetry are required to request a meeting.</p>${requestForm('DEMO')}</article><article class="request-card" id="access"><p class="eyebrow">REQUEST ACCESS</p><h2>Interested in an account?</h2><p>Public self-registration is closed. Submit an access request and we will review it before account enrollment.</p>${requestForm('ACCESS')}</article></section><section class="request-privacy"><strong>Private by design.</strong><span>Submitting this form does not connect an AI provider, upload telemetry, or grant access to the CutAIcost application.</span></section></main>`; }
export function stopDemo() {}
async function submitRequest(event) {
  event.preventDefault(); const form = event.currentTarget, button = form.querySelector('button[type="submit"]'), status = form.querySelector('.request-status'), data = Object.fromEntries(new FormData(form)); button.disabled = true; status.textContent = 'Sending request…';
  try { const response = await fetch('/api/v1/public/requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify(data) }); const payload = await response.json().catch(() => ({})); if (!response.ok) { const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join('. ') : payload.detail; throw new Error(typeof detail === 'string' ? detail : 'Unable to submit your request.'); } form.reset(); status.textContent = `${data.request_type === 'DEMO' ? 'Demo' : 'Access'} request received${payload.ticket_number ? ` as ${payload.ticket_number}` : ''}. We will follow up with you.`; }
  catch (error) { status.textContent = error.message || 'Unable to submit your request.'; button.disabled = false; }
}
export function wireDemo() { protectPublicSurface(); document.querySelectorAll('[data-public-request]').forEach((form) => form.addEventListener('submit', submitRequest)); if (location.hash === '#access') requestAnimationFrame(() => document.querySelector('#access')?.scrollIntoView({ block: 'start' })); }
