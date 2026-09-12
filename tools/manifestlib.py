# Shared reader/writer for audio/manifest.json.
#
# On disk (v2, compact): {"v": 2, "bitrate": "16k", "tiers": [...], "langs": [...],
#                         "ids": {"<id>": <bitmask over langs>}, "tiles": {"<lang>": ["<hash>", ...]},
#                         "dir": {"<id>": "<TIER>"}}     # only ids whose folder is not derivable from the id
# v1 (older): {"keys": ["<id>:<lang>", ...], "dir": {"<key>": "<TIER>"}, "tiers": [...], "bitrate": ...}
#
# In memory both become: {'keys': set of "<id>:<lang>", 'dir': {key: TIER}, 'tiers': [...], 'bitrate': ...}.
# index.html reads either format (see the AUDIO_EXT loader). v2 is ~25x smaller: 110k keys -> ~200 KB.
import json, os

def derived_tier(id_):
    if id_.startswith('x-'): return 'TILES'
    return id_.split('-')[0].upper()

def empty(bitrate='16k'):
    return {'keys': set(), 'dir': {}, 'tiers': [], 'bitrate': bitrate}

def load(path):
    if not os.path.exists(path): return empty()
    m = json.load(open(path, encoding='utf-8'))
    if m.get('v') == 2:
        langs = m['langs']; keys = set(); dir_ = {}
        iddir = m.get('dir', {})
        for id_, mask in m.get('ids', {}).items():
            tier = iddir.get(id_) or derived_tier(id_)
            for b, l in enumerate(langs):
                if mask >> b & 1:
                    k = id_ + ':' + l; keys.add(k); dir_[k] = tier
        for l, hashes in m.get('tiles', {}).items():
            for h in hashes:
                k = 'x-' + h + ':' + l; keys.add(k); dir_[k] = 'TILES'
        return {'keys': keys, 'dir': dir_, 'tiers': list(m.get('tiers', [])), 'bitrate': m.get('bitrate', '16k')}
    keys = set(m.get('keys', [])); dir_ = dict(m.get('dir', {}))
    for k in keys: dir_.setdefault(k, derived_tier(k[:k.rfind(':')]))
    return {'keys': keys, 'dir': dir_, 'tiers': list(m.get('tiers', [])), 'bitrate': m.get('bitrate', '16k')}

def save(path, man):
    keys = man['keys']; dir_ = man.get('dir', {})
    langs = sorted({k[k.rfind(':')+1:] for k in keys})
    bit = {l: i for i, l in enumerate(langs)}
    ids = {}; tiles = {}; iddir = {}
    for k in sorted(keys):
        id_, l = k[:k.rfind(':')], k[k.rfind(':')+1:]
        tier = dir_.get(k) or derived_tier(id_)
        if id_.startswith('x-') and tier == 'TILES':
            tiles.setdefault(l, []).append(id_[2:]); continue
        ids[id_] = ids.get(id_, 0) | (1 << bit[l])
        if tier != derived_tier(id_): iddir[id_] = tier
    tiers = sorted(set(man.get('tiers', [])) | {dir_.get(k) or derived_tier(k[:k.rfind(':')]) for k in keys})
    out = {'v': 2, 'bitrate': man.get('bitrate', '16k'), 'tiers': tiers, 'langs': langs, 'ids': ids, 'tiles': tiles, 'dir': iddir}
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
    os.replace(tmp, path)   # atomic: a crash mid-write never leaves a truncated manifest
    return len(keys)
