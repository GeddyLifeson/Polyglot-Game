# Polyglot Voyager — source & build kit

A single-file, sci-fi roguelite language-learning game: a 5,005-word A1→C2 fluency ladder in
twenty languages (Spanish, French, Italian, Brazilian Portuguese, Japanese, Mandarin, German, Dutch,
Swedish, Polish, Russian, Greek, Latin, Turkish, Arabic, Hindi, Korean, Cantonese, Vietnamese,
Indonesian) with
vocabulary, dialogue, sentence-building, grammar, idiom, nuance and listening modules,
a Signal Chain meta-progression, an Engineering Bay, anomaly events, daily Signal Storms,
officer ranks, commendations, and native-speaker recordings generated with Kokoro-82M.

Everything the game needs at runtime is `index.html` plus (optionally) the `audio/` folder.

```
index.html            the built game (content already spliced in; audio NOT embedded)
content/              the vocabulary & skill content, one Python module per batch
build.py              validates content/ and splices it into index.html
audio/                native-speaker recordings (Ogg Opus) + manifest.json  ← all six bands, 30,510 clips
tools/gen_audio.py    records any band with Kokoro-82M            (→ audio/<TIER>/…)
tools/embed_audio.py  optional: bakes audio/ into index.html for a single-file build
tools/mkqa.py         builds qa/hub-qa-wrapped.html with a window.__QA debug hook
qa/*.js               Playwright test suites (content, chain, overhaul, voices, clips)
```

## 1. Run it locally (2 minutes)

`index.html` is a complete standalone page. Serve it over HTTP (not as a `file://`) so it can find
`audio/manifest.json` — opened from disk it still runs, but with device voices only.

```bash
python3 -m http.server 8000
# open http://localhost:8000/
```

That's a fully working game with a recording for every word, sentence and dialogue line in all six
bands and six languages (30,510 clips, ~125 MB). Anything without a clip falls back to the best native
voice installed on the device (🎙️ Voices panel in the HUD).

## 2. Re-record or extend the recordings

All bands ship recorded. Use this when you add content, change a translation, or want different voices
(the hosted single-file build embeds only A1 because of its 16 MB page cap; locally there is no cap).

```bash
# system deps: ffmpeg on PATH, Python 3.10+
pip install -r requirements.txt            # kokoro (Apache-2.0) + CPU torch + ja/zh phonemizers
python3 tools/gen_audio.py B1               # ~1 h per band on a laptop CPU, resumable
python3 tools/gen_audio.py B2 C1 C2
```

`gen_audio.py` records, for each band and language: every vocabulary entry, every
sentence-building line (as a whole sentence) and every dialogue prompt line, at 16 kbps Opus
(~2 KB per word). It appends to `audio/manifest.json`; the game picks new clips up on reload.
Re-running skips anything already recorded. Options: `--langs es,ja`, `--bitrate 24k`,
`--speed 0.9`, `--out audio`.

To also record the A1/A2 sentences and dialogue lines (only their vocabulary shipped):
`python3 tools/gen_audio.py A1 A2` — it only records what's missing.

The `TILES` band (`python3 tools/gen_audio.py TILES`) records every sentence-building tile and every
nuance option, keyed by a hash of the tile text (`x-<hash>:<lang>`, matched by `tileClipKey` in the
game), so tapping a tile or hearing the answer to a nuance round never falls back to the device voice.

Japanese honours the furigana in the content: when the kanji reading the G2P guesses differs from the
`{漢字|かな}` reading (明日 → あした, 辛い → からい), the kana reading wins. Only the ONNX backend does
this; the torch backend records the kanji form as-is.

**No torch, or no access to Hugging Face?** Use the ONNX backend: the same Kokoro-82M weights
exported to ONNX, the same voices and the same misaki G2P, so clips come out identical to the shipped
A1/A2 ones. Install `pip install -r requirements-onnx.txt`, download `kokoro-v1.0.onnx` and
`voices-v1.0.bin` from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 into
`models/` (git-ignored), then `python3 tools/gen_audio.py B1 B2 C1 C2 --backend onnx`. Without
`--backend` the script picks torch when the `kokoro` package is importable and ONNX otherwise.
The Playwright ffmpeg lacks an Opus encoder; `pip install imageio-ffmpeg` ships a static build that has one.

