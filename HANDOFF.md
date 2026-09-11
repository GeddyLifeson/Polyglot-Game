# Polyglot Voyager — handoff

Written 2026-09-11 so nothing is lost when a session compacts. Read this before touching anything.
README.md explains the game and the build; CLAUDE.md has the after-change checklist. This file is the
state of the work and what happens next.

## What the project is

A single-file browser game, `index.html`, plus an `audio/` folder of Opus clips. Sci-fi roguelite framing
over a 5,005-word A1→C2 vocabulary ladder in twenty languages. Repo: `GeddyLifeson/Polyglot-Game`, default
branch `main`, published by GitHub Pages from `main` at https://geddylifeson.github.io/Polyglot-Game/.
Every merge to `main` goes live in about a minute. Local clone: `C:\Users\imarl\polyglot_game`.

Owner's priorities, in their words: it has to stay a game from beginning to end (things to buy all the
way through C2), pronunciations must be as natural as possible, and the whole thing lives on GitHub.

## Where things are

| Area | Location | Notes |
|---|---|---|
| Game | `index.html` | generated content sits between the GENERATED CONTENT markers; never hand-edit inside them |
| Vocabulary, six core languages | `content/vocab_*.py`, `content/*.py` skill modules | rows `(en, emoji, topic, es, fr, it, pt, ja, zh, pinyin[, fact])` |
| Fourteen added languages | `content/xlate_<lang>_<band>.py` | `WORDS` dict id → (text, reading); `_skills` files carry `SENTENCES` and `DIALOGUES` |
| Build | `build.py` | merges everything, validates, emits `LANG_META`, splices into index.html |
| Recordings | `audio/<TIER>/<id>_<lang>.ogg`, `audio/manifest.json` | keys `<id>:<lang>`; `TILES` band holds sentence tiles and nuance options keyed `x-<fnv1a>:<lang>` |
| Recorder | `tools/gen_audio.py` | backends: `onnx` (Kokoro, GPU by default), `azure`, `chatterbox`, `torch` |
| Merge staged audio | `tools/merge_audio.py <staging dirs>` | never overwrites an existing clip |
| QA | `tools/mkqa.py` then `qa/*.js` | six Playwright suites; run against a live server with `QA_URL=http://localhost:8765` |
| Env, Kokoro CPU | `.venv312` | Python 3.12, misaki refuses 3.13, pyopenjtalk-plus instead of pyopenjtalk |
| Env, Kokoro GPU | `.venv312gpu` | onnxruntime-gpu 1.29 = CUDA 13 wheels; the plain `onnxruntime` package must not be installed alongside |
| Env, Chatterbox | `.venv311cbx` | Python 3.11, torch 2.6 cu124, chatterbox-tts from GitHub master (V3), Russian stresser from GitHub |
| Model files | `models/` (git-ignored) | Kokoro ONNX pair; `models/chatterbox/` six files; `models/local_roots.pem` |
| Node | `C:\Users\imarl\tools\node-v22.23.2-win-x64` | not on PATH by default |
| Dev server | launch config `voyager` in `C:\.claude\launch.json`, port 8765 | `python -m http.server 8765 --directory <repo>` |

## Language codes

es fr it pt ja zh (core, Kokoro-recorded) · de nl sv pl ru el la tr ar hi ko yue vi ind.
Indonesian is `ind`, never `id` (`id` collides with the item id field). Languages with a reading line:
zh (pinyin), ru, el, ar, hi, ko, yue (Jyutping). Japanese carries furigana `{漢字|かな}` in the text itself.

## Game systems added in September 2026 (all live on main)

- Relay-scoped answer options; a runtime guard so two options never show the same visible text.
- Interference (nine stackable handicaps → Noise Level; +12% credits, +8% XP per point). Replaces Ascension.
- Dark Matter (C1 = 2, C2 = 3 per clear, Noise 3+ pays noise/2, first clear ×2, perfect +1; storms and Deep Space floors pay it).
- Engineering Bay: 68 upgrades, prices ×1.015 per fitted upgrade × (1 + 0.3 per extra language on the voyage).
- Deep Space Refit: 5 uncapped Reactor Tuning tracks (×1.25 per level) and 13 Resonance modules behind Clearance deeds.
- Warp Jump (prestige): cores = floor(sqrt(lifetime XP / 100)) + floor(lifetime Dark Matter / 25); +3% credits, +3% data, +2% XP per core; Warp Drive spends cores on 12 permanent upgrades without reducing the bonus.
- Journey screen: pick languages on first launch, change any time; sectors count only chosen languages; a language appears in a tier only when its translations are complete.
- Wipe-save control, in-game 🚩 pronunciation flag (Mission Log lists flags; `gen_audio.py --only` re-records those keys).
- All constants live in one block near `SHOP_UPGRADES` in index.html; README section 3b documents them.

## Audio: the current job

Chatterbox Multilingual V3 (Resemble AI, MIT) is recording every language. It covers 18 of our 20;
Latin reads through the Italian model, Indonesian through Malay. **Cantonese and Vietnamese are not
covered** and still need `--backend azure` (needs `AZURE_TTS_KEY` and `AZURE_TTS_REGION`; ~63k characters
per language; the Azure free tier is 500k characters a month).

