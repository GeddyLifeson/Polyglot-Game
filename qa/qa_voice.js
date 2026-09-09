const { chromium } = require('playwright'); const path = require('path');
function log(l, ok, x){ console.log((ok?'PASS':'FAIL')+' — '+l+(x!==undefined?' :: '+JSON.stringify(x):'')); if(!ok) process.exitCode=1; }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 } });
  page.on('pageerror', e => { console.log('PAGE ERROR:', e.message); process.exitCode = 1; });
  await page.addInitScript(() => {
    const mk = (name, lang, local) => ({ name, lang, voiceURI: name, localService: !!local, default: false });
    const fake = [mk('Google US English','en-US'), mk('Microsoft Zira','en-US',true), mk('Google español','es-ES'), mk('Microsoft Elvira Online (Natural) - Spanish (Spain)','es-ES'),
      mk('eSpeak Spanish','es', true), mk('Google français','fr-FR'), mk('Alice','it-IT',true), mk('Luciana','pt-BR',true), mk('Joana','pt-PT',true), mk('Kyoko','ja-JP',true), mk('Tingting','zh-CN',true), mk('Google 普通话（中国大陆）','zh-CN')];
    const spoken = []; window.__spoken = spoken;
    Object.defineProperty(window, 'speechSynthesis', { value: { getVoices: () => fake, cancel: () => {}, speak: u => spoken.push({ text: u.text, voice: u.voice && u.voice.name, lang: u.lang, rate: u.rate }), onvoiceschanged: null }, configurable: true });
    window.SpeechSynthesisUtterance = function(t){ this.text = t; };
  });
  await page.goto('file://' + path.resolve(__dirname, 'hub-qa-wrapped.html')); await page.waitForTimeout(300);
  const pick = await page.evaluate(() => { const Q = window.__QA; const o = {}; ['es','fr','it','pt','ja','zh'].forEach(l => { const v = Q.voiceFor(l); o[l] = v && v.name; }); return o; });
  log('best native voice per language (Natural > Google > local; pt-BR first; never eSpeak)', pick.es.indexOf('Natural') !== -1 && pick.fr === 'Google français' && pick.it === 'Alice' && pick.pt === 'Luciana' && pick.ja === 'Kyoko' && pick.zh.indexOf('Google') !== -1, pick);
  const sp = await page.evaluate(() => { const Q = window.__QA; Q.save.muted = false; Q.speakText('{食|た}べる (comer)', 'ja', true); Q.speakText('El gobierno anunció nuevas medidas.', 'es', true); return window.__spoken; });
  log('utterances carry the native voice, stripped furigana/gloss, sensible rate', sp[0].voice === 'Kyoko' && sp[0].text === '食べる' && sp[0].rate === 0.85 && sp[1].voice.indexOf('Natural') !== -1 && sp[1].rate === 0.92, sp);
  const ovr = await page.evaluate(() => { const Q = window.__QA; Q.save.voices = { es: 'Google español' }; return Q.voiceFor('es').name; });
  log('player override respected', ovr === 'Google español', ovr);
  await page.click('#btn-voices'); await page.waitForTimeout(150);
  const panel = await page.evaluate(() => ({ hidden: document.getElementById('voices-overlay').hidden, rows: document.querySelectorAll('#voices-body .voice-row').length, sels: document.querySelectorAll('#voices-body .voice-sel').length, esOpts: document.querySelector('.voice-sel[data-lang="es"]').options.length }));
  log('Voices panel: 6 rows, selects for every language, eSpeak listed last', !panel.hidden && panel.rows === 6 && panel.sels === 6 && panel.esOpts === 3, panel);
  await page.screenshot({ path: 'voice_panel.png' });
  await page.selectOption('.voice-sel[data-lang="zh"]', 'Tingting'); await page.waitForTimeout(100);
  const after = await page.evaluate(() => ({ saved: window.__QA.save.voices.zh, last: window.__spoken[window.__spoken.length-1] }));
  log('changing a voice saves it and plays a sample', after.saved === 'Tingting' && after.last.voice === 'Tingting' && /早上好/.test(after.last.text), after);
  const missing = await page.evaluate(() => { const Q = window.__QA; Object.defineProperty(window, 'speechSynthesis', { value: { getVoices: () => [{name:'Google US English', lang:'en-US', voiceURI:'x'}], cancel: () => {}, speak: () => {} }, configurable: true }); Q.loadVoices(); Q.speakText('bonjour','fr',true); return document.getElementById('toast').textContent; });
  log('missing native voice → clear warning', /No French voice/.test(missing), missing.slice(0, 60));
  await browser.close(); console.log('DONE');
})();
