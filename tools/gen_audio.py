#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate native-speaker recordings for Polyglot Voyager with Kokoro-82M (Apache-2.0).

  python3 tools/gen_audio.py A1            # one band
  python3 tools/gen_audio.py A1 A2 B1 B2 C1 C2   # everything (~1 h per band on CPU)
  python3 tools/gen_audio.py B1 --langs es,ja --bitrate 16k --out audio

What gets recorded for a band:
  * every vocabulary word/phrase in all six languages      -> audio/<TIER>/<id>_<lang>.ogg
  * every sentence-building line (spoken as a full sentence)
  * every dialogue prompt line (the line the other person says)
Keys are `<id>:<lang>`; the game plays a clip whenever a key exists in audio/manifest.json.

Requires: index.html already built (python3 build.py), ffmpeg on PATH, and
  pip install kokoro soundfile jieba unidic-lite cn2an pypinyin fugashi jaconv mojimoji pyopenjtalk

Backends (--backend auto|torch|onnx, default auto = torch if `kokoro` is importable, else onnx):
  torch  the reference pipeline (kokoro + torch); weights come from huggingface.co/hexgrad/Kokoro-82M
  onnx   the same Kokoro-82M weights exported to ONNX, same voices, same misaki G2P — for machines
         without torch or without access to Hugging Face. Needs `pip install misaki[ja,zh] kokoro-onnx`
         plus the two files from github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
         (kokoro-v1.0.onnx, voices-v1.0.bin) — pass them with --onnx-model/--onnx-voices or put
         them in models/.
"""
import sys, os, re, json, subprocess, time, warnings, argparse
warnings.filterwarnings('ignore')

ap = argparse.ArgumentParser()
ap.add_argument('tiers', nargs='+')
ap.add_argument('--langs', default='es,fr,it,pt,ja,zh')
ap.add_argument('--bitrate', default='16k')
ap.add_argument('--out', default='audio')
ap.add_argument('--html', default='index.html')
ap.add_argument('--speed', type=float, default=0.95)
ap.add_argument('--backend', choices=['auto', 'torch', 'onnx'], default='auto')
ap.add_argument('--onnx-model', default=os.environ.get('KOKORO_ONNX_MODEL', 'models/kokoro-v1.0.onnx'))
ap.add_argument('--onnx-voices', default=os.environ.get('KOKORO_ONNX_VOICES', 'models/voices-v1.0.bin'))
args = ap.parse_args()

import numpy as np, soundfile as sf

backend = args.backend
if backend == 'auto':
    try:
        import kokoro  # noqa: F401
        backend = 'torch'
    except ImportError:
        backend = 'onnx'
if backend == 'torch':
    from kokoro import KPipeline
else:
    from kokoro_onnx import Kokoro
    from misaki import espeak
print('backend:', backend, flush=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(ROOT, args.html), encoding='utf-8').read()
def block(name):
    m = re.search(r'var '+name+r'\s*=\s*(\[.*?\n\s*\]);', html, re.S)
    return json.loads(m.group(1)) if m else []
rows = block('VOCAB_RAW')
sentences = block('BUILD_SENTENCES')
dialogues = block('DIALOGUES')
nuance = block('NUANCE')
COL = {'es':5,'fr':6,'it':7,'pt':8,'ja':9,'zh':10}
KOKO = {'es':('e','ef_dora'), 'fr':('f','ff_siwis'), 'it':('i','if_sara'), 'pt':('p','pf_dora'), 'ja':('j','jf_alpha'), 'zh':('z','zf_xiaobei')}
ESPEAK_LANG = {'e':'es', 'f':'fr-fr', 'i':'it', 'p':'pt-br'}   # what kokoro.KPipeline uses per lang_code


class OnnxPipeline:
    """Drop-in for kokoro.KPipeline: identical misaki G2P per language, Kokoro-82M via onnxruntime."""
    _model = None

    def __init__(self, lang_code):
        self.lang_code = lang_code
        if OnnxPipeline._model is None:
            for f in (args.onnx_model, args.onnx_voices):
                if not os.path.exists(f):
                    sys.exit('onnx backend: missing %s (see the docstring for where to download it)' % f)
            OnnxPipeline._model = Kokoro(args.onnx_model, args.onnx_voices)
        if lang_code == 'j':
            from misaki import ja
            self.g2p = ja.JAG2P()
        elif lang_code == 'z':
            from misaki import zh
            self.g2p = zh.ZHG2P(version=None)
        else:
            self.g2p = espeak.EspeakG2P(language=ESPEAK_LANG[lang_code])

    def __call__(self, text, voice, speed=1.0):
        ps = self.phonemes(text)
        if len(ps) > 510:
            print('WARN phonemes truncated', len(ps), text[:40], flush=True)
        ps = ps[:510]
        samples, _sr = OnnxPipeline._model.create(ps, voice=voice, speed=speed, is_phonemes=True)
        yield text, ps, np.asarray(samples, dtype=np.float32)

    def phonemes(self, text):
        """Japanese honours the furigana the content authors wrote. The kanji form gives the G2P the
        best segmentation and long vowels, but it guesses readings (明日 -> asu, 辛い -> tsurai). When
        the kana form disagrees on the sounds, the kana phonemes win and the kanji form's word breaks
        are projected onto them, because kana-only input splits words in odd places."""
        if self.lang_code != 'j' or '{' not in text:
            return self.g2p(clean(text))[0]
        pk, _ = self.g2p(clean(text))
        ph, _ = self.g2p(clean(text, reading=True))
        k = pk.replace(' ', ''); h = ph.replace(' ', '')
        if k == h:
            return pk
        import difflib
        breaks = set(); pos = 0
        for c in pk:
            if c == ' ': breaks.add(pos)
            else: pos += 1
        kept = set()
        for a, b, n in difflib.SequenceMatcher(None, k, h, autojunk=False).get_matching_blocks():
            for j in range(n):
                if (a + j) in breaks: kept.add(b + j)
        out = []
        for i, c in enumerate(h):
            if i in kept and i: out.append(' ')
            out.append(c)
        return ''.join(out)

def clean(text, reading=False):
    if reading: t = re.sub(r'\{[^|{}]+\|([^}]+)\}', r'\1', text)   # {漢字|かな} -> かな
    else:       t = re.sub(r'\{([^|{}]+)\|[^}]+\}', r'\1', text)   # {漢字|かな} -> 漢字
    t = re.sub(r'\s*[（(][^)）]*[)）]\s*', ' ', t)                 # drop (glosses)
    t = t.replace('〜', '').replace('~', '').replace('_', '').strip()
    return re.sub(r'\s+', ' ', t)

def fnv1a(text):
    """Stable id for a spoken string; index.html computes the same hash (tileClipKey) over code points."""
    h = 0x811c9dc5
    for ch in text:
        h = ((h ^ ord(ch)) * 0x01000193) & 0xffffffff
    return format(h, '08x')

def tile_items(lang):
    """The TILES band: every sentence-building tile and every nuance option, so nothing the game speaks
    falls back to the device's own voice. Keys are x-<hash>:<lang>; the game derives the same hash."""
    seen = {}
    for s in sentences:
        if isinstance(s.get(lang), list):
            for t in s[lang]:
                seen.setdefault('x-' + fnv1a(t), t)
    for n in nuance:
        if n.get('lang') == lang:
            for o in n.get('options', []):
                seen.setdefault('x-' + fnv1a(o), o)
    return sorted(seen.items())

