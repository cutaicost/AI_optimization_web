import './request.css';

const clean = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

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

const publicObserver = new MutationObserver(protectPublicSurface);
if (document.body) publicObserver.observe(document.body, { childList: true, subtree: true });
document.addEventListener('click', (event) => {
  const link = event.target.closest('a[href="/register"], a[href="/demo#access"]');
  if (!link) return;
  event.preventDefault(); event.stopImmediatePropagation(); history.pushState({}, '', '/demo#access'); window.dispatchEvent(new PopStateEvent('popstate'));
}, true);

const demoHeader = () => `<header class="demo-nav request-nav"><a href="/" data-route class="brand">CutAIcost</a><nav><a href="/" data-route>Back to Home</a><a href="/login" data-route>Sign In</a></nav></header>`;
const field = (label, input) => `<label>${clean(label)}${input}</label>`;
function requestForm(type) {
  const isDemo = type === 'DEMO';
  return `<form class="request-form" data-public-request="${type}"><input type="hidden" name="request_type" value="${type}"><input class="request-honeypot" name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="request-form-grid">${field('Name', '<input name="name" autocomplete="name" maxlength="100" required>')}${field('Work Email', '<input name="email" type="email" autocomplete="email" maxlength="320" required>')}${field('Company', '<input name="company" autocomplete="organization" maxlength="120">')}${field('Role / Job Title', '<input name="role" autocomplete="organization-title" maxlength="120">')}${field('Approximate Monthly AI Spend', '<select name="ai_spend_range"><option value="">Prefer not to say</option><option>Under $1,000</option><option>$1,000–$10,000</option><option>$10,000–$50,000</option><option>$50,000–$250,000</option><option>$250,000+</option></select>')}${field('Preferred Contact', '<select name="preferred_contact"><option>Email</option><option>Phone / video call</option></select>')}</div>${field('AI Providers Currently Used', '<input name="providers" maxlength="300" placeholder="Optional">')}${field(isDemo ? 'What would you like to review with us?' : 'What are you hoping to use CutAIcost for?', '<textarea name="goals" maxlength="1500" rows="5" required></textarea>')}<button class="button primary request-submit" type="submit">${isDemo ? 'Request a Demo' : 'Request Access'}</button><p class="request-status" role="status" aria-live="polite"></p></form>`;
}
export function demoPage() { return `${demoHeader()}<main id="main" class="request-shell"><section class="request-hero"><p class="eyebrow">PRIVATE PRODUCT ACCESS</p><h1>See CutAIcost with us.</h1><p>We do not expose the working product, dashboards, or internal workflows through a public demo. Tell us what you are evaluating and we will follow up for a private walkthrough or account access.</p><div class="request-trust"><span>Private walkthrough</span><span>No public dashboard</span><span>Access by approval</span></div></section><section class="request-options" aria-label="Demo and access requests"><article class="request-card" id="book-demo"><p class="eyebrow">BOOK A DEMO</p><h2>Request a private demonstration</h2><p>Meet with us for a guided overview tailored to your organization. No customer credentials or production telemetry are required to request a meeting.</p>${requestForm('DEMO')}</article><article class="request-card" id="access"><p class="eyebrow">REQUEST ACCESS</p><h2>Interested in an account?</h2><p>Public self-registration is closed. Submit an access request and we will review it before account enrollment.</p>${requestForm('ACCESS')}</article></section><section class="request-privacy"><strong>Private by design.</strong><span>Submitting this form does not connect an AI provider, upload telemetry, or grant access to the CutAIcost application.</span></section></main>`; }
export function stopDemo() {}
async function submitRequest(event) {
  event.preventDefault(); const form = event.currentTarget, button = form.querySelector('button[type="submit"]'), status = form.querySelector('.request-status'), data = Object.fromEntries(new FormData(form)); button.disabled = true; status.textContent = 'Sending request…';
  try { const response = await fetch('/api/v1/public/requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify(data) }); const payload = await response.json().catch(() => ({})); if (!response.ok) { const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join('. ') : payload.detail; throw new Error(typeof detail === 'string' ? detail : 'Unable to submit your request.'); } form.reset(); status.textContent = data.request_type === 'DEMO' ? 'Demo request received. We will follow up with you.' : 'Access request received. We will review it and follow up with you.'; }
  catch (error) { status.textContent = error.message || 'Unable to submit your request.'; button.disabled = false; }
}
export function wireDemo() { protectPublicSurface(); document.querySelectorAll('[data-public-request]').forEach((form) => form.addEventListener('submit', submitRequest)); if (location.hash === '#access') requestAnimationFrame(() => document.querySelector('#access')?.scrollIntoView({ block: 'start' })); }
