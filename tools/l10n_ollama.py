# -*- coding: utf-8 -*-
"""Translate one localization chunk with a local Ollama model instead of a cloud agent.

  python tools/l10n_ollama.py <lang> <chunk> [--model qwen3:8b] [--host http://127.0.0.1:11434]

Reads l10n_in/<chunk>.json, writes l10n_out/<lang>_<chunk>.json in the same shape, resumable (a partial output
file is reused; only missing strings are requested). Validate afterwards with tools/l10n_check.py <lang> <chunk>.
Quality is below the cloud agents' (especially for CJK, Arabic and Hindi); use it for bulk refreshes, then spot-check.
Run it only when the GPU is free: a loaded model drops the Chatterbox recorders from ~30 to ~6 clips a minute."""
import argparse, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {'es': 'Spanish', 'fr': 'French', 'it': 'Italian', 'pt': 'Brazilian Portuguese', 'ja': 'Japanese', 'zh': 'Simplified Chinese',
         'de': 'German', 'nl': 'Dutch', 'sv': 'Swedish', 'pl': 'Polish', 'ru': 'Russian', 'el': 'Modern Greek', 'la': 'Classical Latin',
         'tr': 'Turkish', 'ar': 'Modern Standard Arabic', 'hi': 'Hindi', 'ko': 'Korean', 'yue': 'Cantonese (traditional characters)',
         'vi': 'Vietnamese', 'ind': 'Indonesian'}

ap = argparse.ArgumentParser()
ap.add_argument('lang'); ap.add_argument('chunk')
ap.add_argument('--model', default=os.environ.get('OLLAMA_MODEL', 'qwen3:8b'))
ap.add_argument('--host', default=os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'))
ap.add_argument('--batch', type=int, default=12, help='strings per request')
args = ap.parse_args()
lang, chunk = args.lang, args.chunk
name = NAMES.get(lang, lang)

src = json.load(open(os.path.join(ROOT, 'l10n_in', chunk + '.json'), encoding='utf-8'))
out_path = os.path.join(ROOT, 'l10n_out', '%s_%s.json' % (lang, chunk))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
out = json.load(open(out_path, encoding='utf-8')) if os.path.exists(out_path) else {}

# flatten every string with a path, skipping a folk tale's own language
def walk(node, path, acc):
    if isinstance(node, dict):
        for k, v in node.items(): walk(v, path + [k], acc)
    elif isinstance(node, list):
        for i, v in enumerate(node): walk(v, path + [i], acc)
    elif isinstance(node, str):
        acc.append((path, node))
items = []
if chunk.startswith('folk'):
    for sid, v in src.items():
        if v.get('lang') == lang: continue
        walk({'title': v['title'], 'paras': v['paras']}, [sid], items)
else:
    walk(src, [], items)

def get(d, path):
    for p in path:
        if isinstance(d, dict): d = d.get(p)
        elif isinstance(d, list): d = d[p] if p < len(d) else None
        else: return None
        if d is None: return None
    return d
def put(d, path, value):
    for i, p in enumerate(path[:-1]):
        nxt = path[i + 1]
        if isinstance(d, dict):
            if p not in d: d[p] = [] if isinstance(nxt, int) else {}
            d = d[p]
        else:
            while len(d) <= p: d.append([] if isinstance(nxt, int) else {})
            d = d[p]
    if isinstance(d, dict): d[path[-1]] = value
    else:
        while len(d) <= path[-1]: d.append('')
        d[path[-1]] = value

todo = [(p, s) for p, s in items if not (isinstance(get(out, p), str) and get(out, p).strip())]
print('%s %s: %d strings, %d to translate with %s' % (lang, chunk, len(items), len(todo), args.model), flush=True)

SYSTEM = ('You translate short strings from English into %s for a language-learning game. Reply with ONLY a JSON array of the '
          'translated strings, same count and order as the input, nothing else. Keep proper names (Ana, Marco, Yuki, Sam, Rosetta), '
          'keep any non-English words that are being explained, keep <b>...</b> tags and the blank marker ___ unchanged.' % name)

def ask(strings):
    body = json.dumps({'model': args.model, 'stream': False, 'format': 'json', 'options': {'temperature': 0.2},
                       'messages': [{'role': 'system', 'content': SYSTEM},
                                    {'role': 'user', 'content': json.dumps({'strings': strings}, ensure_ascii=False) +
                                     '\nReturn {"strings": [...]} with the %d translations.' % len(strings)}]}).encode('utf-8')
    req = urllib.request.Request(args.host.rstrip('/') + '/api/chat', data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as r:
        content = json.loads(r.read())['message']['content']
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.S).strip()
    data = json.loads(content)
    arr = data['strings'] if isinstance(data, dict) else data
    if not isinstance(arr, list) or len(arr) != len(strings): raise ValueError('bad count %r' % (len(arr) if isinstance(arr, list) else type(arr)))
    return [str(x) for x in arr]

t0 = time.time(); done = 0
for i in range(0, len(todo), args.batch):
    batch = todo[i:i + args.batch]
    for attempt in range(3):
        try:
            res = ask([s for _, s in batch]); break
        except Exception as e:
            print('  retry', i, repr(e)[:80], flush=True); res = None; time.sleep(2)
    if res is None:
        res = [s for _, s in batch]   # leave English rather than lose the shape; l10n_check will flag it
    for (p, _), t in zip(batch, res): put(out, p, t)
    done += len(batch)
    if (i // args.batch) % 5 == 4 or i + args.batch >= len(todo):
        json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  %d/%d  %ds' % (done, len(todo), round(time.time() - t0)), flush=True)
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('wrote', out_path, '- now run: python tools/l10n_check.py %s %s' % (lang, chunk))