def items_for(tier, lang):
    if tier == 'TILES':
        # a tile that is only a parenthetical gloss, e.g. "(officieux)", is still spoken when tapped
        return [(i, t if clean(t) else t.strip('()（） ')) for i, t in tile_items(lang) if clean(t) or t.strip('()（） ')]
    out = []
    for r in rows:
        if r[4] == tier: out.append((r[0], r[COL[lang]]))
    for s in sentences:
        if s.get('tier') == tier and isinstance(s.get(lang), list):
            joiner = '' if lang in ('ja','zh') else ' '
            out.append((s['id'], joiner.join(s[lang])))
    for d in dialogues:
        if d.get('tier') == tier and isinstance(d.get(lang), list) and d[lang]:
            out.append((d['id'], d[lang][0]))
    return [(i, t) for i, t in out if clean(t)]

out_root = os.path.join(ROOT, args.out)
os.makedirs(out_root, exist_ok=True)
man_path = os.path.join(out_root, 'manifest.json')
manifest = json.load(open(man_path)) if os.path.exists(man_path) else {'keys': [], 'dir': {}, 'tiers': [], 'bitrate': args.bitrate}
keys = set(manifest['keys'])

for tier in args.tiers:
    tdir = os.path.join(out_root, tier); os.makedirs(tdir, exist_ok=True)
    for lang in args.langs.split(','):
        code, voice = KOKO[lang]
        pipe = KPipeline(lang_code=code, repo_id='hexgrad/Kokoro-82M') if backend == 'torch' else OnnxPipeline(code)
        todo = [(i, t) for i, t in items_for(tier, lang) if (i+':'+lang) not in keys]
        print(f'{tier} {lang}: {len(todo)} clips to record', flush=True)
        t0 = time.time()
        for n, (iid, text) in enumerate(todo):
            key = iid+':'+lang
            wav = os.path.join(tdir, f'{iid}_{lang}.wav'); ogg = wav[:-4]+'.ogg'
            try:
                spoken = text if backend == 'onnx' else clean(text)
                audio = np.concatenate([a for _, _, a in pipe(spoken, voice=voice, speed=args.speed)])
                idx = np.where(np.abs(audio) > 0.01)[0]
                if len(idx): audio = audio[max(0, idx[0]-1200): min(len(audio), idx[-1]+2400)]
                sf.write(wav, audio, 24000)
                subprocess.run(['ffmpeg','-y','-loglevel','error','-i',wav,'-ac','1','-ar','24000','-c:a','libopus','-b:a',args.bitrate,'-vbr','on','-application','voip','-frame_duration','40',ogg], check=True)
                os.remove(wav)
                keys.add(key); manifest['dir'][key] = tier
            except Exception as e:
                print('FAIL', key, clean(text)[:40], repr(e)[:100], flush=True)
            if n % 50 == 49:
                manifest['keys'] = sorted(keys); json.dump(manifest, open(man_path, 'w'))
                print(f'  {tier} {lang} {n+1}/{len(todo)} · {round(time.time()-t0)}s', flush=True)
        manifest['keys'] = sorted(keys)
        if tier not in manifest['tiers']: manifest['tiers'].append(tier)
        json.dump(manifest, open(man_path, 'w'))
        print(f'{tier} {lang} done in {round(time.time()-t0)}s', flush=True)
print('DONE —', len(keys), 'clips in manifest')
