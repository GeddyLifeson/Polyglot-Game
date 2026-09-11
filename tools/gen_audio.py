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
ap.add_argument('--backend', choices=['auto', 'torch', 'onnx', 'azure', 'chatterbox'], default='auto')
ap.add_argument('--cbx-prompt', default=os.environ.get('CBX_PROMPT', ''), help='chatterbox: reference wav for the narrator voice (optional)')
ap.add_argument('--cbx-device', default=os.environ.get('CBX_DEVICE', 'cuda'))
ap.add_argument('--azure-key', default=os.environ.get('AZURE_TTS_KEY', ''))
ap.add_argument('--azure-region', default=os.environ.get('AZURE_TTS_REGION', 'eastus'))
ap.add_argument('--voice', default='', help='override the voice name for every language in --langs')
ap.add_argument('--only', default='', help='comma-separated keys (id:lang) or a file of keys: re-record just these')
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
if backend == 'chatterbox':
    import torch
elif backend == 'azure':
    import urllib.request, html as _html
    if not args.azure_key:
        sys.exit('azure backend: set AZURE_TTS_KEY (and AZURE_TTS_REGION) or pass --azure-key/--azure-region')
elif backend == 'torch':
    from kokoro import KPipeline
else:
    import onnxruntime as ort
    # GPU by default: onnxruntime-gpu needs its CUDA/cuDNN DLLs loaded first (pip's nvidia-* wheels),
    # and kokoro-onnx would otherwise try TensorRT first and fall back to the CPU when it is missing.
    if hasattr(ort, 'preload_dlls'):
        try: ort.preload_dlls()
        except Exception: pass
    if not os.environ.get('ONNX_PROVIDER'):
        _avail = ort.get_available_providers()
        for _p in ('CUDAExecutionProvider', 'DmlExecutionProvider', 'CPUExecutionProvider'):
            if _p in _avail: os.environ['ONNX_PROVIDER'] = _p; break
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
KOKO = {'es':('e','ef_dora'), 'fr':('f','ff_siwis'), 'it':('i','if_sara'), 'pt':('p','pf_dora'), 'ja':('j','jf_alpha'), 'zh':('z','zf_xiaobei'),
        'hi':('h','hf_alpha')}
# Chatterbox Multilingual V3 (Resemble AI, MIT): our code -> its language id. Latin reads through the Italian
# model, Indonesian through Malay; Cantonese and Vietnamese are not covered (use --backend azure for those).
CBX = {'es':'es', 'fr':'fr', 'it':'it', 'pt':'pt', 'ja':'ja', 'zh':'zh', 'de':'de', 'nl':'nl', 'sv':'sv', 'pl':'pl', 'ru':'ru',
       'el':'el', 'la':'it', 'tr':'tr', 'ar':'ar', 'hi':'hi', 'ko':'ko', 'ind':'ms'}
# Azure Neural voices (the same voices Edge's Read Aloud uses); output is Ogg Opus straight from the service.
AZURE = {
    'es':('es-ES','es-ES-ElviraNeural'), 'fr':('fr-FR','fr-FR-DeniseNeural'), 'it':('it-IT','it-IT-ElsaNeural'), 'pt':('pt-BR','pt-BR-FranciscaNeural'),
    'ja':('ja-JP','ja-JP-NanamiNeural'), 'zh':('zh-CN','zh-CN-XiaoxiaoNeural'), 'de':('de-DE','de-DE-KatjaNeural'), 'nl':('nl-NL','nl-NL-ColetteNeural'),
    'sv':('sv-SE','sv-SE-SofieNeural'), 'pl':('pl-PL','pl-PL-ZofiaNeural'), 'ru':('ru-RU','ru-RU-SvetlanaNeural'), 'el':('el-GR','el-GR-AthinaNeural'),
    'la':('it-IT','it-IT-DiegoNeural'), 'tr':('tr-TR','tr-TR-EmelNeural'), 'ar':('ar-SA','ar-SA-ZariyahNeural'), 'hi':('hi-IN','hi-IN-SwaraNeural'),
    'ko':('ko-KR','ko-KR-SunHiNeural'), 'yue':('zh-HK','zh-HK-HiuMaanNeural'), 'vi':('vi-VN','vi-VN-HoaiMyNeural'), 'ind':('id-ID','id-ID-GadisNeural')}
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
            print('onnx provider:', OnnxPipeline._model.sess.get_providers()[0], flush=True)
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

