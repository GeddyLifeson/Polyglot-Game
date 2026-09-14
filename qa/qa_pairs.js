// Crews: languages travel in pairs and climb the ladder in lockstep; crews are independent of each other.
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
  log('languages ordered by world speakers, descending', desc && order.first[0] === 'eng' && order.first[1] === 'zh' && order.first[2] === 'hi' && order.first[3] === 'es' && order.last[2] === 'la', order);

  // 2. pairing: picks form crews in order; an existing crew is kept when a new pair is added
  const pairs = await page.evaluate(() => { const Q = window.__QA; Q.save.native = 'en'; Q.save.clearedDungeons = {}; Q.save.journey = {set:true, langs:['es','ja','it','fr'], pairs:null}; const p1 = Q.journeyPairs(); Q.save.journey.pairs = p1; Q.save.journey.langs = ['es','ja','it','fr','de','ko']; const p2 = Q.journeyPairs(); return { p1, p2, partner: Q.pairOf('ja') }; });
  log('four languages form two crews; adding two more forms a third without reshuffling', JSON.stringify(pairs.p1) === '[["es","ja"],["it","fr"]]' && JSON.stringify(pairs.p2) === '[["es","ja"],["it","fr"],["de","ko"]]' && pairs.partner.join() === 'es,ja', pairs);

  // 3. lockstep: the stronger language waits for its crewmate
  const clearTier = (lang, idx) => `(function(){ const Q = window.__QA; Q.topicsForTier(Q.TIERS[${idx}], '${lang}').forEach(t => { Q.save.clearedDungeons[${idx}+':'+'${lang}'+':'+t] = true; }); })()`;
  const lock = await page.evaluate(`(function(){ const Q = window.__QA; Q.save.journey = {set:true, langs:['es','ja','it','fr'], pairs:[['es','ja'],['it','fr']]}; Q.save.clearedDungeons = {};
    ${clearTier('es', 0)}
    const a = { esA2: Q.langTierUnlocked(1,'es'), jaA2: Q.langTierUnlocked(1,'ja'), hubA2: Q.isHubUnlocked(1), esCleared: Q.langTiersCleared('es'), frontier: Q.pairFrontier(Q.pairOf('es')) };
    ${clearTier('ja', 0)}
    const b = { esA2: Q.langTierUnlocked(1,'es'), jaA2: Q.langTierUnlocked(1,'ja'), itA2: Q.langTierUnlocked(1,'it'), hubA2: Q.isHubUnlocked(1), esA3: Q.langTierUnlocked(2,'es') };
    return { a, b }; })()`);
  log('es clears A1 alone: A2 stays locked for es (crewmate ja at A1)', lock.a.esA2 === false && lock.a.jaA2 === false && lock.a.hubA2 === false && lock.a.esCleared === 1 && lock.a.frontier === 0, lock.a);
  log('ja clears A1 too: A2 opens for that crew only; it/fr crew still at A1', lock.b.esA2 === true && lock.b.jaA2 === true && lock.b.itA2 === false && lock.b.hubA2 === true && lock.b.esA3 === false, lock.b);

  // 4. the sector screen shows the held-back language as locked
  await page.evaluate(() => { const Q = window.__QA; Q.save.clearedDungeons = {}; Q.save.journey = {set:true, langs:['es','ja'], pairs:[['es','ja']]}; });
  await page.evaluate(clearTier('es', 0)); await page.evaluate(clearTier('es', 1));
  await page.evaluate(() => window.__QA.showHub(1)); await page.waitForTimeout(150);
  const hub = await page.$$eval('#dungeon-grid .dungeon-tile', els => els.map(e => ({ name: e.querySelector('.dungeon-name').textContent, locked: e.getAttribute('data-locked'), meta: e.querySelector('.dungeon-meta').textContent })));
  log('A2 sector: Spanish locked with a "waiting for Japanese" note while Japanese is still on A1', hub.some(t => t.name === 'Spanish' && t.locked === '1' && /Waiting for Japanese/.test(t.meta)), hub);

  // 5. placement pre-clears a language ahead of its crewmate: it still waits
  const placed = await page.evaluate(() => { const Q = window.__QA; return { esB1: Q.langTierUnlocked(2,'es'), esA1: Q.langTierUnlocked(0,'es'), frontier: Q.frontierHubIdx() }; });
  log('placement ahead of the crewmate: B1 locked for the placed language, A1 replayable', placed.esB1 === false && placed.esA1 === true && placed.frontier === 0, placed);

  // 6. Open Channel opens per crew and draws only from finished crews
  const oc2 = await page.evaluate(() => { const Q = window.__QA; Q.save.clearedDungeons = {}; Q.save.journey = {set:true, langs:['es','ja','it','fr'], pairs:[['es','ja'],['it','fr']]};
    for (let i = 0; i < 6; i++) { ['es','ja'].forEach(l => Q.topicsForTier(Q.TIERS[i], l).forEach(t => { Q.save.clearedDungeons[i+':'+l+':'+t] = true; })); }
    const endless = Q.TIERS.length - 1; const langs = Q.openChannelLangs();
    Q.save.muted = true; Q.startDungeonAttempt(endless, null, null, null); const seen = {}; for (let k = 0; k < 60; k++) { const r = Q.makeRound(); if (r && r.lang) seen[r.lang] = true; }
    return { unlocked: Q.isHubUnlocked(endless), langs, tierLangs: Q.tierLangs(Q.TIERS[endless]), seen: Object.keys(seen).sort(), itLocked: !Q.langTierUnlocked(endless, 'it') }; });
  log('crew es+ja finishes the ladder: Open Channel opens for them although it+fr are untouched', oc2.unlocked === true && oc2.langs.join() === 'es,ja' && oc2.tierLangs.join() === 'es,ja' && oc2.itLocked, oc2);
  log('Open Channel rounds come only from the finished crew', oc2.seen.every(l => l === 'es' || l === 'ja'), oc2.seen);

  // 7. Journey screen: an odd pick cannot be charted
  await page.evaluate(() => { const Q = window.__QA; Q.save.journey = {set:true, langs:['es','ja'], pairs:[['es','ja']]}; Q.showJourney(); });
  await page.waitForTimeout(150);
  await page.click('.journey-card[data-lang="it"]'); await page.waitForTimeout(100);
  const j1 = await page.evaluate(() => ({ disabled: document.getElementById('btn-journey-go').disabled, summary: document.getElementById('journey-summary').textContent }));
  await page.click('.journey-card[data-lang="fr"]'); await page.waitForTimeout(100);
  const j2 = await page.evaluate(() => ({ disabled: document.getElementById('btn-journey-go').disabled, crews: [...document.querySelectorAll('.journey-card.on .jc-crew')].map(e => e.textContent) }));
  log('Journey: three picked → cannot chart, warning shown; four picked → two crews, can chart', j1.disabled === true && /pairs/.test(j1.summary) && j2.disabled === false && j2.crews.length === 4, { j1, j2 });
  await page.click('#btn-journey-go'); await page.waitForTimeout(150);
  const saved = await page.evaluate(() => window.__QA.save.journey);
  log('charted voyage stores the crews', JSON.stringify(saved.pairs) === '[["es","ja"],["it","fr"]]' && saved.langs.length === 4, saved);

  await browser.close(); console.log('DONE');
})();
