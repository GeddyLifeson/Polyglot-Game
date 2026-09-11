# -*- coding: utf-8 -*-
"""Smoke test + benchmark for the Chatterbox backend: loads the model once and times a few clips per language.
   python tools/cbx_bench.py [cuda|cpu]"""
import sys, time, os
import numpy as np, soundfile as sf
dev = sys.argv[1] if len(sys.argv) > 1 else 'cuda'
import torch
import perth
if getattr(perth, 'PerthImplicitWatermarker', None) is None: perth.PerthImplicitWatermarker = perth.DummyWatermarker   # optional watermarker not installed
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
t = time.time()
m = ChatterboxMultilingualTTS.from_local('models/chatterbox', dev, t3_model='v3'); print('model: v3 (local files)')
print('loaded on', dev, 'in %.0fs' % (time.time()-t), 'sr', m.sr, flush=True)
tests = [('de', 'Guten Morgen'), ('de', 'Ich lerne gerade Auto fahren.'), ('ru', 'Спасибо'), ('el', 'Καλημέρα'),
         ('ko', '감사합니다'), ('ar', 'شكرا'), ('hi', 'धन्यवाद'), ('es', 'Buenos días, ¿cómo estás?'), ('ja', 'あした'), ('ms', 'Terima kasih')]
os.makedirs('bench_cbx', exist_ok=True)
tot = 0
for lang, text in tests:
    t = time.time()
    with torch.inference_mode():
        wav = m.generate(text, language_id=lang, exaggeration=0.4, cfg_weight=0.5)
    dt = time.time()-t; tot += dt
    a = wav.squeeze().cpu().numpy()
    sf.write(f'bench_cbx/{lang}_{abs(hash(text))%10000}.wav', a, m.sr)
    print('%s %-32s %.2fs audio in %.2fs' % (lang, text, len(a)/m.sr, dt), flush=True)
print('avg %.2fs per clip' % (tot/len(tests)))
if dev == 'cuda': print('peak VRAM %.0f MB' % (torch.cuda.max_memory_allocated()/1e6))
