# Builds qa/hub-qa-wrapped.html: the game with a window.__QA debug hook exposing its internals.
# index.html is already a complete document; this only injects the hook and points AUDIO_BASE
# at ../audio/ so the page works from the qa/ folder (over HTTP, for the clips suite).
with open('index.html', encoding='utf-8') as f:
    content = f.read()

hook = """
  window.__QA = {
    TIERS: TIERS, LANGS: LANGS, CONCEPTS: CONCEPTS, BUILD_SENTENCES: BUILD_SENTENCES, GRAMMAR_ITEMS: GRAMMAR_ITEMS,
    IDIOMS: IDIOMS, NUANCE: NUANCE, DIALOGUES: DIALOGUES, LISTEN_MODULES: LISTEN_MODULES, SHOP_UPGRADES: SHOP_UPGRADES,
    ITEM: ITEM, st: st, save: save, persist: persist,
    isDungeonCleared: isDungeonCleared, isLangCleared: isLangCleared, isHubCleared: isHubCleared,
    isHubUnlocked: isHubUnlocked, frontierHubIdx: frontierHubIdx,
    CHAIN_MILESTONES: CHAIN_MILESTONES, settleChain: settleChain, activeMilestones: activeMilestones, carryCap: carryCap,
    startDungeonAttempt: startDungeonAttempt, onDungeonCleared: onDungeonCleared, onDungeonFailed: onDungeonFailed, PERKS: PERKS, onScan: onScan, showShop: showShop,
    RANKS: RANKS, EVENTS: EVENTS, COMMENDATIONS: COMMENDATIONS, STORM_MODS: STORM_MODS, rankIndex: rankIndex, addXp: addXp, draftPool: draftPool,
    showEvent: showEvent, startStorm: startStorm, stormToday: stormToday, recoveryIds: recoveryIds, checkCommendations: checkCommendations, showLog: showLog, resolveRound: resolveRound, advanceRound: advanceRound, augmentEncrypted: augmentEncrypted, isEncryptedNow: isEncryptedNow, showLoadoutDraft: showLoadoutDraft, voiceFor: voiceFor, hasClip: hasClip, playClip: playClip, clipSrc: clipSrc, tileClipKey: tileClipKey, INTERFERENCE: INTERFERENCE, REFIT_TUNING: REFIT_TUNING, REFIT_MODULES: REFIT_MODULES, noiseLevel: noiseLevel, shopPrice: shopPrice, darkMatterFor: darkMatterFor, renderShop: renderShop, refitUnlocked: refitUnlocked, deepSpaceFloorCheck: deepSpaceFloorCheck, endEndless: endEndless, applyInterference: applyInterference, tuningCost: tuningCost, warpCores: warpCores, warpCoresFor: warpCoresFor, warpClaimable: warpClaimable, doWarpJump: doWarpJump, renderWarpCard: renderWarpCard, LANG_META: LANG_META, LANG_ORDER: LANG_ORDER, journeyLangs: journeyLangs, tierLangs: tierLangs, showJourney: showJourney, modulesForLang: modulesForLang, repertoireMult: repertoireMult, WARP_DRIVE: WARP_DRIVE, driveLevel: driveLevel, warpAvailable: warpAvailable, renderWarpDrive: renderWarpDrive, srsUpdate: srsUpdate, srsDueIds: srsDueIds, sweepIds: sweepIds, dueSummary: dueSummary, clozeRound: clozeRound, isDrillTopic: isDrillTopic, renderSweepCard: renderSweepCard, streakTouch: streakTouch, streakAlive: streakAlive, currentPlan: currentPlan, checkPlan: checkPlan, questProgress: questProgress, renderPlanCard: renderPlanCard, constellationsFor: constellationsFor, wordRelation: wordRelation, interceptAnalyze: interceptAnalyze, showIntercept: showIntercept, interceptRun: interceptRun, showPlacement: showPlacement, showPlacementPicker: showPlacementPicker, placementFinish: placementFinish, coach: coach, COACH: COACH, STORIES: STORIES, STORY_MODES: STORY_MODES, storySim: storySim, nativeLang: nativeLang, applyNative: applyNative, applyL10n: applyL10n, loadL10n: loadL10n, l10n: function(){ return L10N; }, showStories: showStories, startStory: startStory, storyNext: storyNext, storyFinish: storyFinish, storyOpen: storyOpen, STORY_PAY: STORY_PAY, clipsInfo: function(){ return AUDIO_CLIPS_INFO; }, AUDIO_CLIPS: AUDIO_CLIPS, AUDIO_CLIPS_INFO: AUDIO_CLIPS_INFO, voicesFor: voicesFor, loadVoices: loadVoices, renderVoicesPanel: renderVoicesPanel, speakText: speakText,
    topicsForTier: topicsForTier, modulesForTier: modulesForTier, moduleFor: moduleFor, topicLabel: topicLabel,
    dungeonItemIds: dungeonItemIds, vocabForTier: vocabForTier,
    enterDungeon: enterDungeon, showHome: showHome, showHub: showHub, showTopics: showTopics,
    showDungeonIntro: showDungeonIntro, nextRound: nextRound, makeRound: makeRound, renderPhrasebook: renderPhrasebook
  };

  save.journey.set = true;   /* QA drives the Journey screen explicitly via showJourney() */
  save.tutorial = {done:true, seen:{}};   /* QA turns the coach on explicitly when it tests it */
  showHome();
})();
"""
assert "\n  showHome();\n})();\n" in content
assert "<head>\n" in content
content = content.replace("\n  showHome();\n})();\n", hook, 1)
content = content.replace("<head>\n", '<head>\n<script>window.AUDIO_BASE="../audio/";window.L10N_BASE="../l10n/";</script>\n', 1)
with open('qa/hub-qa-wrapped.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('qa/hub-qa-wrapped.html rebuilt')
