// The reading line in the learner's own script: load the game over HTTP with several native languages, check that
// pron/<lang>.json arrives, that the line under a target-language word is written in the native script (katakana for
// a Japanese speaker, Hangul for Korean, an English respelling for English, ...), that every native engine renders
// every target language without errors, and that the "show IPA" toggle adds the IPA.
// Run with: node qa/with_server.js qa/qa_pron.js   (screenshots go to $SHOT_DIR or cwd)
const { chromium } = require('playwright');
const path = require('path');
function log(label, ok, extra) {
  console.log((ok ? 'PASS' : 'FAIL') + ' — ' + label + (extra !== undefined ? ' :: ' + JSON.stringify(extra).slice(0, 400) : ''));
  if (!ok) process.exitCode = 1;
}
const BASE = (process.env.QA_URL || 'http://localhost:8000') + '/qa/hub-qa-wrapped.html';
const SHOTS = process.env.SHOT_DIR || '.';
const SCRIPT = {
  en: /^[A-Za-z' -]+$/, ja: /^[゠-ヿ・ー]+$/, ko: /^[가-힣 ]+$/, ar: /^[؀-ۿ ]+$/, ru: /^[Ѐ-ӿ́ ]+$/,
  el: /^[Ͱ-Ͽἀ-῿ ]+$/, hi: /^[ऀ-ॿ ]+$/, zh: /^[a-zü -]+$/, yue: /^[a-z -]+$/,
};
// native -> journey languages to try (never the native itself)
const CASES = [['en', ['ru', 'zh']], ['ja', ['ru', 'es']], ['ko', ['fr', 'ja']], ['ar', ['de', 'ko']], ['ru', ['eng', 'ja']],
               ['zh', ['es', 'ru']], ['hi', ['eng', 'fr']], ['el', ['it', 'zh']], ['es', ['ru', 'ja']], ['yue', ['eng', 'de']]];

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  for (const [nat, langs] of CASES) {
    const ctx = await browser.newContext({ viewport: { width: 430, height: 900 } });
    await ctx.addInitScript(([nat, langs]) => {
      try { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1');
        localStorage.setItem('polyglotBistro.v2', JSON.stringify({ native: nat, journey: { langs: langs, set: true }, tutorial: { done: true, seen: {} }, xp: 3000, tips: 5000 })); } } catch (e) {}
    }, [nat, langs]);
    const page = await ctx.newPage();
    page.on('pageerror', e => { console.log('PAGE ERROR (' + nat + '):', e.message); process.exitCode = 1; });
    await page.goto(BASE);
    await page.waitForFunction((langs) => window.__QA && langs.every(l => window.__QA.PRON.data[l]), langs, { timeout: 15000 }).catch(() => {});
    const loaded = await page.evaluate((langs) => langs.filter(l => window.__QA.PRON.data[l]), langs);
    log(nat + ': pron files loaded for ' + langs.join('+'), loaded.length === langs.length, loaded);

    // a sample of words per journey language, rendered for this native
    const sample = await page.evaluate((langs) => {
      const Q = window.__QA; const out = {};
      langs.forEach(l => { out[l] = Q.CONCEPTS.filter(c => c[l]).filter((c, i) => i % 400 === 0).map(c => [c[l].t, Q.pronLine(l, c[l].t, c[l].r)]); });
      return out;
    }, langs);
    for (const l of langs) {
      const lines = sample[l]; const empty = lines.filter(x => !x[1]);
      log(nat + ' reading ' + l + ': every sampled word has a line', empty.length === 0, empty.slice(0, 3));
      if (SCRIPT[nat]) {
        const bad = lines.filter(x => x[1] && !SCRIPT[nat].test(x[1].replace(/[A-Z]/g, c => c.toLowerCase()).replace(/[.,!?¿¡'’"“”()]/g, '')));
        log(nat + ' reading ' + l + ': written in the native script', bad.length <= Math.ceil(lines.length * 0.05), bad.slice(0, 4));
      }
      console.log('   ' + nat + '←' + l + ': ' + lines.slice(0, 4).map(x => x[0] + ' → ' + x[1]).join(' | '));
    }

    // a real relay: the prompt's reading line is filled in and options carry theirs
    await page.evaluate((l) => window.__QA.enterDungeon(0, l, window.__QA.topicsForTier(window.__QA.TIERS[0])[0]), langs[0]);
    await page.waitForTimeout(150);
    await page.click('#btn-start'); await page.waitForTimeout(150);
    const perk = await page.$('#btn-skip-perk'); if (perk && await perk.isVisible()) { await perk.click(); await page.waitForTimeout(300); }
    const r = await page.evaluate(() => { const e = document.getElementById('pl-romaji'); return { kind: window.__QA.st.round && window.__QA.st.round.kind, main: document.getElementById('pl-word').textContent, line: e.textContent, hidden: e.hidden, pl: e.getAttribute('data-pl') }; });
    log(nat + ': relay prompt shows a reading line', !!r.pl && !r.hidden && r.line.length > 0, r);
    await page.screenshot({ path: path.join(SHOTS, 'pron_' + nat + '_' + langs[0] + '.png') });

    // the IPA toggle adds /ipa/
    await page.evaluate(() => { window.__QA.save.showIpa = true; window.__QA.pronRefresh(); });
    const withIpa = await page.evaluate(() => document.getElementById('pl-romaji').textContent);
    log(nat + ': IPA toggle adds the IPA', /\/.+\//.test(withIpa), withIpa);
    await page.screenshot({ path: path.join(SHOTS, 'pron_' + nat + '_' + langs[0] + '_ipa.png') });
    await page.evaluate(() => { window.__QA.save.showIpa = false; window.__QA.pronRefresh(); });
    await ctx.close();
  }

  // every native engine x every target language: no exceptions, no empty output, on a slice of the data
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(BASE);
  const all = await page.evaluate(async () => {
    const Q = window.__QA; const langs = Object.keys(Q.LANG_META).filter(l => l !== 'eng').concat(['eng']);
    const natives = ['en'].concat(Object.keys(Q.LANG_META).filter(l => l !== 'eng'));
    const base = window.PRON_BASE || 'pron/'; const res = { pairs: 0, strings: 0, empty: [], errors: [], ms: 0 };
    for (const l of langs) {
      const j = await fetch(base + l + '.json').then(r => r.json()); const keys = Object.keys(j.ipa).filter((k, i) => i % 25 === 0);
      for (const n of natives) {
        if (n === l || (n === 'en' && l === 'eng')) continue; res.pairs++;
        const t0 = performance.now();
        for (const k of keys) {
          res.strings++;
          try { const s = Q.PRON.respell(j.ipa[k], n, l); if (!s) res.empty.push(n + '←' + l + ':' + k); } catch (e) { res.errors.push(n + '←' + l + ':' + e.message); }
        }
        res.ms += performance.now() - t0;
      }
    }
    return res;
  });
  log('every native engine renders every target language (' + all.pairs + ' pairs, ' + all.strings + ' strings, ' + Math.round(all.ms) + ' ms)', all.errors.length === 0 && all.empty.length <= all.strings * 0.002, { errors: all.errors.slice(0, 5), empty: all.empty.length, sample: all.empty.slice(0, 5) });
  await browser.close();
})();
