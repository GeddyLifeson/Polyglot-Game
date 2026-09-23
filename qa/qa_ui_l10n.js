// The interface in the player's own language: load the game with a few native languages over HTTP (the ui pool
// is fetched from l10n/<lang>.json), walk every screen and check that no English interface string is left where
// a translation exists. Run with: node qa/with_server.js qa/qa_ui_l10n.js   (screenshots go to $SHOT_DIR or cwd)
const { chromium } = require('playwright');
const path = require('path');
function log(label, ok, extra) {
  console.log((ok ? 'PASS' : 'FAIL') + ' — ' + label + (extra !== undefined ? ' :: ' + JSON.stringify(extra).slice(0, 400) : ''));
  if (!ok) process.exitCode = 1;
}
const BASE = (process.env.QA_URL || 'http://localhost:8000') + '/qa/hub-qa-wrapped.html';
const SHOTS = process.env.SHOT_DIR || '.';
const LANGS = (process.env.UI_LANGS || 'es,ja,ar,de,gr').split(',');

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const nat of LANGS) {
    const ctx = await browser.newContext({ viewport: { width: 430, height: 900 } });
    await ctx.addInitScript((nat) => {
      try { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
        localStorage.setItem('polyglotBistro.v2', JSON.stringify({ native: nat, journey: { langs: nat === 'fr' ? ['es', 'ja'] : ['fr', 'ja'], set: true }, tutorial: { done: true, seen: {} }, xp: 3000, tips: 5000, dark: 30 })); } } catch (e) {}
    }, nat);
    const page = await ctx.newPage();
    page.on('pageerror', e => { console.log('PAGE ERROR (' + nat + '):', e.message); process.exitCode = 1; });
    await page.goto(BASE);
    await page.waitForFunction(() => window.__QA && window.__QA.l10n() && !document.documentElement.classList.contains('l10n-wait'), null, { timeout: 15000 });
    const ui = await page.evaluate(() => (window.__QA.l10n() || {}).ui || {});
    const nUi = Object.keys(ui).length;
    log(nat + ': ui pool loaded', nUi > 1000, nUi);

    // every visible text node / attribute that is still an English source string with a different translation
    const leftovers = async (where) => page.evaluate(() => {
      const U = (window.__QA.l10n() || {}).ui || {}; const out = [];
      const own = {}; Object.keys(window.__QA.LANG_META).forEach(c => { own[window.__QA.LANG_META[c].native] = 1; });   /* a language's own name is shown on purpose */
      const vis = (e) => { for (let x = e; x && x !== document.body; x = x.parentElement) { if (x.hidden || getComputedStyle(x).display === 'none') return false; } return true; };
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) { const s = n.textContent.trim(); if (s.length > 1 && U[s] && U[s] !== s && !own[s] && n.parentElement && n.parentElement.tagName !== 'SCRIPT' && vis(n.parentElement)) out.push(s); }
      document.querySelectorAll('[data-t]').forEach(e => { const k = e.innerHTML.trim(); if (U[k] && U[k] !== k) out.push('data-t:' + k); });
      document.querySelectorAll('[title],[placeholder],[aria-label]').forEach(e => ['title', 'placeholder', 'aria-label'].forEach(a => { const v = e.getAttribute(a); if (v && U[v] && U[v] !== v) out.push(a + ':' + v); }));
      return out;
    });
    const check = async (label, fn, shot) => {
      await page.evaluate(fn); await page.waitForTimeout(150);
      const left = await leftovers();
      log(nat + ': ' + label + ' has no English left', left.length === 0, left.slice(0, 8));
      if (shot) await page.screenshot({ path: path.join(SHOTS, 'ui_' + nat + '_' + shot + '.png'), fullPage: true });
    };
    await check('home', () => window.__QA.showHome(), 'home');
    const home = await page.evaluate(() => ({ lang: document.documentElement.lang, chart: document.querySelector('#screen-home h2').textContent, tier: document.querySelector('.hub-name').textContent }));
    log(nat + ': <html lang>, headings and sector names follow the native language', home.lang !== 'en' && home.chart !== 'Star Chart' && !/Comms Cadet/.test(home.tier), home);
    await check('journey + language picker', () => window.__QA.showJourney(), 'journey');
    const picker = await page.evaluate(() => Array.from(document.querySelectorAll('#native-sel option')).map(o => o.textContent));
    const es = picker.find(o => /Español/.test(o)) || '', en = picker[0] || '';
    log(nat + ': picker shows each language by its own name plus its name in the player\'s language', /Español/.test(es) && (nat === 'es' || / · /.test(es)) && /English · /.test(en), { es, en });
    await check('engineering bay', () => { window.__QA.showShop(); }, 'shop');
    await check('mission log', () => window.__QA.showLog(), 'log');
    await check('library', () => window.__QA.showStories(), 'library');
    await check('placement picker', () => window.__QA.showPlacementPicker(), null);
    await check('intercept', () => window.__QA.showIntercept(), null);
    await check('sector + topics', () => { window.__QA.showHub(0); window.__QA.showTopics(0, window.__QA.journeyLangs()[0]); }, 'topics');
    await check('relay briefing', () => window.__QA.enterDungeon(0, window.__QA.journeyLangs()[0], 'greetings'), 'briefing');
    await check('loadout draft', () => window.__QA.showLoadoutDraft(0, window.__QA.journeyLangs()[0], 'greetings'), 'draft');
    await check('a round in play', () => { window.__QA.startDungeonAttempt(0, window.__QA.journeyLangs()[0], 'greetings', null); }, 'play');
    await check('anomaly event', () => { window.__QA.showEvent(); }, null);
    await check('relay result', () => { const Q = window.__QA; Q.startDungeonAttempt(0, Q.journeyLangs()[0], 'greetings', null); Q.st.correct = 10; Q.st.total = 10; Q.st.floorCorrect = 10; Q.onDungeonCleared(); }, 'result');
    await check('voices panel', () => { document.getElementById('btn-voices').click(); }, null);
    await page.evaluate(() => { document.getElementById('voices-overlay').hidden = true; });
    await check('lexicon', () => { document.getElementById('btn-phrasebook').click(); }, 'lexicon');
    await page.evaluate(() => { document.getElementById('phrasebook-overlay').hidden = true; });
    const toast = await page.evaluate(() => { window.__QA.addXp(100000); return document.getElementById('toast').textContent; });
    log(nat + ': a toast (promotion) is translated', toast && !/Promoted/.test(toast), toast.slice(0, 80));
    await ctx.close();
  }
  // English players see exactly the English source
  const ctx = await browser.newContext({ viewport: { width: 430, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE); await page.waitForTimeout(400);
  const en = await page.evaluate(() => ({ l10n: window.__QA.l10n(), wait: document.documentElement.classList.contains('l10n-wait'), chart: document.querySelector('#screen-home h2').textContent }));
  log('en: no pool fetched, page shown at once, English text', en.l10n === null && !en.wait && en.chart === 'Star Chart', en);
  await ctx.close();
  await browser.close();
  console.log('DONE');
})();
