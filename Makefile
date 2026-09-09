.PHONY: build serve qa audio audio-all embed
build:
	python3 build.py
serve:
	python3 -m http.server 8000
qa:
	python3 tools/mkqa.py && node qa/qa_modules.js && node qa/qa_chain.js && node qa/qa_overhaul.js && node qa/qa_voice.js && node qa/qa_c2.js
audio:
	python3 tools/gen_audio.py B1 B2 C1 C2
audio-all:
	python3 tools/gen_audio.py A1 A2 B1 B2 C1 C2
embed:
	CLIPDIR=audio python3 tools/embed_audio.py A1 A2
