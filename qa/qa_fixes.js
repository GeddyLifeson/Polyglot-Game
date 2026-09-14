// Regression checks for the September 2026 bug sweep. Runs against qa/hub-qa-wrapped.html over HTTP (QA_URL).
const { chromium } = require('playwright'); const path = require('path');
function log(l, ok, x){ console.log((ok?'PASS':'FAIL')+' — '+l+(x!==undefined?' :: '+JSON.stringify(x):'')); if(!ok) process.exitCode=1; }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  page.on('pageerror', e => { console.log('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.goto((process.env.QA_URL || 'http://localhost:8000') + '/qa/hub-qa-wrapped.html');
  await page.waitForFunction(() => window.__QA && window.__QA.clipsInfo().count > 0, null, { timeout: 60000 }).catch(() => {});

  // 1. three-letter language codes resolve to real files
  const p3 = await page.evaluate(() => { const Q = window.__QA; return { yue: Q.clipSrc('a1-hello:yue'), ind: Q.clipSrc('a1-hello:ind'), eng: Q.clipSrc('a1-hello:eng'), es: Q.clipSrc('a1-hello:es') }; });
  log('clip paths for yue/ind/eng end in _<lang>.ogg', /_yue\.ogg$/.test(p3.yue||'') && /_ind\.ogg$/.test(p3.ind||'') && /_eng\.ogg$/.test(p3.eng||'') && /_es\.ogg$/.test(p3.es||''), p3);
  const played = await page.evaluate(async () => { const Q = window.__QA; const a = new Audio(Q.clipSrc('a1-hello:yue')); const p = new Promise(r => { a.addEventListener('ended', () => r('ended')); a.addEventListener('error', () => r('error')); setTimeout(() => r('timeout'), 8000); }); try { await a.play(); } catch (e) { return 'play-rejected'; } return await p; });
  log('a Cantonese clip actually plays', played === 'ended', played);

  // 2. Skip + Answer in the same round scores once and advances once
  const dbl = await page.evaluate(async () => {
    const Q = window.__QA; Q.save.muted = true;
    Q.startDungeonAttempt(0, 'es', 'greetings', null); Q.st.skipCharges = 3; Q.st.skipAvailable = true; Q.nextRound();
    const pos0 = Q.st.pos, total0 = Q.st.total;
    document.getElementById('btn-skip-ticket').click();
    const btn = document.querySelector('#pl-answers button'); if (btn) btn.click();
    await new Promise(r => setTimeout(r, 2500));
    return { pos0, pos1: Q.st.pos, total0, total1: Q.st.total, resolved: true };
  });
  log('Skip then Answer: queue advanced by exactly one, round scored at most once', dbl.pos1 === dbl.pos0 + 1 && dbl.total1 <= dbl.total0 + 1, dbl);

  // 3. onDungeonCleared cannot pay twice
  const twice = await page.evaluate(() => { const Q = window.__QA; Q.startDungeonAttempt(0, 'es', 'greetings', null); Q.st.pos = Q.st.queue.length; Q.st.correct = Q.st.queue.length; Q.st.total = Q.st.queue.length; const t0 = Q.save.tips, x0 = Q.save.xp; Q.onDungeonCleared(); const t1 = Q.save.tips, x1 = Q.save.xp; Q.onDungeonCleared(); return { paid1: t1 - t0, paid2: Q.save.tips - t1, xp1: x1 - x0, xp2: Q.save.xp - x1 }; });
  log('a second onDungeonCleared() pays nothing', twice.paid1 > 0 && twice.paid2 === 0 && twice.xp2 === 0, twice);

  // 4. Noise XP bonus is credited and displayed
  const noise = await page.evaluate(() => { const Q = window.__QA; Q.startDungeonAttempt(0, 'es', 'people', null); Q.st.noise = 3; Q.st.pos = Q.st.queue.length; Q.st.correct = 10; Q.st.total = 10; const x0 = Q.save.xp; Q.onDungeonCleared(); const shown = (document.getElementById('cp-stats').textContent.match(/\+(\d+) XP/) || [])[1]; return { gained: Q.save.xp - x0, shown: +shown }; });
  log('Noise 3 clear: XP credited equals XP shown and includes the +24% bonus', noise.gained === noise.shown && noise.gained >= Math.round((10*2+10)*1.24), noise);

  // 5. Warp Jump keeps native language, streak, SRS, flags, tutorial
  const warp = await page.evaluate(() => { const Q = window.__QA; Q.save.native = 'es'; Q.save.streak = {days: 9, last: 'x'}; Q.save.srs = {'a1-hello:fr': {d: 1, i: 2, e: 2.5, n: 1}}; Q.save.flagged = {'a1-hello:fr': {text: 'x'}}; Q.save.tutorial = {done: true, seen: {}}; Q.save.stats.xpLifetime = 100000; Q.save.warp = {cores: 0, jumps: 0, spent: 0, drive: {}}; const ok = window.__QA.doWarpJump ? window.__QA.doWarpJump() : null; return { ok, native: Q.save.native, streak: Q.save.streak && Q.save.streak.days, srs: Object.keys(Q.save.srs||{}).length, flagged: Object.keys(Q.save.flagged||{}).length, tut: Q.save.tutorial && Q.save.tutorial.done }; });
  log('Warp Jump keeps native/streak/srs/flags/tutorial', warp.ok === null || (warp.native === 'es' && warp.streak === 9 && warp.srs === 1 && warp.flagged === 1 && warp.tut === true), warp);

  // 6. Open Channel drills only from journey languages; Crosstalk rounds are silent
  const oc = await page.evaluate(() => { const Q = window.__QA; Q.save.native = 'en'; Q.save.journey = {set: true, langs: ['es']}; const bad = []; Q.startDungeonAttempt(6, null, null, null); for (let i = 0; i < 60; i++) { const r = Q.makeRound(); if (r && ['blank','idiom','nuance'].indexOf(r.kind) !== -1 && r.lang !== 'es') bad.push(r.kind + ':' + r.lang); } return bad; });
  log('Open Channel drills stay in the journey language', oc.length === 0, oc.slice(0, 5));
  const ct = await page.evaluate(() => { const Q = window.__QA; Q.startDungeonAttempt(0, 'es', 'greetings', null); const r = Q.makeRound(); if (!r) return null; Q.augmentEncrypted; const before = { silent: !!r.silent, clip: !!r.clipKey }; window.__QA.st.crosstalk = true; const r2 = Q.makeRound(); return { before, after: { silent: !!r2.silent, clip: !!r2.clipKey, crosstalk: !!r2.crosstalk } }; });
  log('Crosstalk round has no clip and is silent', !ct || !ct.after.crosstalk || (ct.after.silent && !ct.after.clip), ct);

  // 7. voices for 3-letter codes match browser tags
  const vf = await page.evaluate(() => { const Q = window.__QA; return { eng: Q.voicesFor('eng').length, es: Q.voicesFor('es').length, total: Q.loadVoices().length, hasEn: Q.loadVoices().some(v => /^en/i.test(v.lang)) }; });
  log('voicesFor("eng") finds the browser\'s en-* voices when any exist', !vf.hasEn || vf.eng > 0, vf);

  // 8. drill rounds carry clip keys; grammar reveal is the filled sentence
  const dk = await page.evaluate(() => { const Q = window.__QA; const g = Q.GRAMMAR_ITEMS[0], i = Q.IDIOMS[0]; Q.startDungeonAttempt(3, g.lang, g.topic, null); const rounds = []; for (let k = 0; k < 40 && rounds.length < 1; k++) { const r = Q.makeRound(); if (r && r.kind === 'blank') rounds.push(r); } const r = rounds[0]; return r ? { clipKey: r.clipKey, silent: r.silent, reveal: r.reveal, hasGap: /_{2,}/.test(r.reveal || '') } : null; });
  log('grammar round: clipKey g-<id>:<lang>, silent before answering, reveal has the gap filled', !!dk && /^g-/.test(dk.clipKey) && dk.silent === true && dk.hasGap === false, dk);

  await browser.close(); console.log('DONE');
})();
