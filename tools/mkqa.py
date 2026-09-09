# Builds hub-qa-wrapped.html: the game with a window.__QA debug hook, wrapped in the same minimal
# skeleton the Artifact publisher adds.
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
    showEvent: showEvent, startStorm: startStorm, stormToday: stormToday, recoveryIds: recoveryIds, checkCommendations: checkCommendations, showLog: showLog, resolveRound: resolveRound, advanceRound: advanceRound, augmentEncrypted: augmentEncrypted, isEncryptedNow: isEncryptedNow, showLoadoutDraft: showLoadoutDraft, voiceFor: voiceFor, hasClip: hasClip, playClip: playClip, clipSrc: clipSrc, clipsInfo: function(){ return AUDIO_CLIPS_INFO; }, AUDIO_CLIPS: AUDIO_CLIPS, AUDIO_CLIPS_INFO: AUDIO_CLIPS_INFO, voicesFor: voicesFor, loadVoices: loadVoices, renderVoicesPanel: renderVoicesPanel, speakText: speakText,
    topicsForTier: topicsForTier, modulesForTier: modulesForTier, moduleFor: moduleFor, topicLabel: topicLabel,
    dungeonItemIds: dungeonItemIds, vocabForTier: vocabForTier,
    enterDungeon: enterDungeon, showHome: showHome, showHub: showHub, showTopics: showTopics,
    showDungeonIntro: showDungeonIntro, nextRound: nextRound, makeRound: makeRound, renderPhrasebook: renderPhrasebook
  };

  showHome();
})();
"""
assert "\n  showHome();\n})();\n" in content
content2 = content.replace("\n  showHome();\n})();\n", hook, 1)
wrapped = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>[hidden]{display:none!important}</style><script>window.AUDIO_BASE="../audio/";</script></head><body>
""" + content2 + """
</body></html>
"""
with open('qa/hub-qa-wrapped.html', 'w', encoding='utf-8') as f:
    f.write(wrapped)
print('qa/hub-qa-wrapped.html rebuilt')
