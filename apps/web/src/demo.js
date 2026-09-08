import './request.css';

const clean = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const csrf = () => document.cookie.split('; ').find((row) => row.startsWith('aiopt_csrf='))?.split('=').slice(1).join('=') || '';

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
        <dt>Email</dt><dd><a href="mailto:${clean(ticket.email || '')}">Email Requester · ${clean(ticket.email || '—')}</a></dd>
        <dt>Company</dt><dd>${clean(ticket.company || '—')}</dd>
        <dt>Job title</dt><dd>${clean(ticket.role || '—')}</dd><dt>Phone</dt><dd>${clean(ticket.phone || 'Not provided')}</dd>
        <dt>Company size</dt><dd>${clean(ticket.company_size || 'Not provided')}</dd>
        <dt>Monthly AI spend</dt><dd>${clean(ticket.ai_spend_range || 'Not provided')}</dd>
        <dt>Preferred contact</dt><dd>${clean(ticket.preferred_contact || 'Email')}</dd>
        <dt>Providers</dt><dd>${clean(ticket.providers || 'Not provided')}</dd>
        <dt>Goals / request</dt><dd class="ticket-goals">${clean(ticket.goals || '—')}</dd>
        <dt>Additional details</dt><dd class="ticket-goals">${clean(ticket.message || 'None')}</dd>
      </dl>
      <form class="ticket-update-form" data-ticket-update="${clean(ticket.id)}">
        <label>Status<select name="status">${['NEW','CONTACTED','IN_DISCUSSION','SCHEDULED','COMPLETED','APPROVED','DECLINED','CLOSED'].map((value) => `<option value="${value}" ${ticket.status === value ? 'selected' : ''}>${value.replaceAll('_',' ')}</option>`).join('')}</select></label>
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
    const requests = data.items;
    section.innerHTML = `<div class="panel-heading"><div><p class="eyebrow">INCOMING REQUESTS</p><h2>Client Requests</h2><p>Signup and consultation requests are available only to platform administrators.</p></div><div class="ticket-counts"><strong>${requests.filter((ticket) => ticket.status === 'NEW').length}</strong><span>New</span><small>${requests.length} total</small></div></div><div class="ticket-filters"><button class="table-button" data-ticket-filter="ALL">All</button><button class="table-button" data-ticket-filter="SIGNUP_REQUEST">Sign Up</button><button class="table-button" data-ticket-filter="CONSULTATION_REQUEST">Consultation</button><button class="table-button" data-ticket-filter="NEW">New</button><button class="table-button" data-ticket-filter="CONTACTED">Contacted</button><button class="table-button" data-ticket-filter="APPROVED">Approved</button><button class="table-button" data-ticket-filter="DECLINED">Declined</button><button class="table-button" data-ticket-filter="CLOSED">Closed</button></div><div class="ticket-list">${requests.length ? ticketRows(requests) : '<p class="empty">No client requests yet.</p>'}</div>`;
    const navAnchor = workspace.querySelector('.admin-nav');
    if (navAnchor) navAnchor.insertAdjacentElement('afterend', section); else workspace.prepend(section);
  } catch (error) {
    // Organization admins are intentionally denied; only platform admins see lead tickets.
    if (!/403|administrator|Authentication/i.test(error.message)) console.warn('Request tickets unavailable:', error.message);
  } finally {
    ticketLoading = false;
  }
}

const publicObserver = new MutationObserver(() => { enhanceAdminTickets(); });
if (document.body) publicObserver.observe(document.body, { childList: true, subtree: true });