class ChatterboxPipeline:
    """Chatterbox Multilingual V3 on the GPU. One model for every language; Japanese is fed the kana reading
    from the furigana so kanji are never misread. Yields 24 kHz float audio like the other pipelines."""
    _model = None
    def __init__(self, lang):
        self.lang = lang; self.lang_id = CBX[lang]
        if ChatterboxPipeline._model is None:
            import perth
            if getattr(perth, 'PerthImplicitWatermarker', None) is None: perth.PerthImplicitWatermarker = perth.DummyWatermarker   # optional watermarker not installed
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            t = time.time()
            # model files live in models/chatterbox (downloaded with curl: this machine's Python cannot reach
            # huggingface.co over TLS); see README for the list
            local = os.path.join(ROOT, 'models', 'chatterbox')
            if os.path.exists(os.path.join(local, 't3_mtl23ls_v3.safetensors')):
                ChatterboxPipeline._model = ChatterboxMultilingualTTS.from_local(local, args.cbx_device, t3_model='v3'); print('chatterbox: multilingual v3 (local)', flush=True)
            else:
                ChatterboxPipeline._model = ChatterboxMultilingualTTS.from_pretrained(device=args.cbx_device, t3_model='v3'); print('chatterbox: multilingual v3 (hub)', flush=True)
            print('chatterbox: model loaded on %s in %.0fs' % (args.cbx_device, time.time()-t), flush=True)
    def __call__(self, text, voice=None, speed=1.0):
        m = ChatterboxPipeline._model
        spoken = clean(text, reading=(self.lang == 'ja'))
        kw = {'language_id': self.lang_id, 'exaggeration': 0.4, 'cfg_weight': 0.5}
        if args.cbx_prompt: kw['audio_prompt_path'] = args.cbx_prompt
        with torch.inference_mode():
            wav = m.generate(spoken, **kw)
        a = wav.squeeze().detach().cpu().numpy().astype(np.float32)
        if m.sr != 24000:
            import librosa
            a = librosa.resample(a, orig_sr=m.sr, target_sr=24000)
        yield text, '', a

class AzurePipeline:
    """Azure Speech REST: text in, Ogg Opus bytes out. Japanese furigana is honoured by sending the kana reading
    inside <sub alias>, so the neural voice reads the intended pronunciation."""
    def __init__(self, lang):
        self.locale, self.voice = AZURE[lang]
        if args.voice: self.voice = args.voice
        self.url = 'https://%s.tts.speech.microsoft.com/cognitiveservices/v1' % args.azure_region
    def ssml(self, text):
        t = re.sub(r'\s*[（(][^)）]*[)）]\s*', ' ', text).replace('〜', '').replace('~', '').replace('_', '').strip()
        t = re.sub(r'\{([^|{}]+)\|([^}]+)\}', lambda m: '<sub alias="%s">%s</sub>' % (_html.escape(m.group(2)), _html.escape(m.group(1))), t)
        t = re.sub(r'\s+', ' ', t)
        rate = '%+d%%' % round((args.speed - 1) * 100)
        return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="%s">'
                '<voice name="%s"><prosody rate="%s">%s</prosody></voice></speak>') % (self.locale, self.voice, rate, t)
    def synth_ogg(self, text):
        body = self.ssml(text).encode('utf-8')
        req = urllib.request.Request(self.url, data=body, method='POST', headers={
            'Ocp-Apim-Subscription-Key': args.azure_key, 'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'ogg-24khz-16bit-mono-opus', 'User-Agent': 'polyglot-voyager'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.read()
            except Exception as e:
                if attempt == 3: raise
                time.sleep(2 * (attempt + 1))

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
        if r[4] != tier: continue
        if lang in COL: out.append((r[0], r[COL[lang]]))
        elif len(r) > 13 and isinstance(r[13], dict) and r[13].get(lang): out.append((r[0], r[13][lang][0]))
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

only = None
if args.only:
    raw = open(args.only, encoding='utf-8').read() if os.path.exists(args.only) else args.only
    only = set(k.strip() for k in re.split(r'[,\s]+', raw) if k.strip())
    keys -= only   # force these to be re-recorded

for tier in args.tiers:
    tdir = os.path.join(out_root, tier); os.makedirs(tdir, exist_ok=True)
    for lang in args.langs.split(','):
        if backend == 'azure':
            if lang not in AZURE: print('skip', lang, '(no Azure voice mapped)'); continue
            pipe = AzurePipeline(lang); voice = pipe.voice
        elif backend == 'chatterbox':
            if lang not in CBX: print('skip', lang, '(chatterbox has no model for it; use --backend azure)'); continue
            pipe = ChatterboxPipeline(lang); voice = 'chatterbox'
        else:
            if lang not in KOKO: print('skip', lang, '(no Kokoro voice; use --backend azure)'); continue
            code, voice = KOKO[lang]
            pipe = KPipeline(lang_code=code, repo_id='hexgrad/Kokoro-82M') if backend == 'torch' else OnnxPipeline(code)
        todo = [(i, t) for i, t in items_for(tier, lang) if (i+':'+lang) not in keys and (only is None or (i+':'+lang) in only)]
        print(f'{tier} {lang}: {len(todo)} clips to record', flush=True)
        t0 = time.time()
        for n, (iid, text) in enumerate(todo):
            key = iid+':'+lang
            wav = os.path.join(tdir, f'{iid}_{lang}.wav'); ogg = wav[:-4]+'.ogg'
            try:
                if backend == 'azure':
                    data = pipe.synth_ogg(text)
                    if len(data) < 200: raise RuntimeError('empty audio from Azure')
                    open(ogg, 'wb').write(data)
                    keys.add(key); manifest['dir'][key] = tier
                    if n % 50 == 49:
                        manifest['keys'] = sorted(keys); json.dump(manifest, open(man_path, 'w'))
                        print(f'  {tier} {lang} {n+1}/{len(todo)} · {round(time.time()-t0)}s', flush=True)
                    continue
                spoken = text if backend in ('onnx', 'chatterbox') else clean(text)
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
