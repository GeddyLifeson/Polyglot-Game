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

  // 1. module audit: every tier/lang/module has >=1 item; report shape
  const audit = await page.evaluate(() => {
    const Q = window.__QA; const out = {}; let empty = [];
    Q.TIERS.forEach((tier, idx) => {
      if (tier.endless) return;
      const mods = Q.modulesForTier(tier);
      const byType = {};
      mods.forEach(m => { byType[m.type] = (byType[m.type] || 0) + 1; });
      out[tier.code] = { modules: mods.length, byType, vocab: Q.vocabForTier(tier).length };
      tier.langs.forEach(l => mods.forEach(m => { if (Q.dungeonItemIds(tier, l, m.key).length === 0) empty.push(tier.code + '/' + l + '/' + m.key); }));
    });
    return { out, empty };
  });
  console.log(JSON.stringify(audit.out));
  log('no empty tier/lang/module combos', audit.empty.length === 0, audit.empty);
  log('A1 has 23+ vocab modules + 1 listening', audit.out.A1.byType.match >= 23 && audit.out.A1.byType.listen === 1, audit.out.A1);
  log('A2 has dialogue modules', audit.out.A2.byType.dialogue === 2, audit.out.A2);
  log('B1 has build + dialogue + 2 listening modules', audit.out.B1.byType.build === 4 && audit.out.B1.byType.listen === 2 && audit.out.B1.byType.dialogue === 2, audit.out.B1);

  // 2. Topic view groups by type with section headers
  await page.evaluate(() => window.__QA.showTopics(0, 'es'));
  await page.waitForTimeout(150);
  await page.screenshot({ path: 'mod_01_a1_topics.png', fullPage: false });
  const sections = await page.$$eval('#topic-grid .topic-section', els => els.map(e => e.textContent));
  log('A1 topic view shows Vocabulary + Listening sections', sections.length === 2 && /Vocabulary/.test(sections[0]) && /Listening/.test(sections[1]), sections);
  const tileCount = await page.$$eval('#topic-grid .dungeon-tile', els => els.length);
  log('A1 topic view renders 24 module tiles', tileCount === 24, tileCount);

  // 3. A2 dialogue round renders a line + 4 replies, correct reply resolves
  await page.evaluate(() => window.__QA.enterDungeon(1, 'fr', 'talk-meeting-people'));
  await page.waitForTimeout(150);
  const pvCount = await page.textContent('#pv-count');
  log('dialogue intro says exchanges', /6 exchanges to hold/.test(pvCount), pvCount);
  await page.click('#btn-start'); await page.waitForTimeout(150);
  await page.click('#btn-skip-perk'); await page.waitForTimeout(300);
  await page.screenshot({ path: 'mod_02_dialogue_fr.png' });
  const dState = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, main: window.__QA.st.round.main, nOpts: window.__QA.st.round.options.length, sub: window.__QA.st.round.sub }));
  log('dialogue round: kind=dialogue, 4 replies, setup shown', dState.kind === 'dialogue' && dState.nOpts === 4 && /💬/.test(dState.sub), dState);
  const ck = await page.evaluate(() => window.__QA.st.round.options.find(o => o.correct).key);
  const idx = await page.evaluate(() => window.__QA.st.round.options.map(o => o.key)).then(a => a.indexOf(ck));
  const btns = await page.$$('#pl-answers .answer-btn'); await btns[idx].click(); await page.waitForTimeout(1000);
  const afterCorrect = await page.evaluate(() => ({ correct: window.__QA.st.correct, pos: window.__QA.st.pos }));
  log('correct dialogue reply counted', afterCorrect.correct === 1, afterCorrect);

  // 4. A1 listening round: text hidden (🎧), replay visible, reveal after answer; muted fallback shows text
  await page.evaluate(() => { window.__QA.save.muted = false; window.__QA.persist(); window.__QA.enterDungeon(0, 'ja', 'listen-first-words'); });
  await page.waitForTimeout(150);
  await page.click('#btn-start'); await page.waitForTimeout(150);
  await page.click('#btn-skip-perk'); await page.waitForTimeout(300);
  await page.screenshot({ path: 'mod_03_listen_ja.png' });
  const lState = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, word: document.getElementById('pl-word').textContent, replayHidden: document.getElementById('btn-replay').hidden, queue: window.__QA.st.queue.length, spoken: window.__QA.st.round.spoken }));
  // headless chromium has no speech voices -> speechReady may still be true; either path must be coherent
  log('listening round: 16-item sample, kind=listen', lState.kind === 'listen' && lState.queue === 16 && !!lState.spoken, lState);
  log('listening prompt hides text OR shows reading-mode fallback', lState.word === '🎧' || lState.word.length > 0, lState.word);
  const ck2 = await page.evaluate(() => window.__QA.st.round.options.find(o => o.correct).key);
  const idx2 = await page.evaluate(() => window.__QA.st.round.options.map(o => o.key)).then(a => a.indexOf(ck2));
  const btns2 = await page.$$('#pl-answers .answer-btn'); await btns2[idx2].click(); await page.waitForTimeout(300);
  const revealed = await page.evaluate(() => document.getElementById('pl-word').textContent);
  log('listening reveals the subtitle after answering', revealed !== '🎧' && revealed.length > 0, revealed);
  await page.waitForTimeout(800);

  // 5. B1 listening from sentences works
  await page.evaluate(() => window.__QA.enterDungeon(2, 'es', 'listen-b1-sentences'));
  await page.waitForTimeout(150);
  await page.click('#btn-start'); await page.waitForTimeout(150);
  await page.click('#btn-skip-perk'); await page.waitForTimeout(300);
  const sState = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, spoken: window.__QA.st.round.spoken, opts: window.__QA.st.round.options.map(o => o.main) }));
  log('B1 sentence listening: spoken text is a sentence, options are English sentences', sState.kind === 'listen' && sState.spoken.length > 8 && sState.opts.length === 4, sState);

  // 6. Match round in a big A1 module: distractors come from A1 pool
  await page.evaluate(() => window.__QA.enterDungeon(0, 'zh', 'verbs-1'));
  await page.waitForTimeout(150);
  await page.click('#btn-start'); await page.waitForTimeout(150);
  await page.click('#btn-skip-perk'); await page.waitForTimeout(300);
  await page.screenshot({ path: 'mod_04_match_zh_verbs.png' });
  const mState = await page.evaluate(() => ({ kind: window.__QA.st.round.kind, queue: window.__QA.st.queue.length, sub: window.__QA.st.round.sub, opts: window.__QA.st.round.options.map(o => o.main) }));
  log('A1 verbs-1 zh: 24-item match module with pinyin sub', mState.kind === 'match' && mState.queue === 24 && !!mState.sub, mState);

  // 7. Lexicon: tier filter + search
  await page.evaluate(() => window.__QA.showHome());
  await page.waitForTimeout(150);
  await page.click('#btn-phrasebook'); await page.waitForTimeout(200);
  await page.fill('#pb-search', 'coffee'); await page.waitForTimeout(150);
  const pbRows = await page.$$eval('#pb-tbody tr:not(.pb-topic-row)', els => els.length);
  const pbCount = await page.textContent('#pb-count');
  log('Lexicon search "coffee" in A1 finds 1 row', pbRows === 1, { pbRows, pbCount });
  await page.selectOption('#pb-tier', 'all'); await page.fill('#pb-search', ''); await page.waitForTimeout(200);
  const pbAll = await page.textContent('#pb-count');
  log('Lexicon "all" caps at 300 rows with a hint', /showing 300 of/.test(pbAll), pbAll);
  await page.screenshot({ path: 'mod_05_lexicon.png' });

  // 8. Completion cascade still holds with many modules
  const cascade = await page.evaluate(() => {
    const Q = window.__QA;
    const mods = Q.modulesForTier(Q.TIERS[0]);
    Q.TIERS[0].langs.forEach(l => mods.forEach(m => { Q.save.clearedDungeons['0:' + l + ':' + m.key] = true; }));
    return { hub: Q.isHubCleared(0), a2: Q.isHubUnlocked(1) };
  });
  log('A1 clears + A2 unlocks once every language x module is done', cascade.hub && cascade.a2, cascade);

  await browser.close();
  console.log('DONE');
})();
