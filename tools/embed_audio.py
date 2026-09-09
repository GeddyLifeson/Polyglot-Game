# Splices the generated Opus clips into index.html as base64 (AUDIO_CLIPS).
import os, json, base64, glob, sys
P = 'index.html'
s = open(P, encoding='utf-8').read()
CLIPDIR = os.environ.get('CLIPDIR','audio')
tiers = sys.argv[1:] or ['A1']
clips = {}; info_tiers = []
for t in tiers:
    d = os.path.join(CLIPDIR, t)
    if not os.path.isdir(d): continue
    n = 0
    for f in sorted(glob.glob(os.path.join(d,'*.ogg'))):
        key = os.path.basename(f)[:-4]
        # key file name is id_lang; id itself contains no ':' — restore the last '_' as ':'
        key = key[:key.rfind('_')] + ':' + key[key.rfind('_')+1:]
        clips[key] = base64.b64encode(open(f,'rb').read()).decode('ascii'); n += 1
    if n: info_tiers.append(t)
block = '  /* ==== AUDIO CLIPS START (embed_audio.py — studio recordings, Kokoro-82M, 16 kbps Opus) ==== */\n'
block += '  var AUDIO_CLIPS = ' + json.dumps(clips, separators=(',',':')) + ';\n'
block += '  var AUDIO_CLIPS_INFO = ' + json.dumps({'tiers':info_tiers, 'count':len(clips)}) + ';\n'
block += '  /* ==== AUDIO CLIPS END ==== */'
a = s.index('  /* ==== AUDIO CLIPS START'); b = s.index('  /* ==== AUDIO CLIPS END ==== */') + len('  /* ==== AUDIO CLIPS END ==== */')
s = s[:a] + block + s[b:]
open(P,'w',encoding='utf-8').write(s)
print('embedded', len(clips), 'clips from', info_tiers, '| html bytes:', len(s.encode('utf-8')))
