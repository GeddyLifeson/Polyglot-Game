# Merges one or more staging audio folders (each produced by gen_audio.py --out <dir>) into audio/:
#   python3 tools/merge_audio.py [--tiers B1,C1] /path/to/stageA /path/to/stageB
#   python3 tools/merge_audio.py                 # no sources: just rewrites audio/manifest.json in the compact v2 format
# Copies every <TIER>/<id>_<lang>.ogg and unions keys/dir/tiers into audio/manifest.json (tools/manifestlib.py).
# --tiers limits the merge to finished bands (a staging folder may hold a half-recorded band).
# Never overwrites an existing clip; add --replace to let staged clips replace the ones in audio/.
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifestlib as ML
only = None; replace = False
argv = sys.argv[1:]
while argv and argv[0].startswith('--'):
    if argv[0] == '--tiers': only = set(argv[1].split(',')); argv = argv[2:]
    elif argv[0] == '--replace': replace = True; argv = argv[1:]
    else: sys.exit('unknown option ' + argv[0])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dst = os.path.join(ROOT, 'audio'); man_path = os.path.join(dst, 'manifest.json')
man = ML.load(man_path); copied = 0
for src in argv:
    m = ML.load(os.path.join(src, 'manifest.json'))
    for key in sorted(m['keys']):
        tier = m['dir'].get(key) or ML.derived_tier(key[:key.rfind(':')])
        if only and tier not in only: continue
        f = key[:key.rfind(':')] + '_' + key[key.rfind(':')+1:] + '.ogg'
        s = os.path.join(src, tier, f); d = os.path.join(dst, tier, f)
        if os.path.exists(s) and (replace or not os.path.exists(d)):
            os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(s, d); copied += 1
        if os.path.exists(d):
            man['keys'].add(key); man['dir'][key] = tier
n = ML.save(man_path, man)
print('copied', copied, 'clips; manifest now', n, 'keys; tiers', ML.load(man_path)['tiers'], '|', os.path.getsize(man_path)//1024, 'KB')
