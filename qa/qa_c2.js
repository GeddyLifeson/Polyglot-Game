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

  // C2 topic view sections
  await page.evaluate(() => window.__QA.showTopics(5, 'es'));
  await page.waitForTimeout(100);
  const sections = await page.$$eval('#topic-grid .topic-section', els => els.map(e => e.textContent));
  await page.screenshot({ path: 'c2_topics.png' });
  log('C2 topic view sections', sections.length >= 5, sections);

  // C2 nuance round (ja)
  await page.evaluate(() => window.__QA.enterDungeon(5, 'ja', 'nuance-spoken-register'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const n = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, main: window.__QA.st.round.main, nOpts: window.__QA.st.round.options.length, queue: window.__QA.st.queue.length }));
  log('C2 nuance-spoken-register ja: 2 items, 4 options', n.kind === 'nuance' && n.nOpts === 4 && n.queue === 2, n);

  // C2 tone-shades zh
  await page.evaluate(() => window.__QA.enterDungeon(5, 'zh', 'nuance-tone-shades'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const n2 = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length, main: window.__QA.st.round.main }));
  log('C2 nuance-tone-shades zh', n2.kind === 'nuance' && n2.queue === 2, n2);

  // C2 dialogue (pt)
  await page.evaluate(() => window.__QA.enterDungeon(5, 'pt', 'talk-heated-debate'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const d = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, main: window.__QA.st.round.main, nOpts: window.__QA.st.round.options.length, queue: window.__QA.st.queue.length, sub: window.__QA.st.round.sub }));
  log('C2 heated-debate pt: 4 dialogues, 4 replies', d.kind === 'dialogue' && d.nOpts === 4 && d.queue === 4, d);

  // C2 build (it)
  await page.evaluate(() => window.__QA.enterDungeon(5, 'it', 'build-native-lines'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const b = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length, main: window.__QA.st.round.main }));
  log('C2 build-native-lines it: 12 sentences', b.kind === 'build' && b.queue === 12, b);

  // C2 listen sentences (fr), time 7s
  await page.evaluate(() => { window.__QA.save.muted = false; window.__QA.persist(); window.__QA.enterDungeon(5, 'fr', 'listen-c2-lines'); });
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const l = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length, spoken: window.__QA.st.round.spoken, time: window.__QA.st.round.time || window.__QA.st.roundTime || null }));
  log('C2 listen-c2-lines fr: 12 native-speed lines', l.kind === 'listen' && l.queue === 12 && /\S/.test(l.spoken), l);

  // C2 listen words (es) 20 sample
  await page.evaluate(() => window.__QA.enterDungeon(5, 'es', 'listen-c2-words'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const lw = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length }));
  log('C2 listen-c2-words es: 20 sample', lw.kind === 'listen' && lw.queue === 20, lw);

  // C2 match module (proverbs, zh) — check pinyin sub present
  await page.evaluate(() => window.__QA.enterDungeon(5, 'zh', 'proverbs-sayings'));
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150); var sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const m = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length, main: window.__QA.st.round.main, sub: window.__QA.st.round.sub }));
  log('C2 proverbs zh: 30 items with pinyin', m.kind === 'match' && m.queue === 30 && /[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]/.test(m.sub), m);

  // Lexicon: C2 filter count
  const pb = await page.evaluate(() => { window.__QA.renderPhrasebook && document.getElementById('pb-tier') && (document.getElementById('pb-tier').value = '5'); return null; });
  // total unique check
  const uniq = await page.evaluate(() => { const s = new Set(window.__QA.CONCEPTS.map(c => c.en.toLowerCase())); return { total: window.__QA.CONCEPTS.length, unique: s.size }; });
  log('5,000+ unique English concepts', uniq.unique >= 5000 && uniq.unique === uniq.total, uniq);

  // furigana sanity: all ja strings with braces are well-formed {x|y}
  const bad = await page.evaluate(() => {
    const re = /\{[^{}|]+\|[^{}|]+\}/g; let bad = [];
    window.__QA.CONCEPTS.forEach(c => { const s = (c.ja && c.ja.t) || ''; const stripped = s.replace(re, ''); if (/[{}|]/.test(stripped)) bad.push(c.id + ':' + s); });
    return bad.slice(0, 10);
  });
  log('furigana well-formed in all ja vocab', bad.length === 0, bad);

  await browser.close();
  console.log('DONE');
})();
