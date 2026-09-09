# Merges one or more staging audio folders (each produced by gen_audio.py --out <dir>) into audio/:
#   python3 tools/merge_audio.py [--tiers B1,C1] /path/to/stageA /path/to/stageB
# Copies every <TIER>/<id>_<lang>.ogg and unions keys/dir/tiers into audio/manifest.json.
# --tiers limits the merge to finished bands (a staging folder may hold a half-recorded band).
import json, os, shutil, sys
only = None
if len(sys.argv) > 2 and sys.argv[1] == '--tiers':
    only = set(sys.argv[2].split(',')); sys.argv = sys.argv[:1] + sys.argv[3:]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dst = os.path.join(ROOT, 'audio'); man_path = os.path.join(dst, 'manifest.json')
man = json.load(open(man_path)) if os.path.exists(man_path) else {'keys': [], 'dir': {}, 'tiers': [], 'bitrate': '16k'}
keys = set(man['keys']); copied = 0
for src in sys.argv[1:]:
    m = json.load(open(os.path.join(src, 'manifest.json')))
    for key in m['keys']:
        tier = m.get('dir', {}).get(key) or key.split('-')[0].upper()
        if only and tier not in only: continue
        f = key[:key.rfind(':')] + '_' + key[key.rfind(':')+1:] + '.ogg'
        s = os.path.join(src, tier, f); d = os.path.join(dst, tier, f)
        if os.path.exists(s) and not os.path.exists(d):
            os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(s, d); copied += 1
        if os.path.exists(d):
            keys.add(key); man['dir'][key] = tier
            if tier not in man['tiers']: man['tiers'].append(tier)
man['keys'] = sorted(keys); man['tiers'] = sorted(man['tiers'])
json.dump(man, open(man_path, 'w'))
print('copied', copied, 'clips; manifest now', len(keys), 'keys; tiers', man['tiers'])
