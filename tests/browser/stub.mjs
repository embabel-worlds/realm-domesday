/*
 * The Domesday app against a STUBBED runtime: the app's own HTML from this checkout, the appliance's
 * runtime scripts and view envelopes captured once from a live appliance, and the cases a live run
 * cannot produce on demand — an empty search, a view that fails, a slow search overtaken by a newer
 * one, a question the ask surface fails to answer.
 *
 *   EMBABEL_AUTH='Bearer …' node stub.mjs --capture [base-url]   # refresh fixtures/ from a live appliance
 *   node stub.mjs                                                # run hermetically from fixtures/
 *
 * A stub answers instantly and so hides every timing defect; the delayed-search case exists for that.
 */
import { chromium } from 'playwright';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const here = new URL('./', import.meta.url);
const fixtures = new URL('./fixtures/', here);
const appHtml = readFileSync(new URL('../../apps/domesday.html', here), 'utf8');
const capture = process.argv.includes('--capture');
const base = (process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'http://localhost:11043').replace(/\/$/, '');
const auth = process.env.EMBABEL_AUTH;
if (capture && !auth) { console.error('--capture needs EMBABEL_AUTH'); process.exit(2); }
mkdirSync(fixtures, { recursive: true });

const fixtureName = (path, body) => {
  const view = /\/api\/v1\/views\/([^/]+)\/invoke/.exec(path);
  if (view) return `view-${view[1]}-${Buffer.from(JSON.stringify((body && body.args) || {})).toString('base64url').slice(0, 80)}.json`;
  if (path.includes('/api/v1/tools/')) return `tool-${path.split('/').pop()}-${Buffer.from(body ? JSON.stringify(body) : '').toString('base64url').slice(0, 60)}.json`;
  return 'asset-' + path.replace(/[^a-z0-9.]+/gi, '_');
};

/* Per-scenario overrides: a function of (path, body) returning {status, body, delay} or undefined. */
let override = () => undefined;

async function serve(route) {
  const req = route.request(), url = new URL(req.url()), path = url.pathname;
  if (path.endsWith('/apps/realm-domesday/domesday.html')) return route.fulfill({ status: 200, contentType: 'text/html', body: appHtml });
  if (path.endsWith('/domesday.svg')) return route.fulfill({ status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg"/>' });
  if (path.startsWith('/api/v1/virtual-cypher/events')) return route.fulfill({ status: 204, body: '' });
  let body = null;
  try { body = req.postData() ? JSON.parse(req.postData()) : null; } catch { body = null; }
  const o = override(path, body);
  if (o) {
    if (o.delay) await new Promise((r) => setTimeout(r, o.delay));
    if (o.status) return route.fulfill({ status: o.status, contentType: 'application/json', body: JSON.stringify(o.body ?? {}) });
  }
  const file = new URL(fixtureName(path, body), fixtures);
  if (capture && !existsSync(file)) {
    const res = await fetch(base + path + url.search, { method: req.method(), headers: { Authorization: auth, 'content-type': 'application/json' }, body: req.postData() });
    const text = await res.text();
    writeFileSync(file, JSON.stringify({ status: res.status, contentType: res.headers.get('content-type'), text }));
  }
  if (!existsSync(file)) return route.fulfill({ status: 599, contentType: 'text/plain', body: `no fixture for ${path} — run with --capture` });
  const f = JSON.parse(readFileSync(file, 'utf8'));
  return route.fulfill({ status: f.status, contentType: f.contentType || 'application/json', body: f.text });
}

const failures = [];
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures.push(what); };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1360, height: 900 } });
await context.route('**/*', serve);
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(`${e} @ ${page.url()}`));
page.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push(m.text()); });
const app = `${base}/apps/realm-domesday/domesday.html`;
/* A goto that changes only the hash does not reload the page, so each scenario starts from a real load. */
const fresh = async (hash) => { await page.goto('about:blank'); await page.goto(`${app}${hash}`); };
const mapDrawn = () => page.waitForFunction(() => /\d[\d,]* places/.test(document.getElementById('map-count')?.textContent ?? ''), null, { timeout: 20000 });