**GPU.** On an NVIDIA card use `requirements-onnx-gpu.txt` instead (onnxruntime-gpu plus the CUDA 13
wheels; make sure the plain `onnxruntime` package is not also installed, it shadows the GPU build).
`gen_audio.py` then picks the CUDA provider by default, DirectML if that is what is installed, and the
CPU otherwise, and prints which one it used. Set `ONNX_PROVIDER=CPUExecutionProvider` to force the CPU.

Voices used (Kokoro-82M): es `ef_dora`, fr `ff_siwis`, it `if_sara`, pt-BR `pf_dora`,
ja `jf_alpha`, zh `zf_xiaobei`. Swap them in the `KOKO` table in `tools/gen_audio.py`
(e.g. `em_alex`, `im_nicola`, `pm_alex`, `jm_kumo`, `zm_yunxi` for male voices).

## 3. Host it

Any static host works — the whole thing is `index.html` + `audio/`. All six bands recorded
are about 125 MB of Opus files. GitHub Pages, Netlify, Cloudflare Pages, S3, or a
`python3 -m http.server` on a LAN all work. If `audio/` lives somewhere else, set
`window.AUDIO_BASE = 'https://cdn.example.com/voyager-audio/'` in a `<script>` before the game's.

Single-file build (no `audio/` folder) — only sensible for one or two bands because of size:
`CLIPDIR=audio python3 tools/embed_audio.py A1 A2`.

## 3b. Progression systems (for tuning)

All numbers live near the top of the script in `index.html`, next to `SHOP_UPGRADES`.

- **Interference / Noise Level** (`INTERFERENCE`): nine self-imposed handicaps the player toggles on the
  home screen, each with a weight; the total is the Noise Level. Every point pays +12% credits and +8% XP.
  Applies to relays, storms and Open Channel, never to recovery drills. Replaces the old Ascension dial
  (an old Ascension save carries over as Time Compression).
- **Dark Matter** (`darkMatterFor`): the late currency. C1 relays pay 2, C2 pay 3, any relay at Noise 3+ pays
  floor(noise/2); first clears double it, a perfect run adds 1. First storm clear of the day pays 2 + noise/2.
  Deep Space floors past the first pay 1 each.
- **Engineering Bay prices** (`shopPrice`): +1.5% per upgrade already fitted, times a repertoire multiplier of
  1 + 0.3 per extra language on the voyage (`repertoireMult`, also applied to Reactor Tuning). The 68-item bay
  costs about 60k credits for a one-language voyage and about 165k for six, against roughly 60k and 400k of
  lifetime income, so there is always something left to buy going into C2.
- **Deep Space Refit** (`REFIT_TUNING`, `REFIT_MODULES`): the Dark Matter wing of the bay. Opens at Lieutenant
  or on the first C1/C2 clear with any interference on. Reactor Tuning tracks have no cap and cost 25% more
  per level; Resonance modules each need a Clearance (a deed: a 20-streak, a chain of 15, a Single Cell clear…).
- **Deep Space Run**: Open Channel gains a floor every 10 decodes; each floor adds one interference source
  from `DEEP_SPACE_ORDER`.
- **Warp Jump** (prestige, `warpCoresFor`): resets the voyage (relays, credits, bay, chain, rank, Dark Matter,
  Refit) and banks Warp Cores that never reset: +3% credits, +3% data, +2% XP each. Cores = floor(sqrt(lifetime
  XP / 100)) + floor(lifetime Dark Matter / 25), minus cores already held. Learned words, commendations,
  lifetime stats, interference choices and settings survive a jump. **Wipe all progress** on the home screen
  deletes the save entirely after two confirmations.

## 3c. Languages and the Journey