document.addEventListener('click', (event) => {
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

const demoHeader = () => `<header class="demo-nav request-nav"><a href="/" data-route class="brand">CutAIcost</a><nav><a href="/" data-route>Home</a><a href="/signup" data-route>Sign Up Request</a><a href="/login" data-route>Sign In</a></nav></header>`;
const field = (label, input) => `<label>${clean(label)}${input.replace('maxlength="120>','maxlength="120">')}</label>`;
function requestForm() {
  return `<form class="request-form" data-public-request="DEMO"><input type="hidden" name="request_type" value="DEMO"><input class="request-honeypot" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="request-form-grid">${field('Full Name', '<input name="name" autocomplete="name" maxlength="100" required>')}${field('Work Email', '<input name="email" type="email" autocomplete="email" maxlength="320" required>')}${field('Company / Organization', '<input name="company" autocomplete="organization" maxlength="120" required>')}${field('Job Title', '<input name="role" autocomplete="organization-title" maxlength="120" required>')}${field('Company Size', '<select name="company_size" required><option value="">Select company size</option><option>1–10</option><option>11–50</option><option>51–200</option><option>201–1,000</option><option>1,001+</option></select>')}${field('Estimated Monthly AI/API Spend', '<select name="ai_spend_range" required><option value="">Select a range</option><option>Under $1,000</option><option>$1,000–$10,000</option><option>$10,000–$50,000</option><option>$50,000–$250,000</option><option>$250,000+</option></select>')}${field('Preferred Contact Method', '<select name="preferred_contact" required><option>Email</option><option>Phone</option><option>Video call</option></select>')}</div>${field('Primary AI Providers Used', '<input name="providers" maxlength="300" placeholder="OpenAI, Anthropic, Gemini, etc." required>')}${field('What are you hoping to optimize?', '<textarea name="goals" maxlength="1500" rows="5" required></textarea>')}${field('Optional message / additional details', '<textarea name="message" maxlength="2000" rows="4"></textarea>')}<button class="button primary request-submit" type="submit">Request Demo</button><p class="request-status" role="status" aria-live="polite"></p></form>`;
}
function consultationForm() { return requestForm().replaceAll('DEMO','CONSULTATION_REQUEST').replace('Request Demo','Request Consultation'); }
export function demoPage() { return `${demoHeader()}<main id="main" class="request-shell"><section class="request-hero"><p class="eyebrow">BOOK A CONSULTATION</p><h1>Meet directly with a CutAICost owner.</h1><p>Review your AI usage, providers, model costs, telemetry goals, and optimization opportunities with us.</p><div class="request-trust"><span>Owner-led conversation</span><span>No account created</span><span>Private follow-up</span></div></section><section class="request-options request-options-single" aria-label="Consultation request"><article class="request-card"><h2>Tell us about your organization</h2><p>Share enough context for our team to prepare a useful conversation.</p>${consultationForm()}</article></section><section class="request-privacy"><strong>Private by design.</strong><span>Your submission is visible only to authorized platform administrators.</span></section></main>`; }
function signupRequestForm() { return `<form class="request-form" data-public-request="SIGNUP_REQUEST"><input type="hidden" name="request_type" value="SIGNUP_REQUEST"><input class="request-honeypot" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="request-form-grid">${field('Full Name','<input name="name" autocomplete="name" maxlength="100" required>')}${field('Work Email','<input name="email" type="email" autocomplete="email" maxlength="320" required>')}${field('Company / Organization','<input name="company" autocomplete="organization" maxlength="120" required>')}${field('Job Title','<input name="role" autocomplete="organization-title" maxlength="120>')}${field('Company Size','<select name="company_size"><option value="">Select company size</option><option>1–10</option><option>11–50</option><option>51–200</option><option>201–1,000</option><option>1,001+</option></select>')}${field('Phone Number — optional','<input name="phone" type="tel" autocomplete="tel" maxlength="40">')}${field('Estimated Monthly AI/API Spend','<select name="ai_spend_range"><option value="">Select a range</option><option>Under $1,000</option><option>$1,000–$10,000</option><option>$10,000–$50,000</option><option>$50,000–$250,000</option><option>$250,000+</option></select>')}${field('Preferred Contact Method','<select name="preferred_contact"><option>Email</option><option>Phone</option><option>Video call</option></select>')}</div>${field('Primary AI Providers Used','<input name="providers" maxlength="300" placeholder="OpenAI, Anthropic, Gemini, etc.">')}${field('What are you hoping to use CutAICost for?','<textarea name="goals" maxlength="1500" rows="5"></textarea>')}${field('Additional Notes','<textarea name="message" maxlength="2000" rows="4"></textarea>')}<button class="button primary request-submit" type="submit">Submit Sign Up Request</button><p class="request-status" role="status" aria-live="polite"></p></form>`; }
export function signupRequestPage() { return `${demoHeader()}<main id="main" class="request-shell"><section class="request-hero"><p class="eyebrow">PLATFORM ACCESS</p><h1>Sign Up Request</h1><p>Request access to the CutAICost platform. Provide your contact information and a few details about your organization so we can review your request and follow up with you directly.</p><div class="request-trust"><span>Creates a private ticket</span><span>No automatic account</span><span>Email follow-up</span></div></section><section class="request-options request-options-single" aria-label="Sign up request"><article class="request-card"><h2>Request platform access</h2><p>We can discuss onboarding, access, setup, and questions by email. Submitting this form does not automatically grant admin access.</p>${signupRequestForm()}</article></section><section class="request-privacy"><strong>Private by design.</strong><span>Your request is visible only to authorized platform administrators.</span></section></main>`; }
export function stopDemo() {}
async function submitRequest(event) {
  event.preventDefault(); const form = event.currentTarget, button = form.querySelector('button[type="submit"]'), status = form.querySelector('.request-status'), data = Object.fromEntries(new FormData(form)); button.disabled = true; status.textContent = 'Sending request…';
  try { const response = await fetch('/api/v1/public/requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify(data) }); const payload = await response.json().catch(() => ({})); if (!response.ok) { const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join('. ') : payload.detail; throw new Error(typeof detail === 'string' ? detail : 'Unable to submit your request.'); } form.reset(); status.textContent = data.request_type === 'SIGNUP_REQUEST' ? 'Your sign up request has been received. We’ll review your request and contact you using the email address you provided.' : 'Your consultation request has been received. We’ll contact you using the email address you provided.'; }
  catch (error) { status.textContent = error.message || 'Unable to submit your request.'; button.disabled = false; }
}
export function wireDemo() { document.querySelectorAll('[data-public-request]').forEach((form) => form.addEventListener('submit', submitRequest)); }
