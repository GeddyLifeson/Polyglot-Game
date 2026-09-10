# Polyglot Voyager — source & build kit

A single-file, sci-fi roguelite language-learning game: a 5,005-word A1→C2 fluency ladder in
six languages (Spanish, French, Italian, Brazilian Portuguese, Japanese, Mandarin) with
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
