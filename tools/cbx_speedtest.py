# -*- coding: utf-8 -*-
"""Times Chatterbox variants on the GPU: baseline, cfg_weight=0, fp16 T3. Writes wavs to bench_cbx/ for listening."""
import sys, time, os
import numpy as np, soundfile as sf, torch, perth
if getattr(perth, 'PerthImplicitWatermarker', None) is None: perth.PerthImplicitWatermarker = perth.DummyWatermarker
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
m = ChatterboxMultilingualTTS.from_local('models/chatterbox', 'cuda', t3_model='v3')
tests = [('de', 'Guten Morgen'), ('de', 'Ich lerne gerade Auto fahren.'), ('tr', 'Teşekkür ederim'), ('nl', 'Goedemorgen, hoe gaat het?'), ('ko', '감사합니다'), ('ar', 'شكرا')]
os.makedirs('bench_cbx', exist_ok=True)
def run(label, **kw):
    torch.cuda.synchronize(); t = time.time(); dur = 0
    for i, (lang, text) in enumerate(tests):
        with torch.inference_mode():
            wav = m.generate(text, language_id=lang, exaggeration=0.4, **kw)
        a = wav.squeeze().float().cpu().numpy(); dur += len(a)/m.sr
        sf.write(f'bench_cbx/{label}_{i}_{lang}.wav', a, m.sr)
    torch.cuda.synchronize(); dt = time.time()-t
    print('%-14s %.2fs per clip (%.1fs audio total)  peak VRAM %.0f MB' % (label, dt/len(tests), dur, torch.cuda.max_memory_allocated()/1e6), flush=True)
run('warmup', cfg_weight=0.5)
run('baseline', cfg_weight=0.5)
run('cfg0', cfg_weight=0.0)
try:
    m.t3.half()
    run('fp16-t3', cfg_weight=0.5)
    run('fp16-cfg0', cfg_weight=0.0)
except Exception as e:
    print('fp16 failed:', repr(e)[:200])
