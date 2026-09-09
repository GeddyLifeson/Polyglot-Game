// Recordings QA. Works for both audio builds:
//   - external: audio/<TIER>/<id>_<lang>.ogg listed in audio/manifest.json (this repo's default; needs HTTP)
//   - embedded: AUDIO_CLIPS populated by tools/embed_audio.py (single-file build)
const { chromium } = require('playwright'); const path = require('path');
function log(l, ok, x){ console.log((ok?'PASS':'FAIL')+' — '+l+(x!==undefined?' :: '+JSON.stringify(x):'')); if(!ok) process.exitCode=1; }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  page.on('pageerror', e => { console.log('PAGE ERROR:', e.message); process.exitCode = 1; });
  const t0 = Date.now();
  await page.goto((process.env.QA_URL || 'http://localhost:8000') + '/qa/hub-qa-wrapped.html');
  // the external manifest is fetched asynchronously after load
  await page.waitForFunction(() => window.__QA && window.__QA.clipsInfo().count > 0, null, { timeout: 15000 }).catch(() => {});
  const load = Date.now() - t0;
  const info = await page.evaluate(() => {
    const Q = window.__QA; const L = ['es','fr','it','pt','ja','zh'];
    const mode = Object.keys(Q.AUDIO_CLIPS).length ? 'embedded' : 'external';
    const cov = {};
    Q.clipsInfo().tiers.forEach(t => { const cs = Q.CONCEPTS.filter(c => c.tier === t); cov[t] = { words: cs.length, covered: cs.filter(c => L.every(l => Q.hasClip(c.id+':'+l))).length }; });
    return { mode, info: Q.clipsInfo(), cov, support: document.createElement('audio').canPlayType('audio/ogg; codecs="opus"') };
  });
  console.log('audio mode: ' + info.mode + ' ' + JSON.stringify(info.info));
  const allCovered = info.info.tiers.length > 0 && info.info.tiers.every(t => info.cov[t].covered === info.cov[t].words);
  log('recordings found for A1 + A2 — every word in all six languages; page loads', info.info.count === 7476 && /^A1,A2$/.test(info.info.tiers.join(',')) && allCovered && load < 60000, { ...info, loadMs: load });
  // speakText takes the recording branch when a clip exists
  const play = await page.evaluate(async () => {
    const Q = window.__QA; Q.save.muted = false;
    const c = Q.CONCEPTS.find(x => x.id === 'a1-hello');
    Q.speakText(c.ja.t, 'ja', true, 'a1-hello:ja');
    await new Promise(r => setTimeout(r, 300));
    return { hasClip: Q.hasClip('a1-hello:ja'), src: Q.clipSrc('a1-hello:ja') };
  });
  log('speakText prefers the built-in recording when one exists', play.hasClip === true && !!play.src, play);
  // real playback check: create Audio from the resolved clip source and wait for 'ended'
  const ended = await page.evaluate(async () => { const Q = window.__QA; const a = new Audio(Q.clipSrc('a1-hello:es')); const p = new Promise(r => { a.addEventListener('ended', () => r('ended')); a.addEventListener('error', () => r('error')); setTimeout(() => r('timeout'), 8000); }); try { await a.play(); } catch (e) { return 'play-rejected:' + e.message; } return { r: await p, dur: a.duration, src: a.currentSrc.slice(0, 80) }; });
  log('an Opus clip decodes and plays to the end in Chromium', ended.r === 'ended' && ended.dur > 0.3, ended);
  // a match round in A1 gets a clipKey; a tier without recordings (B1) falls back to the TTS path
  const rt = await page.evaluate(() => { const Q = window.__QA; Q.startDungeonAttempt(0, 'es', 'greetings', null); Q.nextRound(); const r = Q.st.round; const b1 = Q.CONCEPTS.find(c => c.tier === 'B1'); return { kind: r.kind, key: r.conceptId + ':' + r.lang, has: Q.hasClip(r.conceptId + ':' + r.lang), b1: Q.hasClip(b1.id + ':es'), missing: Q.hasClip('a2-no-such-word:es') }; });
  log('A1 rounds have recordings; unrecorded bands fall back to device voice', rt.has === true && rt.b1 === false && rt.missing === false, rt);
  const toggle = await page.evaluate(() => { const Q = window.__QA; Q.save.useClips = false; const off = Q.hasClip('a1-hello:es'); Q.save.useClips = true; return off; });
  log('"Use built-in recordings" toggle disables clips', toggle === false);
  await page.click('#btn-voices'); await page.waitForTimeout(150);
  const panel = await page.evaluate(() => document.getElementById('voices-body').textContent.slice(0, 160));
  log('Voices panel explains the studio recordings', /7,476 native-speaker recordings/.test(panel), panel);
  await page.screenshot({ path: 'clips_panel.png' });
  await browser.close(); console.log('DONE');
})();
