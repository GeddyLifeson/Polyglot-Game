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
  const Q = () => window.__QA;

  // 0. shop renders 6 categories and all upgrades
  await page.evaluate(() => window.__QA.showShop());
  await page.waitForTimeout(100);
  const shop = await page.evaluate(() => ({ cats: document.querySelectorAll('#shop-grid .shop-cat').length, items: document.querySelectorAll('#shop-grid .shop-item').length, n: window.__QA.SHOP_UPGRADES.length }));
  log('shop: 6 categories, all upgrades rendered', shop.cats === 6 && shop.items === shop.n && shop.n >= 42, shop);
  await page.screenshot({ path: 'chain_shop.png', fullPage: true });

  // 1. fresh chain; preview shows chain box for first attempt
  await page.evaluate(() => window.__QA.enterDungeon(0, 'es', 'greetings'));
  await page.waitForTimeout(150);
  const pv = await page.evaluate(() => ({ hidden: document.getElementById('pv-chain').hidden, text: document.getElementById('pv-chain').textContent }));
  log('preview: chain box visible with first-attempt text', !pv.hidden && /First attempt/.test(pv.text) && /0 links/.test(pv.text), pv.text.slice(0, 120));
  await page.screenshot({ path: 'chain_preview.png' });

  // 2. first clear with a drafted perk → chain 1, perk welded
  const r1 = await page.evaluate(() => {
    const Q = window.__QA; const perk = Q.PERKS.filter(p => p.id === 'fast_hands')[0];
    Q.startDungeonAttempt(0, 'es', 'greetings', perk);
    Q.st.correct = 10; Q.st.total = 10; Q.st.floorCorrect = 10;
    Q.onDungeonCleared();
    return { len: Q.save.chain.len, carried: Q.save.chain.carried, text: document.querySelector('#cp-stats .chain-box').textContent };
  });
  log('first clear: chain=1, Overclock welded', r1.len === 1 && r1.carried.join() === 'fast_hands' && /Chain extended/.test(r1.text), r1);
  await page.screenshot({ path: 'chain_complete.png' });

  // 3. next first attempt: carried perk auto-applied + strip shows carried chip
  const r2 = await page.evaluate(() => {
    const Q = window.__QA;
    Q.startDungeonAttempt(0, 'es', 'people', null);
    return { carried: Q.st.carriedPerkIds, active: Q.st.activePerkIds, timeMult: Q.st.perkFlags.timeMult, chips: Array.from(document.querySelectorAll('#run-perks .perk-chip')).map(c => c.className + ':' + c.textContent) };
  });
  log('carried module auto-applies on next relay', r2.carried.join() === 'fast_hands' && Math.abs(r2.timeMult - 1.2) < 1e-9 && r2.chips.some(c => /carried/.test(c)), r2);

  // 4. re-run (already cleared) fails → chain unaffected
  const r3 = await page.evaluate(() => {
    const Q = window.__QA;
    Q.startDungeonAttempt(0, 'es', 'greetings', null); // cleared already → re-run
    Q.st.lives = 0; Q.onDungeonFailed();
    return { len: Q.save.chain.len, carried: Q.save.chain.carried, first: Q.st.firstAttempt, text: document.querySelector('#cp-stats .chain-box').textContent };
  });
  log('re-run failure leaves chain untouched', r3.len === 1 && r3.carried.length === 1 && r3.first === false && /Re-run/.test(r3.text), r3);

  // 4b. re-run success also neutral
  const r3b = await page.evaluate(() => {
    const Q = window.__QA;
    Q.startDungeonAttempt(0, 'es', 'greetings', Q.PERKS[0]);
    Q.st.correct = 5; Q.st.total = 5; Q.st.floorCorrect = 5; Q.onDungeonCleared();
    return { len: Q.save.chain.len, carried: Q.save.chain.carried };
  });
  log('re-run success does not extend chain or weld', r3b.len === 1 && r3b.carried.length === 1, r3b);

  // 5. milestones: chain 3 → +1 cell, +10% time; Amplifier shifts thresholds
  const r4 = await page.evaluate(() => {
    const Q = window.__QA; Q.save.chain.len = 3; Q.save.chain.carried = [];
    Q.startDungeonAttempt(0, 'fr', 'people', null);
    const a = { lives: Q.st.maxLives, time: Q.st.perkFlags.timeMult, ms: Q.st.chainMilestoneNames.map(m => m.name) };
    Q.save.shopOwned.push('shop_amp'); Q.save.chain.len = 3;
    Q.startDungeonAttempt(0, 'fr', 'people', null);
    const b = { lives: Q.st.maxLives, ms: Q.st.chainMilestoneNames.map(m => m.name), soft: Q.st.perkFlags.softCombo };
    Q.save.shopOwned.splice(Q.save.shopOwned.indexOf('shop_amp'), 1);
    return { a, b };
  });
  log('milestones at chain 3: Warm Signal + Chain Cell (4 cells, 1.1x time)', r4.a.lives === 4 && Math.abs(r4.a.time - 1.1) < 1e-9 && r4.a.ms.join() === 'Warm Signal,Chain Cell', r4.a);
  log('Chain Amplifier: Sync Memory (at 5) fires at 3', r4.b.ms.indexOf('Sync Memory') !== -1 && r4.b.soft === true, r4.b);

  // 6. first-attempt failure breaks chain; Anchor keeps half; Insurance absorbs and is consumed
  const r5 = await page.evaluate(() => {
    const Q = window.__QA;
    Q.save.chain.len = 7; Q.save.chain.carried = ['fast_hands', 'big_tipper'];
    Q.startDungeonAttempt(0, 'it', 'people', null); Q.st.lives = 0; Q.onDungeonFailed();
    const plain = { len: Q.save.chain.len, carried: Q.save.chain.carried.slice(), text: document.querySelector('#cp-stats .chain-box').textContent };
    Q.save.chain.len = 7; Q.save.chain.carried = ['fast_hands', 'big_tipper']; Q.save.shopOwned.push('shop_anchor');
    Q.startDungeonAttempt(0, 'it', 'people', null); Q.st.lives = 0; Q.onDungeonFailed();
    const anchor = { len: Q.save.chain.len, carried: Q.save.chain.carried.slice() };
    Q.save.shopOwned.splice(Q.save.shopOwned.indexOf('shop_anchor'), 1);
    Q.save.chain.len = 7; Q.save.chain.carried = ['fast_hands', 'big_tipper']; Q.save.shopOwned.push('shop_insure');
    Q.startDungeonAttempt(0, 'it', 'people', null); Q.st.lives = 0; Q.onDungeonFailed();
    const ins = { len: Q.save.chain.len, carried: Q.save.chain.carried.slice(), stillOwned: Q.save.shopOwned.indexOf('shop_insure') !== -1 };
    return { plain, anchor, ins };
  });
  log('first-attempt failure breaks chain to 0 and drops welded modules', r5.plain.len === 0 && r5.plain.carried.length === 0 && /Chain broken/.test(r5.plain.text), r5.plain);
  log('Chain Anchor keeps half (3) + newest module', r5.anchor.len === 3 && r5.anchor.carried.join() === 'big_tipper', r5.anchor);
  log('Chain Insurance absorbs break and is consumed', r5.ins.len === 7 && r5.ins.carried.length === 2 && r5.ins.stillOwned === false, r5.ins);

  // 7. carry cap + Resonance Link (+2 on perfect first clear)
  const r6 = await page.evaluate(() => {
    const Q = window.__QA;
    Q.save.chain.len = 0; Q.save.chain.carried = ['extra_life', 'big_tipper'];
    Q.save.shopOwned.push('shop_double');
    Q.startDungeonAttempt(0, 'pt', 'people', Q.PERKS.filter(p => p.id === 'sharp_tongue')[0]);
    Q.st.correct = 12; Q.st.total = 12; Q.st.floorCorrect = 12; Q.onDungeonCleared();
    const out = { len: Q.save.chain.len, carried: Q.save.chain.carried.slice(), cap: Q.carryCap() };
    Q.save.shopOwned.splice(Q.save.shopOwned.indexOf('shop_double'), 1);
    return out;
  });
  log('perfect first clear with Resonance = +2; carry cap 2 drops oldest', r6.len === 2 && r6.carried.join() === 'big_tipper,sharp_tongue' && r6.cap === 2, r6);

  // 8. Scan charges: buy Signal Filter, start a relay, scan disables one wrong option
  await page.evaluate(() => { const Q = window.__QA; Q.save.shopOwned.push('shop_scan1'); Q.save.chain.len = 0; Q.save.chain.carried = []; Q.enterDungeon(0, 'ja', 'colors-shapes'); });
  await page.waitForTimeout(150); await page.click('#btn-start'); await page.waitForTimeout(150);
  const sk = await page.$('#btn-skip-perk'); if (sk && await sk.isVisible()) { await sk.click(); await page.waitForTimeout(250); }
  const scanBefore = await page.evaluate(() => ({ charges: window.__QA.st.scanCharges, btnHidden: document.getElementById('btn-scan').hidden }));
  await page.click('#btn-scan'); await page.waitForTimeout(100);
  const scanAfter = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('#pl-answers .answer-btn'));
    const disabledIdx = btns.map((b, i) => b.disabled ? i : -1).filter(i => i >= 0);
    return { charges: window.__QA.st.scanCharges, disabled: disabledIdx.length, disabledIsWrong: disabledIdx.every(i => !window.__QA.st.round.options[i].correct), btnHidden: document.getElementById('btn-scan').hidden };
  });
  log('Signal Filter: 2 charges, scan greys one wrong option, button hides until next round', scanBefore.charges === 2 && !scanBefore.btnHidden && scanAfter.charges === 1 && scanAfter.disabled === 1 && scanAfter.disabledIsWrong && scanAfter.btnHidden, { scanBefore, scanAfter });
  await page.screenshot({ path: 'chain_scan.png' });

  // 9. shields/skips stack: shop_shield + shop_shield2 → 2 charges
  const r7 = await page.evaluate(() => { const Q = window.__QA; Q.save.shopOwned.push('shop_shield', 'shop_shield2', 'shop_swap', 'shop_swap2'); Q.startDungeonAttempt(0, 'zh', 'people', null); return { sh: Q.st.shieldCharges, sk: Q.st.skipCharges, skipLabel: document.getElementById('btn-skip-ticket').textContent }; });
  log('shield/skip charges stack from shop', r7.sh === 2 && r7.sk === 2 && /×2/.test(r7.skipLabel), r7);

  // 10. HUD chain + home stats
  await page.evaluate(() => { window.__QA.save.chain.len = 4; window.__QA.showHome(); });
  await page.waitForTimeout(100);
  const home = await page.evaluate(() => ({ hud: document.getElementById('hud-chain').textContent, stats: document.getElementById('home-stats').textContent }));
  log('HUD + home stats show chain', home.hud === '4' && /Signal chain/.test(home.stats), home);

  await browser.close();
  console.log('DONE');
})();
