/*
 * Drives the Domesday app as a user would, served by a LIVE appliance, and fails on anything a user
 * would see go wrong: the map not drawing, a search not finding Abberley, a place showing the wrong
 * figures, a tab rendering its failure state, the badge missing from the viewport, a console error.
 *
 *   EMBABEL_AUTH='Bearer …' node live.mjs [base-url] [--ask]
 *
 * --ask also asks one question through the app's Ask box, which costs a model call.
 * Screenshots land in tests/browser/screens/.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const base = (process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'http://localhost:11043').replace(/\/$/, '');
const auth = process.env.EMBABEL_AUTH;
if (!auth) { console.error('Set EMBABEL_AUTH.'); process.exit(2); }
const withAsk = process.argv.includes('--ask');
const url = `${base}/apps/realm-domesday/domesday.html`;
mkdirSync(new URL('./screens/', import.meta.url), { recursive: true });
const shot = (page, name) => page.screenshot({ path: new URL(`./screens/${name}.png`, import.meta.url).pathname, fullPage: false });

const failures = [];
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures.push(what); };

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1360, height: 900 }, extraHTTPHeaders: { Authorization: auth } });
const page = await context.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));

const t0 = Date.now();
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => /\d[\d,]* places/.test(document.getElementById('map-count')?.textContent ?? ''), null, { timeout: 30000 });
const firstPaint = Date.now() - t0;
const count = await page.textContent('#map-count');
check(Number(count.replace(/\D/g, '')) > 13000, `map draws every located place (${count}, ${firstPaint} ms to first paint)`);
check(firstPaint < 5000, `first paint under 5 s (${firstPaint} ms)`);
await shot(page, '01-map');

// the badge is visible, links out, inside the viewport
const badge = await page.$('#embabel-badge');
const box = badge && await badge.boundingBox();
check(!!box && box.y + box.height <= 900 && box.height > 10, 'Embabel badge visible in the viewport');
check(!!(await page.$('#embabel-badge a[href="https://worlds.embabel.com"]')), 'badge links to worlds.embabel.com');

// search → place → figures
await page.fill('#q', 'Abberley');
await page.waitForSelector('#results.open a[href^="#/place/"]', { timeout: 15000 });
const placeHits = await page.$$eval('#results a[href^="#/place/"]', (as) => as.map((a) => a.textContent));
check(placeHits.some((t) => t.includes('Abberley') && t.includes('Worcestershire')), `search finds Abberley, Worcestershire (${placeHits.length} places)`);
await shot(page, '02-search');
await page.click('#results a[href="#/place/1"]');
await page.waitForSelector('#drawer.open .entry', { timeout: 15000 });
const entryText = await page.textContent('#drawer-body');
check(entryText.includes('Worcestershire 15,8'), 'Abberley shows its entry, Worcestershire 15,8');
check(/18 villagers/.test(entryText), 'Abberley shows 18 villagers');
check(entryText.includes('£10 10s'), 'Abberley shows £10 10s in 1086');
check(entryText.includes('Ralph of Tosny') && entryText.includes('Wulfmer'), 'Abberley shows Wulfmer (1066) and Ralph of Tosny (1086)');
check(!!(await page.$('#drawer-body a[href*="opendomesday.org/book/worcestershire/09/"]')), 'folio link points at Open Domesday WOR 9');
await shot(page, '03-place');

// a person, from the place
await page.click('#drawer-body a[href="#/person/Ralph%20of%20Tosny"]');
// The place drawer already holds tables, so wait for the PERSON's drawer, not for any table.
await page.waitForFunction(() => (document.querySelector('#drawer-head h2')?.textContent ?? '') === 'Ralph of Tosny'
  && /Tenant-in-chief, 1086/.test(document.querySelector('#drawer-body')?.textContent ?? ''), null, { timeout: 15000 }).catch(() => {});
const personText = await page.textContent('#drawer-body');
check(/Tenant-in-chief, 1086/.test(personText), 'Ralph of Tosny lists his holdings as tenant-in-chief');
await shot(page, '04-person');

// an entry in full
await page.goto(`${url}#/entry/8146`);
await page.waitForFunction(() => (document.querySelector('#drawer-head h2')?.textContent ?? '').includes('15,8'), null, { timeout: 15000 });
const entryBody = await page.textContent('#drawer-body');
check(entryBody.includes('Lord in 1066'), 'entry detail lists people by role');
check(/What it says[\s\S]*Ralph of Tosny holds ABBERLEY|What it says[\s\S]*ABBERLEY/.test(entryBody), 'entry detail shows what Abberley\'s entry says');
await page.click('#edition-toggle');
check(/\[=|\?/.test(await page.textContent('#said')), 'the toggle shows Hull\'s edition with its apparatus');

// then and now: the place drawer sets 1086 households beside 2021's
await page.goto(`${url}#/place/1`);
await page.waitForFunction(() => /Households, 2021/.test(document.querySelector('#place-now')?.textContent ?? ''), null, { timeout: 20000 }).catch(() => {});
const nowText = await page.textContent('#place-now');
check(/Households, 1086\s*32/.test(nowText) && /288/.test(nowText), 'Abberley: 32 households in 1086 beside 288 in 2021');

// a person with a checked Wikipedia article
await page.goto(`${url}#/person/${encodeURIComponent('Bishop Odo/of Bayeux')}`);
await page.waitForFunction(() => /Odo of Bayeux/.test(document.querySelector('#person-wiki')?.textContent ?? ''), null, { timeout: 30000 }).catch(() => {});
check(/Odo of Bayeux[\s\S]*Bayeux Tapestry/.test(await page.textContent('#person-wiki')), 'Odo has his checked Wikipedia article');
await shot(page, '04b-person-wikipedia');

// the text: an exact word is found, counted by county
await page.goto(`${url}#/tab/text`);
await page.fill('#text-q', 'eels');
await page.click('#text-form button[type=submit]');
await page.waitForSelector('#text-results .said-item', { timeout: 30000 }).catch(() => {});
check((await page.$$('#text-results .said-item')).length >= 50, 'the text tab finds the entries that mention eels');
check((await page.textContent('#text-where')).includes('Cambridgeshire'), 'eels are counted by county, Cambridgeshire among them');
await shot(page, '08-text');

// the tabs render rows, not their failure state
for (const [tab, sel, min] of [['counties', '#counties tr.click', 31], ['conquest', '#tic1086 li', 10], ['wealth', '#waste li', 10],
  ['studies', '#devastation li', 10], ['studies', '#whoheld .stack', 25], ['studies', '#antecessors tr', 10], ['studies', '#growth tr', 10]]) {
  await page.goto(`${url}#/tab/${tab}`);
  await page.waitForSelector(sel, { timeout: 20000 });
  const rows = (await page.$$(sel)).length;
  const err = await page.$(`#pane-${tab} .err`);
  check(rows >= min && !err, `${tab} tab renders ${rows} rows and no error`);
  await shot(page, `05-${tab}`);
}
check((await page.textContent('#tic1086 li')).includes('King William'), 'King William heads the tenants-in-chief');
check((await page.textContent('#waste li')).includes('Yorkshire'), 'Yorkshire heads the waste');

// a county drawer
await page.goto(`${url}#/county/YKS`);
await page.waitForSelector('#drawer-body .tiles', { timeout: 20000 });
check((await page.textContent('#drawer-body')).includes('Hundreds'), 'Yorkshire opens with its hundreds');
await page.goto(`${url}#/county/ESS`);
await page.waitForSelector('#drawer-body .tiles', { timeout: 20000 });
const essex = await page.textContent('#drawer-body');
check(essex.includes('Little Domesday') && /read from the translation/.test(essex), 'Essex opens with its figures, and says they are read from the translation');

// near a point on the map
await page.goto(`${url}#/tab/map`);
await page.waitForFunction(() => /\d[\d,]* places/.test(document.getElementById('map-count')?.textContent ?? ''), null, { timeout: 30000 });

if (withAsk) {
  await page.goto(`${url}#/ask/${encodeURIComponent('How many mills were there in Kent?')}`);
  await page.waitForSelector('#answer pre.cypher, #answer .err, #answer .empty', { timeout: 150000 });
  const ans = await page.textContent('#answer');
  check(/345\.75|345,75|346/.test(ans), `ask: mills in Kent answers 345.75 (${ans.slice(0, 80).replace(/\s+/g, ' ')})`);
  await shot(page, '06-ask');
}

// a narrow screen still works
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${url}#/place/1`);
await page.waitForSelector('#drawer.open .entry', { timeout: 15000 });
await shot(page, '07-phone');

check(errors.length === 0, `no console errors${errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''}`);
await browser.close();
console.log(failures.length ? `${failures.length} FAILED` : 'all passed');
process.exit(failures.length ? 1 : 0);
