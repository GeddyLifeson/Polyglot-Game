// Progression: each language climbs the ladder on its own; the next sector opens for a language once it has cleared the one below.
const { chromium } = require('playwright'); const path = require('path');
function log(l, ok, x){ console.log((ok?'PASS':'FAIL')+' — '+l+(x!==undefined?' :: '+JSON.stringify(x):'')); if(!ok) process.exitCode=1; }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  page.on('pageerror', e => { console.log('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto('file://' + path.resolve(__dirname, 'hub-qa-wrapped.html')); await page.waitForTimeout(300);

  // 1. Journey order: most spoken first
  const order = await page.evaluate(() => { const Q = window.__QA; return { first: Q.LANG_ORDER.slice(0, 6), last: Q.LANG_ORDER.slice(-3), speakers: Q.LANG_ORDER.map(l => Q.LANG_META[l].speakers) }; });
  const desc = order.speakers.every((v, i, a) => i === 0 || a[i-1] >= v);
  log('languages ordered by world speakers, descending', desc && order.first[0] === 'eng' && order.first[1] === 'zh' && order.first[2] === 'hi' && order.first[3] === 'es' && order.speakers.slice(-2).every(v => v === 0) && order.last.indexOf('la') !== -1, order);   // the two zero-speaker tongues (Latin, Diaithìris) sit last

  // 2. no crews: an old save's pairs key is dropped and nothing pair-shaped is exposed
  const nocrew = await page.evaluate(() => { const Q = window.__QA; return { pairsFor: typeof Q.pairsFor, pairOf: typeof Q.pairOf, journeyPairs: typeof Q.journeyPairs }; });
  log('pair helpers are gone', nocrew.pairsFor === 'undefined' && nocrew.pairOf === 'undefined' && nocrew.journeyPairs === 'undefined', nocrew);

  // 3. per-language gating: a language's next sector opens as soon as it clears the current one, whatever the others do
  const clearTier = (lang, idx) => `(function(){ const Q = window.__QA; Q.topicsForTier(Q.TIERS[${idx}], '${lang}').forEach(t => { Q.save.clearedDungeons[${idx}+':'+'${lang}'+':'+t] = true; }); })()`;
  const gate = await page.evaluate(`(function(){ const Q = window.__QA; Q.save.native = 'en'; Q.save.journey = {set:true, langs:['es','ja','it','fr']}; Q.save.clearedDungeons = {};
    const z = { esA1: Q.langTierUnlocked(0,'es'), esA2: Q.langTierUnlocked(1,'es'), hubA2: Q.isHubUnlocked(1), frontier: Q.frontierHubIdx() };
    ${clearTier('es', 0)}
    const a = { esA2: Q.langTierUnlocked(1,'es'), esB1: Q.langTierUnlocked(2,'es'), jaA2: Q.langTierUnlocked(1,'ja'), itA2: Q.langTierUnlocked(1,'it'), hubA2: Q.isHubUnlocked(1), hubB1: Q.isHubUnlocked(2), esCleared: Q.langTiersCleared('es'), frontier: Q.frontierHubIdx() };
    ${clearTier('es', 1)}
    const b = { esB1: Q.langTierUnlocked(2,'es'), esB2: Q.langTierUnlocked(3,'es'), jaA2: Q.langTierUnlocked(1,'ja'), hubB1: Q.isHubUnlocked(2), frontier: Q.frontierHubIdx() };
    return { z, a, b }; })()`);
  log('fresh voyage: A1 open, A2 locked for everyone', gate.z.esA1 === true && gate.z.esA2 === false && gate.z.hubA2 === false && gate.z.frontier === 0, gate.z);
  log('es clears A1 alone: A2 opens for es only (B1 still locked); ja and it stay on A1; A2 sector appears on the chart', gate.a.esA2 === true && gate.a.esB1 === false && gate.a.jaA2 === false && gate.a.itA2 === false && gate.a.hubA2 === true && gate.a.hubB1 === false && gate.a.esCleared === 1 && gate.a.frontier === 1, gate.a);
  log('es clears A2 too: B1 opens for es, B2 not yet; ja still locked out of A2', gate.b.esB1 === true && gate.b.esB2 === false && gate.b.jaA2 === false && gate.b.hubB1 === true && gate.b.frontier === 2, gate.b);

  // 4. the sector screen shows a language that is still behind as locked, with the sector it has to clear first
  await page.evaluate(() => { const Q = window.__QA; Q.save.clearedDungeons = {}; Q.save.journey = {set:true, langs:['es','ja']}; });
  await page.evaluate(clearTier('es', 0)); await page.evaluate(clearTier('es', 1));
  await page.evaluate(() => window.__QA.showHub(2)); await page.waitForTimeout(150);
  const hub = await page.$$eval('#dungeon-grid .dungeon-tile', els => els.map(e => ({ name: e.querySelector('.dungeon-name').textContent, locked: e.getAttribute('data-locked'), disabled: e.disabled, meta: e.querySelector('.dungeon-meta').textContent })));
  log('B1 sector: Spanish open, Japanese locked with "Clear A1 in Japanese first"', hub.some(t => t.name === 'Spanish' && t.locked === '0' && !t.disabled) && hub.some(t => t.name === 'Japanese' && t.locked === '1' && t.disabled && /Clear A1 in Japanese first/.test(t.meta)), hub);
  const chart = await page.evaluate(() => { const Q = window.__QA; Q.showHome(); const tiles = [...document.querySelectorAll('.hub-tile')]; return tiles.map(t => ({ code: t.querySelector('.lvl-badge').textContent, locked: t.getAttribute('data-locked'), progress: t.querySelector('.hub-progress').textContent })); });
  log('Star Chart: A1–B1 open, B2 locked, B1 tile notes one language still on an earlier sector', chart[0].locked === '0' && chart[1].locked === '0' && chart[2].locked === '0' && chart[3].locked === '1' && /1 still on an earlier sector/.test(chart[2].progress), chart.slice(0, 4));

  // 5. placement pre-clears a language: it starts there right away, the others are untouched
  const placed = await page.evaluate(() => { const Q = window.__QA; return { esB1: Q.langTierUnlocked(2,'es'), esA1: Q.langTierUnlocked(0,'es'), jaA2: Q.langTierUnlocked(1,'ja'), frontier: Q.frontierHubIdx(), story: Q.storyOpen({tier:'B1'}, 'es') && !Q.storyOpen({tier:'A2'}, 'ja') }; });
  log('placement at B1: B1 open for the placed language, A1 replayable, others unchanged, stories follow the same frontier', placed.esB1 === true && placed.esA1 === true && placed.jaA2 === false && placed.frontier === 2 && placed.story === true, placed);

  // 6. Open Channel opens per language and draws only from finished languages
  const oc = await page.evaluate(() => { const Q = window.__QA; Q.save.clearedDungeons = {}; Q.save.journey = {set:true, langs:['es','ja','it','fr']};
    for (let i = 0; i < 6; i++) { ['es'].forEach(l => Q.topicsForTier(Q.TIERS[i], l).forEach(t => { Q.save.clearedDungeons[i+':'+l+':'+t] = true; })); }
    const endless = Q.TIERS.length - 1; const langs = Q.openChannelLangs();
    Q.save.muted = true; Q.startDungeonAttempt(endless, null, null, null); const seen = {}; for (let k = 0; k < 60; k++) { const r = Q.makeRound(); if (r && r.lang) seen[r.lang] = true; }
    return { unlocked: Q.isHubUnlocked(endless), langs, tierLangs: Q.tierLangs(Q.TIERS[endless]), seen: Object.keys(seen).sort(), jaLocked: !Q.langTierUnlocked(endless, 'ja') }; });
  log('es finishes the ladder alone: Open Channel opens for es although ja/it/fr are untouched', oc.unlocked === true && oc.langs.join() === 'es' && oc.tierLangs.join() === 'es' && oc.jaLocked, oc);
  log('Open Channel rounds come only from the finished language', oc.seen.length > 0 && oc.seen.every(l => l === 'es'), oc.seen);

  // 7. Journey screen: any count works, one included; no crew tags; an old pairs key is dropped on save
  await page.evaluate(() => { const Q = window.__QA; Q.save.journey = {set:true, langs:['es','ja'], pairs:[['es','ja']]}; Q.showJourney(); });
  await page.waitForTimeout(150);
  await page.click('.journey-card[data-lang="it"]'); await page.waitForTimeout(100);
  const j1 = await page.evaluate(() => ({ disabled: document.getElementById('btn-journey-go').disabled, summary: document.getElementById('journey-summary').textContent, crews: document.querySelectorAll('.jc-crew').length }));
  await page.click('.journey-card[data-lang="es"]'); await page.click('.journey-card[data-lang="ja"]'); await page.waitForTimeout(100);
  const j2 = await page.evaluate(() => ({ disabled: document.getElementById('btn-journey-go').disabled, summary: document.getElementById('journey-summary').textContent }));
  await page.click('.journey-card[data-lang="it"]'); await page.waitForTimeout(100);
  const j0 = await page.evaluate(() => ({ disabled: document.getElementById('btn-journey-go').disabled, summary: document.getElementById('journey-summary').textContent }));
  await page.click('.journey-card[data-lang="it"]'); await page.waitForTimeout(100);
  log('Journey: three picked → can chart, no crew tags; one picked → can chart; none → cannot', j1.disabled === false && /3 languages on this voyage/.test(j1.summary) && !/crew/i.test(j1.summary) && j1.crews === 0 && j2.disabled === false && /1 language on this voyage/.test(j2.summary) && j0.disabled === true && /at least one/.test(j0.summary), { j1, j2, j0 });
  await page.click('#btn-journey-go'); await page.waitForTimeout(150);
  const saved = await page.evaluate(() => window.__QA.save.journey);
  log('charted voyage stores one language and no pairs', saved.langs.join() === 'it' && saved.pairs === undefined && saved.set === true, saved);

  await browser.close(); console.log('DONE');
})();