The first six languages are authored inline in `content/vocab_*.py` and have studio recordings. The other
fourteen live in `content/xlate_<lang>_<band>.py` files (`WORDS` keyed by item id, plus `SENTENCES` and
`DIALOGUES` in the `_skills` file) and are merged by `build.py`, which emits `LANG_META` with each language's
name, flag, speech locale, whether it shows a reading line, and which tiers its translations cover
completely. A language is offered for a tier only when every word of that tier is translated. Grammar,
idiom and nuance modules are authored per language and exist for the six recorded languages only.

On first launch the **Journey** screen asks which languages to take; it can be changed any time from the
Star Chart. Sectors hold one relay per chosen language, storms and the Deep Space Run mix the chosen
languages, and the Lexicon, Voices panel and Mission Log follow the choice. Indonesian uses the code `ind`
(`id` would collide with the item id field).

Recordings for the fourteen new languages are not shipped yet; they use the device voice until recorded.
`tools/gen_audio.py --backend azure` records any language with Azure Neural voices (set `AZURE_TTS_KEY`
and `AZURE_TTS_REGION`; about 63k characters per language, 1.14M for all twenty), and `--only` re-records
just the keys listed by the in-game 🚩 flag button (Mission Log). Kokoro covers es, fr, it, pt, ja, zh, hi.

`--backend chatterbox` records with Chatterbox Multilingual V3 (Resemble AI, MIT; 23 languages, covering all of
ours except Cantonese and Vietnamese; Latin reads through the Italian model, Indonesian through Malay). Set up
with `pip install -r requirements-chatterbox.txt` in a Python 3.11 env with CUDA torch 2.6, download the six model
files listed in `tools/cbx_bench.py` into `models/chatterbox/`, and run `python tools/cbx_bench.py cuda` to check.
About 8 s per clip on a 16-core CPU, well under 1 s on a GPU. On this machine Python cannot reach HTTPS hosts
until the local TLS root is appended to certifi (`tools/export_local_roots.ps1`).

## 3d. Learning systems (September 2026)

- **Spaced repetition** (`save.srs`, `srsUpdate`): every correctly or incorrectly decoded (word, language) gets a
  card; intervals 1 day, 3 days, then interval × ease (2.5 → 3.0), a miss resets to tomorrow. Due words show
  as a home card and a chain-neutral **Maintenance Sweep** tile on the topics screen (`__sweep`).
- **Graduated recall**: a missed word is re-queued 4 rounds later, then 9 later on a second miss.
- **Fill the Gap** (`cloze` module per band): one tile of a sentence blanked, options from other sentences of
  the band; the prompt is silent until answered, then the full sentence plays.
- **📘 Note** shows a sentence's grammar note before answering; **🎤 Shadow** records four seconds and plays
  the native clip and your take back to back.
- **Streak** (`save.streak`): a cleared relay, storm or sweep a day; pays min(days, 30) × 2 credits scaled by
  Noise; a 4-Dark-Matter shield covers one missed day, max two.
- **Flight Plan** (`buildPlan`, `checkPlan`): six weekly objectives generated from the voyage's languages
  (seeded by ISO week and language set), progress measured from lifetime stats since the plan began,
  rewards on completion, three milestones ending in a warp core.
- **Placement test** (`showPlacement`): twelve adaptive questions per language; may pre-clear the tiers
  below the level reached, for that language only.
- **Signal Intercept** (`interceptAnalyze`): paste any text; ladder words light up, decoded ones green;
  the unknown ones become a chain-neutral relay (`__intercept`). CJK text is scanned by longest match.
- **Constellations** (`wordRelation`, `constellationsFor`): same / similar / shared-character words across
  the voyage's languages only (English loanwords included), shown on decode and in the Lexicon.
- **Tutorial** (`COACH`, `coach`): one coach card per screen the first time a new voyage reaches it, from the
  Journey through the first relay result; skippable; never shown to a save with cleared relays.
