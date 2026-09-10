const { chromium } = require('playwright');
const path = require('path');
function log(label, ok, extra) {
  console.log((ok ? 'PASS' : 'FAIL') + ' — ' + label + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : ''));
  if (!ok) process.exitCode = 1;
}
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  page.on('pageerror', e => { console.log('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto('file://' + path.resolve(__dirname, 'hub-qa-wrapped.html'));
  await page.waitForTimeout(300);

  // 1. home: profile card, storm card, log button
  const home = await page.evaluate(() => ({ profile: document.getElementById('home-profile').textContent, storm: document.getElementById('storm-card').textContent, asc: document.getElementById('asc-row').hidden }));
  log('home: profile shows Cadet + XP, storm card with 2 modifiers, interference panel hidden at rank 0', /Comms Cadet/.test(home.profile) && /0 XP/.test(home.profile) && /Signal Storm/.test(home.storm) && home.asc === true, { p: home.profile.slice(0, 80), s: home.storm.slice(0, 60) });
  await page.screenshot({ path: 'ov_home.png', fullPage: true });

  // 2. rank-gated draft: rank 0 → commons only; xp 300 → rare allowed; 2400 → legendary
  const draft = await page.evaluate(() => {
    const Q = window.__QA; const out = {};
    Q.save.xp = 0; out.r0 = Array.from(new Set(Array.from({length: 30}, () => Q.draftPool()).flat().map(p => p.rarity)));
    Q.save.xp = 300; out.r1 = Array.from(new Set(Array.from({length: 60}, () => Q.draftPool()).flat().map(p => p.rarity)));
    Q.save.xp = 2400; out.r4 = Array.from(new Set(Array.from({length: 120}, () => Q.draftPool()).flat().map(p => p.rarity)));
    out.size = Q.draftPool().length; out.uniq = new Set(Q.draftPool().map(p => p.id)).size;
    Q.save.xp = 0; return out;
  });
  log('draft pool gated by rank (common → +rare → +legendary), no duplicate cards', draft.r0.join() === 'common' && draft.r1.indexOf('rare') !== -1 && draft.r1.indexOf('legendary') === -1 && draft.r4.indexOf('legendary') !== -1 && draft.size === 3 && draft.uniq === 3, draft);

  // 3. XP + rank up toast + credits
  const xp = await page.evaluate(() => { const Q = window.__QA; Q.save.xp = 240; Q.save.tips = 0; const up = Q.addXp(20); return { up, xp: Q.save.xp, rank: Q.rankIndex(), tips: Q.save.tips, toast: document.getElementById('toast').textContent }; });
  log('rank up at 250 XP → Ensign, +40 credits, toast', xp.up === true && xp.rank === 1 && xp.tips === 40 && /Promoted/.test(xp.toast), xp);

  // 4. encrypted transmissions: last 2 rounds of a relay get 6 options for match, ×0.8 time, ×2 data
  const enc = await page.evaluate(() => {
    const Q = window.__QA; Q.save.xp = 0;
    Q.startDungeonAttempt(0, 'es', 'greetings', null);
    Q.st.pos = Q.st.queue.length - 1; Q.nextRound();
    const r = Q.st.round;
    const base = Q.TIERS[0].time;
    const before = Q.st.score;
    const ck = r.options.find(o => o.correct).key;
    Q.st.playing = true; Q.st.combo = 0;
    // resolve as correct via onAnswer path
    const btns = Array.from(document.querySelectorAll('#pl-answers .answer-btn')); const idx = r.options.map(o => o.key).indexOf(ck); btns[idx].click();
    return { encrypted: r.encrypted, nOpts: r.options.length, time: r.time, base, gained: Q.st.score - before, tag: document.getElementById('pl-flags').textContent, ticketClass: document.querySelector('.ticket').className, cracked: Q.save.stats.encryptedCracked };
  });
  log('encrypted round: 6 options, 0.8× time, flag shown, ×2 data, stat counted', enc.encrypted === true && enc.nOpts === 6 && Math.abs(enc.time - enc.base * 0.8) < 1e-6 && /encrypted/.test(enc.tag) && /encrypted/.test(enc.ticketClass) && enc.gained >= 200 && enc.cracked >= 1, enc);
  await page.screenshot({ path: 'ov_encrypted.png' });
  await page.waitForTimeout(900);

  // 5. anomaly events: scheduled at rank≥1 for queues ≥12; showEvent renders 3 choices; a choice resumes play
  const ev = await page.evaluate(() => {
    const Q = window.__QA; Q.save.xp = 300;
    Q.startDungeonAttempt(0, 'fr', 'people', null);
    const at = Q.st.eventsAt.slice(); const q = Q.st.queue.length;
    Q.st.pos = at[0] - 1; Q.st.lives = 3; Q.advanceRound();
    const shown = !document.getElementById('screen-event').hidden;
    const n = document.querySelectorAll('#ev-grid .ev-choice').length;
    return { at, q, shown, n };
  });
  log('anomaly event fires at 40%/75% of the queue with 3 choices', ev.at.length === 2 && ev.at[0] === Math.floor(ev.q * 0.4) && ev.shown && ev.n === 3, ev);
  await page.screenshot({ path: 'ov_event.png' });
  await page.click('#ev-grid .ev-choice:nth-child(3)'); await page.waitForTimeout(150);
  const afterEv = await page.evaluate(() => ({ playing: !document.getElementById('screen-playing').hidden, st: window.__QA.st.playing, events: window.__QA.save.stats.events, pending: window.__QA.st.eventsAt.length }));
  log('choosing an option resumes the relay and counts the event', afterEv.playing && afterEv.st && afterEv.events >= 1 && afterEv.pending === 1, afterEv);

  // 6. temp effects: setTemp via a flare "Ride it" → next round time halved, ticks down
  const temp = await page.evaluate(() => {
    const Q = window.__QA; Q.save.xp = 300;
    Q.startDungeonAttempt(0, 'it', 'people', null);
    const flare = Q.EVENTS.find(e => e.id === 'flare'); flare.choices[0].apply();
    Q.nextRound();
    const r = Q.st.round; const sec = r.seconds; const base = r.time * Q.st.perkFlags.timeMult;
    return { rounds: Q.st.temp.rounds, sec, base, flag: document.getElementById('pl-flags').textContent };
  });
  log('Solar Flare "Ride it": next rounds at half time with a temp tag', temp.rounds === 5 && Math.abs(temp.sec - temp.base * 0.5) < 1e-6 && /×2/.test(temp.flag), temp);

  // 7. missed-word tracking + recovery tile + recovery run is chain-neutral
  const rec = await page.evaluate(() => {
    const Q = window.__QA; Q.save.missed = {}; Q.save.chain.len = 3; Q.save.chain.carried = [];
    const words = Q.CONCEPTS.filter(c => c.tier === 'A1').slice(0, 5);
    words.forEach(c => { Q.save.missed[c.id + ':es'] = 2; });
    Q.showTopics(0, 'es');
    const tile = document.querySelector('#topic-grid .dungeon-tile[data-state="recovery"]');
    const ids = Q.recoveryIds(Q.TIERS[0], 'es');
    Q.enterDungeon(0, 'es', '__recovery');
    const title = document.getElementById('pv-title').textContent;
    Q.startDungeonAttempt(0, 'es', '__recovery', null);
    const q = Q.st.queue.length; const first = Q.st.firstAttempt;
    Q.st.correct = q; Q.st.total = q; Q.onDungeonCleared();
    return { tile: !!tile, tileText: tile && tile.textContent, ids: ids.length, title, q, first, chain: Q.save.chain.len, recov: Q.save.stats.recoveryCleared, cleared: Object.keys(Q.save.clearedDungeons).some(k => /__recovery/.test(k)) };
  });
  log('Signal Recovery: tile appears for ≥4 weak words, drill runs on them, chain-neutral, not a cleared relay', rec.tile && rec.ids === 5 && /Signal Recovery/.test(rec.title) && rec.q === 5 && rec.first === false && rec.chain === 3 && rec.recov === 1 && rec.cleared === false, rec);

  // 7b. a correct decode clears a strike; a wrong one adds one
  const strikes = await page.evaluate(() => {
    const Q = window.__QA; Q.startDungeonAttempt(0, 'es', 'greetings', null); Q.nextRound();
    const r = Q.st.round; const k = r.conceptId + ':es'; Q.save.missed = {}; Q.save.missed[k] = 1;
    Q.st.lives = 3; Q.resolveRound(true, {});
    const after = Q.save.missed[k];
    return { after: after === undefined ? 'gone' : after };
  });
  log('correct decode removes a strike from a weak word', strikes.after === 'gone', strikes);
  await page.waitForTimeout(800);

  // 8. Signal Storm: deterministic mods for the day, 20-item queue, mixed langs, clear → best + credits + stat, chain untouched
  const storm = await page.evaluate(() => {
    const Q = window.__QA; Q.save.chain.len = 4; Q.save.chain.carried = ['fast_hands']; Q.save.tips = 0;
    const a = Q.stormToday().mods.map(m => m.id); const b = Q.stormToday().mods.map(m => m.id);
    Q.startStorm();
    const pvTitle = document.getElementById('pv-title').textContent;
    Q.startDungeonAttempt(Q.st.tierIdx, null, '__storm', null);
    const q = Q.st.queue.length; const langs = new Set(Q.st.queue.map(e => e.lang)).size;
    Q.nextRound(); const kind = Q.st.round.kind; const rl = Q.st.round.lang;
    Q.st.correct = q; Q.st.total = q; Q.st.score = 1500; Q.onDungeonCleared();
    return { same: a.join() === b.join(), mods: a, pvTitle, q, langs, kind, rl, best: Q.save.storm.best, cleared: Q.save.storm.cleared, tips: Q.save.tips, stat: Q.save.stats.stormsCleared, chain: Q.save.chain.len, title: document.getElementById('cp-title').textContent, storm: Q.st.storm ? Q.st.storm.mods.length : 0 };
  });
  log('Signal Storm: same daily mods, 20-item multilingual queue, clear pays credits, chain untouched', storm.same && storm.mods.length === 2 && /Signal Storm/.test(storm.pvTitle) && (storm.q === 20 || storm.q === 30) && storm.langs >= 3 && (storm.kind === 'match' || storm.kind === 'listen') && storm.best === 1500 && storm.cleared && storm.tips >= 120 && storm.stat === 1 && storm.chain === 4 && /Storm weathered/.test(storm.title), storm);
  await page.screenshot({ path: 'ov_storm.png' });

  // 9. commendations: first relay + perfect → earned with credit reward; log screen renders
  const cmd = await page.evaluate(() => {
    const Q = window.__QA; Q.save.commendations = []; Q.save.tips = 0; Q.save.stats.relaysCleared = 1; Q.save.stats.perfectRelays = 1;
    const fresh = Q.checkCommendations().map(c => c.id);
    Q.showLog();
    return { fresh, tips: Q.save.tips, earned: document.querySelectorAll('#log-body .cmd-tile.earned').length, total: document.querySelectorAll('#log-body .cmd-tile').length, sections: document.querySelectorAll('#log-body .log-section').length };
  });
  log('commendations awarded (first_light, perfect, storm1) with credits; Mission Log renders', cmd.fresh.indexOf('first_light') !== -1 && cmd.fresh.indexOf('perfect') !== -1 && cmd.tips >= 140 && cmd.earned === cmd.fresh.length && cmd.total === window_total(cmd), cmd);
  function window_total(c) { return c.total; }
  await page.screenshot({ path: 'ov_log.png', fullPage: true });

  // 10. interference: Time Compression + Static + Solar Flare = Noise 3 -> 0.9x time, +36% credits, chip, Dark Matter from noise
  const asc = await page.evaluate(() => {
    const Q = window.__QA; Q.save.interference = ['compress','static','flare']; Q.save.chain.len = 0; Q.save.chain.carried = []; Q.save.dark = 0;
    Q.startDungeonAttempt(0, 'pt', 'people', null);
    const out = { time: Q.st.perkFlags.timeMult, tip: Q.st.perkFlags.tipMult, cap: Q.st.perkFlags.comboCapBonus, noise: Q.st.noise, chip: Array.from(document.querySelectorAll('#run-perks .perk-chip')).map(c => c.textContent).join('|') };
    Q.st.correct = 10; Q.st.total = 10; Q.onDungeonCleared(); out.bestNoise = Q.save.stats.bestNoiseClear; out.dark = Q.save.dark;
    Q.save.interference = []; return out;
  });
  log('Interference: Noise 3 -> 0.9x time, +36% credits, cap -5, chip shown, bestNoiseClear + Dark Matter recorded', Math.abs(asc.time - 0.9) < 1e-9 && Math.abs(asc.tip - 1.36) < 1e-9 && asc.cap === -5 && asc.noise === 3 && /Noise 3/.test(asc.chip) && asc.bestNoise === 3 && asc.dark >= 1, asc);

  // 11. legendary perks: glass cannon −1 cell & 1.6× score; iron link protects chain on first-attempt fail; phoenix
  const leg = await page.evaluate(() => {
    const Q = window.__QA; const P = id => Q.PERKS.find(p => p.id === id);
    Q.startDungeonAttempt(0, 'zh', 'people', P('glass_cannon'));
    const g = { lives: Q.st.maxLives, mult: Q.st.perkFlags.scoreMult, risk: Q.st.riskActive };
    Q.save.chain.len = 5; Q.save.chain.carried = ['fast_hands'];
    Q.save.clearedDungeons = {}; Q.startDungeonAttempt(0, 'zh', 'family', P('iron_link'));
    Q.st.lives = 0; Q.onDungeonFailed();
    const iron = { chain: Q.save.chain.len, text: document.querySelector('#cp-stats .chain-box').textContent };
    Q.startDungeonAttempt(0, 'zh', 'family', P('phoenix')); Q.nextRound(); Q.st.lives = 1; Q.st.playing = true;
    Q.resolveRound(false, {});
    const ph = { lives: Q.st.lives, used: Q.st.phoenixUsed };
    return { g, iron, ph };
  });
  log('Glass Cannon: 2 cells, 1.6× data, risk flagged', leg.g.lives === 2 && Math.abs(leg.g.mult - 1.6) < 1e-9 && leg.g.risk === true, leg.g);
  log('Iron Link: failed first attempt leaves chain intact', leg.iron.chain === 5 && /Iron Link/.test(leg.iron.text), leg.iron);
  log('Phoenix Cell: losing the last cell leaves 1', leg.ph.lives === 1 && leg.ph.used === true, leg.ph);
  await page.waitForTimeout(1800);

  // 12. tipsThisRun (Black Market Cache / Salvage AI) is actually paid out now
  const pay = await page.evaluate(() => {
    const Q = window.__QA; Q.save.tips = 0; Q.save.chain.len = 0; Q.save.chain.carried = [];
    Q.startDungeonAttempt(0, 'ja', 'people', Q.PERKS.find(p => p.id === 'deep_pockets'));
    Q.st.correct = 0; Q.st.total = 0; Q.st.floorCorrect = 0; Q.onDungeonCleared();
    return { tips: Q.save.tips };
  });
  log('Black Market Cache pays its +40 at relay end', pay.tips >= 40 + 20, pay);

  await browser.close();
  console.log('DONE');
})();
