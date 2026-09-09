# Polyglot Voyager — notes for Claude Code

Read README.md first. Quick map:

- `index.html` is the whole game. Content between `/* ==== GENERATED CONTENT START/END ==== */`
  is machine-written by `build.py` from `content/` — never hand-edit inside those markers.
- Audio between `/* ==== AUDIO CLIPS START/END ==== */` is normally empty; recordings live in
  `audio/` and are found via `audio/manifest.json` (served over HTTP). `tools/embed_audio.py`
  can bake them in for a single-file build.
- After any change: `python3 build.py`, then `node --check` the extracted script
  (`python3 -c "import re;h=open('index.html',encoding='utf-8').read();open('/tmp/s.js','w').write('\n'.join(re.findall(r'<script>(.*?)</script>',h,re.S)))" && node --check /tmp/s.js`),
  then `python3 tools/mkqa.py` and run the `qa/*.js` suites.
- Generating audio: `python3 tools/gen_audio.py B1 B2 C1 C2` (needs ffmpeg + `pip install -r requirements.txt`).
  It is resumable and only records missing keys.
- Keep translations consistent with existing conventions: furigana `{漢字|かな}`, tone-marked pinyin,
  Brazilian Portuguese, unique English headwords across the whole ladder.