Recording runs as two GPU chains plus two queued chains, all resumable:

```
bash run_cbx_chain.sh A de nl sv pl el la      # chain A, GPU
bash run_cbx_chain.sh B ru tr ar               # chain B, GPU
bash run_cbx_queue.sh B C hi ko ind            # starts chain C when B logs ALL DONE
bash run_cbx_queue.sh A D es fr it pt ja zh    # starts chain D when A logs ALL DONE (the six re-recordings)
```

Each language records into `staging_cbx_<lang>/`; logs are `gen_cbx_<lang>.log` and `gen_cbx_chain_<tag>.log`
("finished <lang>" / "ALL DONE" lines). Throughput: one recorder on a clear card ≈ 30 clips/min, two ≈ 32.
A third thrashes (10 GB card). Anything else on the GPU (Ollama with a model loaded) drops it to ~6/min.

State at 2026-09-11 09:00:

| Language | Clips staged | Status |
|---|---|---|
| de | 5,250 | merged, pushed, marked recorded |
| ru | 5,249 | merged, pushed, marked recorded (with Russian stress marks) |
| nl | 3,895 | recording (chain A) |
| tr | 2,924 | recording (chain B) |
| hi | 62 | partial from an earlier CPU run; chain C resumes it |
| sv pl el la ar ko ind | 0 | queued |
| es fr it pt ja zh | 0 | chain D dropped 2026-09-11 (owner: "do whatever is best"); Kokoro recordings stay |

## What happens when a language finishes (repeat per language)

```
grep -c '^FAIL' gen_cbx_<lang>.log                         # expect 0
.venv312/python.exe tools/merge_audio.py staging_cbx_<lang>
# flip the language's last flag in build.py LANG_META from False to True (audio recorded), then:
.venv312/python.exe build.py && .venv312/python.exe tools/mkqa.py
git add audio/ build.py index.html && git commit && git push origin main     # unset GITHUB_TOKEN GH_TOKEN first
```
`git add` of thousands of files can hit antivirus locks; retry the add in a loop. For the six core
languages (chain D) the merge must *replace* Kokoro clips: delete `audio/<TIER>/*_<lang>.ogg` for that
language and its keys from the manifest before merging, or add a `--replace` flag to merge_audio.py.

## Next steps, in order

1. Keep merging languages as chains report them (above). Watch the monitor output; if the GPU rate
   collapses, check `nvidia-smi` and `ollama ps` for a model that reloaded onto the card.
2. Chain D (re-recording the six Kokoro languages) was dropped to save ~14 h. Re-queue with
   `bash run_cbx_queue.sh A D es fr it pt ja zh` only if the owner asks for it.
3. Cantonese and Vietnamese: record with `--backend azure` once the owner provides a key.
4. When every language is merged: run all six QA suites against the live server, update README language
   notes (which languages have studio voice), update the memory file, and merge.
5. Restore what was stopped for the GPU (see below), then restart the Panscriptum loops.
6. Owner's open wishes not yet started: none recorded beyond the above. Pronunciation complaints should
   now come through the 🚩 flag list; re-record flagged keys with `--only`.

## Things stopped for the GPU, and how to restore them

- **Ollama** is running CPU-only from a background shell (`CUDA_VISIBLE_DEVICES=-1 GGML_VK_VISIBLE_DEVICES=-1
  OLLAMA_KEEP_ALIVE=5m ollama serve`, log `C:\Users\imarl\ollama_cpu.log`). Hiding CUDA alone is not
  enough; it falls back to Vulkan. Restore: kill `ollama.exe`, relaunch `ollama app.exe` from
  `C:\Users\imarl\AppData\Local\Programs\Ollama`.
- **Panscriptum library kit** background loops (`overnight.py`, `read.py`, `foreman.py`, `overwatch.py`,
  `pipeline.py`, `autostart.py --watch`, `drill.py`, `health.py`, ...) were stopped because they pinned
  qwen3:8b on the card with keep-alive forever. The owner said not to touch Panscriptum until recording is
  done. Notes are in `C:\Users\imarl\panscriptum-library-kit\HANDOFF.md`. The Panscriptum maintenance
  Claude session relaunches them; it must be paused or it will keep doing so.
- A Startup-folder `Panscriptum.vbs` autostarts the loops at login.

## Machine quirks that cost time

- Norton's TLS root breaks Python HTTPS. Fix per environment: run `tools/export_local_roots.ps1`, then append
  `models/local_roots.pem` to that env's `certifi` bundle. curl.exe always works.
- A session-level `GITHUB_TOKEN` breaks every push with 403; `unset GITHUB_TOKEN GH_TOKEN` before git push.
- The QA page persists its save on unload; scripted tests must reset save fields explicitly.
- Bash-wrapped PowerShell one-liners: never use backticks (write a .ps1 and use -File), and never kill by a
  command-line pattern that your own shell also matches (it did, three times).
- Bulk subagents fan out into children by default; say "do not spawn subagents", give unique output
  paths, validate outputs by script (see `xlate_in/` inputs and the coverage check in git history).

## Verification standards used so far

Every claim in commits was checked live: Playwright suites, the QA hook (`window.__QA`), and scripted
sweeps (25,051 rounds for duplicate options; 358 relays for relay scoping; every translation file for
script and id coverage). Keep that bar.