// 1 — the normal path, from captured envelopes
await page.goto(app);
await mapDrawn();
check(Number((await page.textContent('#map-count')).replace(/\D/g, '')) > 13000, 'map renders every captured place');
await page.waitForSelector('#glance .big');
check((await page.$$('#glance .big')).length === 4, 'England in 1086 shows its four totals');
await page.fill('#q', 'Abberley');
await page.waitForSelector('#results a[href="#/place/1"]');
await page.click('#results a[href="#/place/1"]');
await page.waitForSelector('#drawer.open .entry');
check(/18 villagers/.test(await page.textContent('#drawer-body')), 'a place renders its figures');
for (const tab of ['counties', 'conquest', 'wealth']) {
  await fresh(`#/tab/${tab}`);
  await page.waitForFunction((t) => !document.querySelector(`#pane-${t} .loading`), tab, { timeout: 20000 });
  check(!(await page.$(`#pane-${tab} .err`)), `${tab} tab renders without its failure state`);
}

// 2 — an empty search is said to be empty, not shown as blank
/* The runtime validates an envelope's shape, so an empty answer is replayed as the appliance sends one. */
const emptyEnvelope = (op) => ({ executionId: 'exec_stub', operationId: op, contractVersion: '1', status: 'SUCCEEDED',
  outcome: 'EMPTY', outputType: 'rows', data: [], warnings: [], error: null, metrics: { durationMs: 1, externalCalls: 0, cacheHit: false } });
override = (path) => /\/(DomesdayPlaceSearch|DomesdayPersonSearch)\/invoke$/.test(path)
  ? { status: 200, body: emptyEnvelope(path.split('/').slice(-2)[0]) } : undefined;
await fresh('#/tab/map');
await mapDrawn();
await page.fill('#q', 'Zzyzx');
await page.waitForSelector('#results .empty');
check((await page.textContent('#results')).includes('names no place or person'), 'an empty search says Domesday names nothing like it');

// 3 — a failing view says it failed, and says that is not "nothing"
override = (path) => path.endsWith('/DomesdayCountySummary/invoke') ? { status: 500, body: { error: 'boom' } } : undefined;
await fresh('#/tab/counties');
await page.waitForSelector('#counties .err', { timeout: 20000 });
check((await page.textContent('#counties')).includes('not because there is nothing'), 'a failed view says the failure is not an empty answer');
check(!!(await page.$('#glance .err')), 'the glance column shows the same failure, not zeros');

// 4 — a slow search overtaken by a newer one never paints over it
override = (path, body) => path.endsWith('/DomesdayPlaceSearch/invoke') && body?.args?.name === 'Abber' ? { delay: 2500 } : undefined;
await fresh('#/tab/map');
await mapDrawn();
await page.fill('#q', 'Abber');
await page.waitForTimeout(400);
await page.fill('#q', 'Abberley');
await page.waitForSelector('#results a[href="#/place/1"]');
await page.waitForTimeout(3000);
const shown = await page.$$eval('#results a[href^="#/place/"]', (as) => as.map((a) => a.textContent));
check(shown.length > 0 && shown.every((t) => /abberley/i.test(t)), `the newer search stays on screen after the slower one lands (${shown.length} rows)`);

// 5 — a question the ask surface fails to answer is reported as unanswered
override = (path) => path.endsWith('/api/v1/tools/kg_ask') ? { status: 502, body: { error: 'upstream' } } : undefined;
await fresh(`#/ask/${encodeURIComponent('How many mills were there in Kent?')}`);
await page.waitForSelector('#answer .err', { timeout: 20000 });
check((await page.textContent('#answer')).includes('not because Domesday is silent'), 'a failed question says it was not answered');

// 6 — a hostile route is ignored, not rendered
override = () => undefined;
await fresh(`#/person/${encodeURIComponent('<img src=x onerror=alert(1)>')}`);
await page.waitForSelector('#drawer.open');
await page.waitForTimeout(1500);
check(!(await page.$('#drawer img')), 'a name from the route is escaped, never rendered as markup');

check(errors.length === 0, `no console errors${errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''}`);
await browser.close();
console.log(failures.length ? `${failures.length} FAILED` : 'all passed');
process.exit(failures.length ? 1 : 0);