- **Ship's Library** (`STORIES`, `showStories`): each language's own traditional tales (six per language,
  two B1, two B2, one C1, one C2, in `content/folk_<lang>.py`: myths, legends, fables and folk humour retold
  natively with the English beside, shown only for that language) plus six shared crew stories authored in
  English in `content/stories_src.py` and translated into every language in `content/xlate_<lang>_stories.py`. A story opens once its sector is reachable for that language; it is
  read one paragraph at a time (tap for the English, 🔊 to hear it, decoded ladder words glow) with four
  comprehension questions in English between paragraphs. First finish pays credits by tier (40/60/80/100)
  plus Dark Matter for C1/C2 and a perfect score; a later perfect read pays 20 credits once.
- **Skill drills for every language**: the fourteen added languages have their own B2 grammar, C1 idiom and
  C2 nuance items in `content/xlate_<lang>_skills2.py` (same schema and topic keys as the core six), so the
  grammar / idiom / nuance modules now appear in those sectors for every language on the voyage.

## 4. Edit content

Content lives in `content/*.py`. Each module exports `TIER`, `TOPICS` (key → label) and
`WORDS` rows `(en, emoji, topic, es, fr, it, pt, ja, zh, pinyin[, fact])`; skill modules add
`SENTENCES`, `GRAMMAR`, `IDIOMS`, `NUANCE`, `DIALOGUES`, `LISTEN` lists (see
`content/skills_c2.py` for every shape). Conventions: furigana as `{漢字|かな}`, pinyin with
tone marks, Brazilian Portuguese, no duplicate English headwords anywhere in the ladder.

```bash
python3 build.py        # validates everything and rewrites the generated block in index.html
```

The validator rejects: duplicate ids, duplicate English within a tier, listening modules
with < 4 source items, per-language pools missing a language, malformed dialogues.

## 5. Test

```bash
npm install                                  # playwright
npx playwright install chromium              # or set CHROMIUM_PATH to an existing binary
npm run qa                                   # builds qa/hub-qa-wrapped.html and runs all six suites
```

`npm run qa` (or `make qa`) runs qa_modules, qa_chain, qa_overhaul, qa_voice and qa_c2 from disk, then
`qa/with_server.js` serves the repo on a free port and runs qa_clips against it (the clips suite needs HTTP
for the audio manifest). Run one suite alone with `node qa/qa_modules.js`, or the clips suite with
`npm run qa:clips`. Either audio build passes: external `audio/` + manifest, or embedded via `embed_audio.py`.

## Architecture notes (for the next engineer, human or otherwise)

* **Tiers** (`TIERS`): A1 Survival → A2 Small talk → B1 Conversation → B2 Grammar → C1 Media →
  C2 Native speed → ∞ Open Channel. Each tier = a vocabulary frequency band + a skill layer.
* **Modules**: every content item has `tier` + `topic`; `modulesForTier(tier)` lists
  `[{key,type}]` in `TYPE_ORDER` (match, dialogue, build, blank, idiom, nuance, listen).
  `dungeonItemIds(tier, lang, topic)` is the exact item list of one relay run.
  Pseudo-topics: `__recovery` (missed-word drill), `__storm` (daily storm).
* **Runs**: `enterDungeon → showDungeonIntro → showLoadoutDraft → startDungeonAttempt →
  beginDungeonPlay → nextRound/makeRound → resolveRound → advanceRound → onDungeonCleared/Failed`.
  Perk effects live in `st.perkFlags` (see `freshPerkFlags`); temporary event effects in `st.temp`.
* **Meta**: `save` (localStorage `polyglotBistro.v2`) holds credits, shop, Signal Chain
  (`settleChain`), XP/ranks (`RANKS`, `addXp`), commendations, missed words, storm bests, stats.
* **Audio**: `speakText(text, lang, force, clipKey)` → `playClip(clipKey)` if a recording exists
  (embedded `AUDIO_CLIPS` or external `audio/manifest.json`), else the best native
  `speechSynthesis` voice (`voiceFor`). Round objects carry `clipKey` = `<itemId>:<lang>`.

Translations were AI-authored; the rarer C1/C2 items (proverb equivalents, literary
Mandarin) are worth a native speaker's spot-check.
