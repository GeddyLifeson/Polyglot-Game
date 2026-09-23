# -*- coding: utf-8 -*-
"""Pronunciation data: one IPA transcription for every target-language word or phrase the game shows.

  python3 tools/gen_pron.py            # all languages (resumable: keeps entries whose text is unchanged)
  python3 tools/gen_pron.py ru ja      # just these
  python3 tools/gen_pron.py --fresh    # recompute everything

Needs: pip install espeakng-loader pypinyin pycantonese   (espeakng-loader ships libespeak-ng and its data)

Writes pron/<lang>.json = {"lang": .., "ipa": {text: ipa}} keyed by the exact text the game displays
(Japanese keeps its {漢字|かな} markup). The game fetches the file for each language on the voyage and turns the
IPA into the player's own writing system at runtime (katakana for a Japanese speaker, an English respelling for
an English speaker, ...), see PRON in index.html. Run after build.py (it reads the generated block).

IPA conventions of the output (the runtime parser relies on them): words separated by one space, syllables by
'.', a stress mark (ˈ primary, ˌ secondary) replaces the '.' in front of a stressed syllable, tone letters
(˥˦˧˨˩) close a syllable. Sources per language:
  es fr it pt de nl sv pl ru el la tr hi vi ind eng   espeak-ng (espeakng-loader, via ctypes)
  ja    kana from the text and its furigana (own kana table)     zh   pinyin (data, else pypinyin)
  yue   Jyutping (data, else pycantonese)                        ko   own Hangul rules (liaison, assimilation)
  ar    the romanization in the data (word lexicon for sentences, espeak fallback)
  gr    Ròdais IPA from the dictionary (word lexicon for sentences, espeak gd fallback with sc read as sg)
"""
import ctypes, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'pron')

# ---------------------------------------------------------------- data from the built page
def load_content():
    h = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    def block(name):
        m = re.search(r'var ' + name + r' = (\[.*?\n  \]);', h, re.S)
        return json.loads(m.group(1))
    m = re.search(r'var LANG_META = (\{.*?\});\n', h)
    return json.loads(m.group(1)), block('VOCAB_RAW'), block('BUILD_SENTENCES'), block('GRAMMAR_ITEMS'), block('IDIOMS'), block('NUANCE'), block('DIALOGUES')

CORE = ['es', 'fr', 'it', 'pt', 'ja', 'zh']

def collect():
    """lang -> {text: reading-or-None}: every string shown as a target-language word/phrase/option."""
    meta, V, S, G, I, N, D = load_content()
    langs = list(meta.keys()) + ['eng']
    items = {l: {} for l in langs}
    def add(l, t, r=None):
        if not isinstance(t, str) or not t.strip(): return
        if t not in items[l] or (r and not items[l][t]): items[l][t] = r
    for r in V:
        for i, l in enumerate(CORE):
            add(l, r[5 + i], r[11] if l == 'zh' else None)
        add('eng', r[1])
        if len(r) > 13 and isinstance(r[13], dict):
            for l, (t, rd) in r[13].items(): add(l, t, rd)
    for s in S:
        for l in langs:
            key = l
            if isinstance(s.get(key), list):
                for t in s[key]: add(l, t)
        if s.get('en'):
            for t in s['en'].rstrip('.!?').split(' '): add('eng', t)
    for d in D:
        for l in langs:
            if isinstance(d.get(l), list):
                for t in d[l]: add(l, t)
    for g in G + N:
        rom = g.get('romaji') or {}
        for o in g['options']: add(g['lang'], o, rom.get(o) if isinstance(rom, dict) else None)
    for i in I:
        add(i['lang'], i['phrase'], i.get('romaji') if isinstance(i.get('romaji'), str) else None)
    return items

# ---------------------------------------------------------------- espeak-ng through ctypes
_esp = None
def espeak(text, voice):
    global _esp
    if _esp is None:
        import espeakng_loader
        lib = ctypes.cdll.LoadLibrary(espeakng_loader.get_library_path())
        lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.espeak_Initialize(2, 0, espeakng_loader.get_data_path().encode(), 0)
        lib.espeak_TextToPhonemes.restype = ctypes.c_char_p
        lib.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_int]
        lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
        _esp = [lib, None]
    lib = _esp[0]
    if _esp[1] != voice:
        if lib.espeak_SetVoiceByName(voice.encode()) != 0: raise RuntimeError('no espeak voice ' + voice)
        _esp[1] = voice
    buf = ctypes.create_string_buffer(text.encode('utf-8'))
    p = ctypes.c_char_p(ctypes.addressof(buf))
    out = []
    while p.value:
        s = lib.espeak_TextToPhonemes(ctypes.byref(p), 1, 0x02)
        if s: out.append(s.decode('utf-8'))
    ipa = ' '.join(out)
    ipa = re.sub(r'\([a-z-]+\)', '', ipa)          # language-switch markers like (en)
    return ipa

ESPEAK_VOICE = {'es': 'es', 'fr': 'fr', 'it': 'it', 'pt': 'pt-br', 'de': 'de', 'nl': 'nl', 'sv': 'sv', 'pl': 'pl',
                'ru': 'ru', 'el': 'el', 'la': 'la', 'tr': 'tr', 'hi': 'hi', 'vi': 'vi', 'ind': 'id', 'eng': 'en-us',
                'ar': 'ar', 'gr': 'gd'}

# ---------------------------------------------------------------- IPA tokenizer + syllabifier
VOWELS = set('iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒɚɝᵻä')
MODS = set('ːˑʰʲʷˠˤⁿˡʱ̚ʼ')
TONES = set('˥˦˧˨˩')
GLIDE2 = set('ɪʊiuyʏ')   # second element of a diphthong
LIQ = set('lrɾɹʁʀjwʋʎɫ')
STOPS = set('pbtdkgɡqcɟʈɖ')
FRIC = set('fvθðszʃʒçxɣχhβɸɕʑʂʐ')
AFFR = {'tʃ', 'dʒ', 'ts', 'dz', 'tɕ', 'dʑ', 'ʈʂ', 'ɖʐ', 'pf'}

def tokenize(word):
    """-> list of ('V'|'C'|'S'|'T', text): vowels, consonants, stress marks, tone letters."""
    toks = []
    i, n = 0, len(word)
    while i < n:
        ch = word[i]
        if ch in 'ˈˌ':
            toks.append(['S', ch]); i += 1; continue
        if ch in TONES or ch.isdigit():
            if ch in TONES:
                if toks and toks[-1][0] == 'T': toks[-1][1] += ch
                else: toks.append(['T', ch])
            i += 1; continue
        if ch in '.|-‿': toks.append(['B', '.']); i += 1; continue
        if unicodedata.category(ch).startswith('M') or ch in MODS:
            if toks and toks[-1][0] in 'VC':
                toks[-1][1] += ch
                if ch == '̩': toks[-1][0] = 'V'           # syllabic consonant
                if ch == '̯' and toks[-1][0] == 'V': toks[-1].append('glide')
            i += 1; continue
        if ch in '͜͡':
            if toks and i + 1 < n: toks[-1][1] += ch + word[i + 1]; i += 2
            else: i += 1
            continue
        if ch in VOWELS:
            toks.append(['V', ch]); i += 1; continue
        if ch.isalpha() or ch in 'ʔʕɡ':
            # affricates written without a tie bar
            if toks and toks[-1][0] == 'C' and (toks[-1][1] + ch) in AFFR:
                toks[-1][1] += ch
            else:
                toks.append(['C', ch])
            i += 1; continue
        i += 1   # punctuation etc.
    return toks

def base(seg):
    return seg[0]

def legal_onset(cl, initial=False):
    if len(cl) <= 1: return True
    b = [base(c) if c not in AFFR else c for c in cl]
    if len(cl) == 2:
        a, c = cl
        if base(a) == base(c): return False
        if (base(a) in STOPS or base(a) in FRIC) and base(a) not in 'hħ' and base(c) in LIQ: return True
        if base(a) in 'sʃ' and base(c) in STOPS: return initial
        return False
    if len(cl) == 3:
        return initial and base(cl[0]) in 'sʃ' and base(cl[1]) in STOPS and base(cl[2]) in LIQ
    return False

def syllabify_word(word):
    toks = tokenize(word)
    # split geminates written with length on a consonant: tː -> t.t
    t2 = []
    for t in toks:
        if t[0] == 'C' and 'ː' in t[1]:
            s = t[1].replace('ː', '')
            t2.append(['C', s]); t2.append(['C', s])
        else: t2.append(t)
    toks = t2
    # nuclei
    units = []  # ('N', [vowels], stress) | ('C', seg) | ('S', mark) | ('T', tone) | ('B',)
    for t in toks:
        if t[0] == 'V':
            prev = units[-1] if units else None
            if prev and prev[0] == 'N' and len(prev[1]) == 1 and (t[1][0] in GLIDE2 or 'glide' in t) and not prev[3]:
                prev[1].append(t[1]); continue
            units.append(['N', [t[1]], None, False])
        elif t[0] == 'S':
            units.append(['S', t[1]])
        elif t[0] == 'T':
            # tone closes the preceding syllable
            for u in reversed(units):
                if u[0] == 'N': u.append(t[1]); break
            units.append(['B'])
        elif t[0] == 'B':
            units.append(['B'])
        else:
            units.append(['C', t[1]])
    # stress: a mark applies to the next nucleus
    pending = None
    for u in units:
        if u[0] == 'S': pending = u[1]
        elif u[0] == 'N':
            u[2] = pending; pending = None
    nuc_idx = [i for i, u in enumerate(units) if u[0] == 'N']
    if not nuc_idx:
        cons = ''.join(u[1] for u in units if u[0] == 'C')
        return cons
    sylls = []
    for k, ni in enumerate(nuc_idx):
        sylls.append({'on': [], 'nu': units[ni][1], 'co': [], 'st': units[ni][2], 'tone': units[ni][4] if len(units[ni]) > 4 else ''})
    # onset of the first syllable
    first = nuc_idx[0]
    sylls[0]['on'] = [u[1] for u in units[:first] if u[0] == 'C']
    for k in range(len(nuc_idx)):
        a = nuc_idx[k]
        b = nuc_idx[k + 1] if k + 1 < len(nuc_idx) else len(units)
        mid = units[a + 1:b]
        cl = [u[1] for u in mid if u[0] == 'C']
        if k + 1 == len(nuc_idx):
            sylls[k]['co'] = cl; break
        # explicit boundary (tone / '.') inside the cluster wins
        bpos = None; ci = 0
        for u in mid:
            if u[0] == 'B': bpos = ci
            if u[0] == 'C': ci += 1
        if bpos is not None:
            split = bpos
        else:
            split = len(cl)
            while split > 0 and legal_onset(cl[split - 1:]): split -= 1
            if split == 0 and len(cl) > 0 and len(cl) >= 1: split = 0
        sylls[k]['co'] = cl[:split]; sylls[k + 1]['on'] = cl[split:]
    out = ''
    for k, s in enumerate(sylls):
        body = ''.join(s['on']) + ''.join(s['nu']) + ''.join(s['co']) + s['tone']
        if s['st']: out += s['st'] + body
        else: out += ('.' if k else '') + body
    return out

def syllabify(ipa):
    words = [w for w in re.split(r'[\s,;:!?¡¿"“”«»()\[\]/]+', ipa) if w]
    return ' '.join(x for x in (syllabify_word(w) for w in words) if x)

# ---------------------------------------------------------------- Japanese
KANA = {}
def _kana():
    rows = {
        '': 'あいうえお', 'k': 'かきくけこ', 's': 'さしすせそ', 't': 'たちつてと', 'n': 'なにぬねの', 'h': 'はひふへほ',
        'm': 'まみむめも', 'r': 'らりるれろ', 'g': 'がぎぐげご', 'z': 'ざじずぜぞ', 'd': 'だぢづでど', 'b': 'ばびぶべぼ', 'p': 'ぱぴぷぺぽ'}
    ipa = {'': ['a', 'i', 'ɯ', 'e', 'o'], 'k': ['ka', 'ki', 'kɯ', 'ke', 'ko'], 's': ['sa', 'ɕi', 'sɯ', 'se', 'so'],
           't': ['ta', 'tɕi', 'tsɯ', 'te', 'to'], 'n': ['na', 'ɲi', 'nɯ', 'ne', 'no'], 'h': ['ha', 'çi', 'ɸɯ', 'he', 'ho'],
           'm': ['ma', 'mi', 'mɯ', 'me', 'mo'], 'r': ['ɾa', 'ɾi', 'ɾɯ', 'ɾe', 'ɾo'], 'g': ['ga', 'gi', 'gɯ', 'ge', 'go'],
           'z': ['dza', 'dʑi', 'dzɯ', 'dze', 'dzo'], 'd': ['da', 'dʑi', 'dzɯ', 'de', 'do'], 'b': ['ba', 'bi', 'bɯ', 'be', 'bo'],
           'p': ['pa', 'pi', 'pɯ', 'pe', 'po']}
    for k, ks in rows.items():
        for c, v in zip(ks, ipa[k]): KANA[c] = v
    KANA.update({'や': 'ja', 'ゆ': 'jɯ', 'よ': 'jo', 'わ': 'wa', 'を': 'o', 'ゐ': 'i', 'ゑ': 'e', 'ゔ': 'vɯ',
                 'ぁ': 'a', 'ぃ': 'i', 'ぅ': 'ɯ', 'ぇ': 'e', 'ぉ': 'o'})
_kana()
SMALL_Y = {'ゃ': 'a', 'ゅ': 'ɯ', 'ょ': 'o'}
PAL = {'k': 'kj', 'g': 'gj', 'ɕ': 'ɕ', 'tɕ': 'tɕ', 'dʑ': 'dʑ', 'ɲ': 'ɲ', 'ç': 'ç', 'b': 'bj', 'p': 'pj', 'm': 'mj', 'ɾ': 'ɾj'}

def kata2hira(s):
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in s)

def ja_ipa(text):
    t = re.sub(r'\{([^|}]*)\|([^}]*)\}(は(?=$|[、。！？!?\s」）)]))?', lambda m: m.group(2) + ('ワ' if m.group(3) else ''), text)
    t = t.replace('ワ', '\x01')
    t = re.sub(r'[（(][^）)]*[）)]', '', t)
    t = kata2hira(t).replace('\x01', 'わ')
    # topic particle は / direction へ at the end of a phrase
    t = re.sub(r'(?<=[でにとも])は(?=$|[、。！？!?\s])', 'わ', t)
    t = re.sub(r'(?<=[ちば])は$', 'わ', t)          # こんにちは, こんばんは
    words = re.split(r'[\s、。！？!?「」『』・〜~…]+', t)
    out = []
    for w in words:
        if not w: continue
        segs = []  # list of [cons, vowel]
        i = 0
        while i < len(w):
            c = w[i]
            if c == 'う' and segs and segs[-1][1] in ('o', 'ɯ') and not (i + 1 < len(w) and w[i + 1] in SMALL_Y):
                segs[-1][1] += 'ː'; i += 1; continue      # おう / こう / とう: a long o
            if c in KANA:
                v = KANA[c]
                m = re.match(r'([^aiɯeo]*)([aiɯeo])', v)
                segs.append([m.group(1), m.group(2)])
                if i + 1 < len(w) and w[i + 1] in SMALL_Y:
                    cons = segs[-1][0]
                    segs[-1] = [PAL.get(cons, cons + 'j'), SMALL_Y[w[i + 1]]]; i += 1
                elif i + 1 < len(w) and w[i + 1] in 'ぁぃぇぉ' and c in 'ふてでうしちじつヴゔ':
                    cons = segs[-1][0] or ('w' if c == 'う' else '')
                    segs[-1] = [cons, KANA[w[i + 1]]]; i += 1
            elif c == 'っ':
                segs.append(['Q', ''])
            elif c == 'ん':
                segs.append(['N', ''])
            elif c == 'ー':
                if segs and segs[-1][1]: segs[-1][1] += 'ː'
            i += 1
        # render: Q doubles the next consonant (closing the previous syllable), N assimilates
        s = ''
        for k, (c, v) in enumerate(segs):
            nxt = segs[k + 1] if k + 1 < len(segs) else None
            if c == 'Q':
                if nxt and nxt[0] and nxt[0] not in ('Q', 'N'):
                    s = s.rstrip('.') + nxt[0][0] + '.'
                continue
            if c == 'N':
                if nxt and nxt[0][:1] in ('p', 'b', 'm'): n_ = 'm'
                elif nxt and nxt[0][:1] in ('k', 'g'): n_ = 'ŋ'
                elif nxt is None: n_ = 'ɴ'
                else: n_ = 'n'
                s = s.rstrip('.') + n_ + '.'
                continue
            s += c + v + '.'
        s = s.strip('.')
        out.append(s)
    return ' '.join(out)

# ---------------------------------------------------------------- Mandarin (pinyin)
PY_INIT = [('zh', 'ʈʂ'), ('ch', 'ʈʂʰ'), ('sh', 'ʂ'), ('b', 'p'), ('p', 'pʰ'), ('m', 'm'), ('f', 'f'), ('d', 't'), ('t', 'tʰ'),
           ('n', 'n'), ('l', 'l'), ('g', 'k'), ('k', 'kʰ'), ('h', 'x'), ('j', 'tɕ'), ('q', 'tɕʰ'), ('x', 'ɕ'), ('r', 'ʐ'),
           ('z', 'ts'), ('c', 'tsʰ'), ('s', 's'), ('y', ''), ('w', '')]
PY_FIN = {'a': 'a', 'o': 'wo', 'e': 'ɤ', 'ai': 'ai', 'ei': 'ei', 'ao': 'au', 'ou': 'ou', 'an': 'an', 'en': 'ən', 'ang': 'aŋ',
          'eng': 'əŋ', 'ong': 'ʊŋ', 'er': 'aɚ', 'i': 'i', 'ia': 'ja', 'ie': 'jɛ', 'iao': 'jau', 'iu': 'jou', 'ian': 'jɛn',
          'in': 'in', 'iang': 'jaŋ', 'ing': 'iŋ', 'iong': 'jʊŋ', 'u': 'u', 'ua': 'wa', 'uo': 'wo', 'uai': 'wai', 'ui': 'wei',
          'uan': 'wan', 'un': 'wən', 'uang': 'waŋ', 'ueng': 'wəŋ', 'ü': 'y', 'üe': 'ɥɛ', 'üan': 'ɥɛn', 'ün': 'yn', 'ue': 'ɥɛ',
          'v': 'y', 've': 'ɥɛ', 'ê': 'ɛ', 'm': 'm̩', 'n': 'n̩', 'ng': 'ŋ̩', 'r': 'ɚ'}
TONEMARK = {'ā': ('a', 1), 'á': ('a', 2), 'ǎ': ('a', 3), 'à': ('a', 4), 'ē': ('e', 1), 'é': ('e', 2), 'ě': ('e', 3), 'è': ('e', 4),
            'ī': ('i', 1), 'í': ('i', 2), 'ǐ': ('i', 3), 'ì': ('i', 4), 'ō': ('o', 1), 'ó': ('o', 2), 'ǒ': ('o', 3), 'ò': ('o', 4),
            'ū': ('u', 1), 'ú': ('u', 2), 'ǔ': ('u', 3), 'ù': ('u', 4), 'ǖ': ('ü', 1), 'ǘ': ('ü', 2), 'ǚ': ('ü', 3), 'ǜ': ('ü', 4),
            'ń': ('n', 2), 'ň': ('n', 3), 'ǹ': ('n', 4), 'ḿ': ('m', 2)}
MAND_TONE = {1: '˥', 2: '˧˥', 3: '˨˩˦', 4: '˥˩', 0: ''}

def py_syllable(s, tone):
    """one toneless pinyin syllable -> IPA or None"""
    if s in ('m', 'n', 'ng', 'hm', 'hng'): return {'m': 'm̩', 'n': 'n̩', 'ng': 'ŋ̩', 'hm': 'hm̩', 'hng': 'hŋ̩'}[s] + MAND_TONE[tone]
    ini, ipa0 = '', ''
    for a, b in PY_INIT:
        if s.startswith(a):
            ini, ipa0 = a, b; break
    fin = s[len(ini):]
    if ini == 'y':
        fin = {'i': 'i', 'in': 'in', 'ing': 'ing', 'u': 'ü', 'ue': 'üe', 'uan': 'üan', 'un': 'ün', 'e': 'ie', 'ou': 'iu', 'a': 'ia',
               'ao': 'iao', 'an': 'ian', 'ang': 'iang', 'ong': 'iong', 'o': 'io'}.get(fin, 'i' + fin)
    elif ini == 'w':
        fin = {'u': 'u', 'o': 'uo', 'ei': 'ui', 'en': 'un', 'eng': 'ueng'}.get(fin, 'u' + fin)
    elif ini in ('j', 'q', 'x') and fin.startswith('u'):
        fin = 'ü' + fin[1:]
    if fin == 'io': fin = 'iao'
    if fin not in PY_FIN: return None
    f = PY_FIN[fin]
    if fin == 'i' and ini in ('z', 'c', 's'): f = 'ɹ̩'
    if fin == 'i' and ini in ('zh', 'ch', 'sh', 'r'): f = 'ɻ̩'
    if fin == 'o' and ini in ('b', 'p', 'm', 'f'): f = 'wo'
    if fin in ('ui',) and ini: f = 'wei'
    if fin in ('iu',) and ini: f = 'jou'
    if fin == 'un' and ini not in ('j', 'q', 'x', 'y'): f = 'wən'
    return ipa0 + f + MAND_TONE[tone]

_PY_VALID = None
def pinyin_ipa(py):
    """pinyin with tone marks or digits, words separated by spaces -> IPA"""
    words = []
    for w in re.split(r"[\s,.;:!?，。？！、…“”\"()（）\-–—/]+", py.lower()):
        if not w: continue
        # tone marks -> base letters + per-letter tone
        letters, tones = [], []
        for ch in unicodedata.normalize('NFC', w):
            if ch in TONEMARK:
                b, t = TONEMARK[ch]; letters.append(b); tones.append(t)
            elif ch == "'" or ch == '’':
                letters.append("'"); tones.append(0)
            elif ch.isdigit() and letters:
                tones.append(-int(ch)); letters.append('#')
            else:
                letters.append(ch); tones.append(0)
        s = ''.join(letters)
        # segment into syllables (DP on valid syllables)
        n = len(s); best = [None] * (n + 1); best[0] = []
        for i in range(n):
            if best[i] is None: continue
            if s[i] in "'#":
                if best[i + 1] is None or len(best[i + 1]) > len(best[i]): best[i + 1] = best[i]
                continue
            for j in range(min(n, i + 6), i, -1):
                seg = s[i:j]
                if py_syllable(seg, 0) is not None:
                    cand = best[i] + [(i, j)]
                    if best[j] is None or len(best[j]) > len(cand): best[j] = cand
        if best[n] is None:
            continue
        sy = []
        for (i, j) in best[n]:
            t = max([x for x in tones[i:j] if x > 0] or [0])
            if j < n and s[j] == '#': t = -tones[j]
            if t == 5: t = 0
            sy.append(py_syllable(s[i:j], t))
        words.append('.'.join(sy))
    return ' '.join(words)

def zh_ipa(text, reading):
    if reading and re.search(r'[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]', reading):
        r = pinyin_ipa(reading)
        if r: return r
    from pypinyin import lazy_pinyin, Style
    parts = []
    for chunk in re.split(r'([㐀-鿿]+)', text):
        if not chunk.strip(): continue
        if re.match(r'[㐀-鿿]', chunk):
            parts.append('.'.join(pinyin_ipa(p) for p in lazy_pinyin(chunk, style=Style.TONE3, neutral_tone_with_five=True)))
        elif re.search(r'[A-Za-z]', chunk):
            parts.append(syllabify(espeak(chunk, 'en-us')))
    return ' '.join(p for p in parts if p)

# ---------------------------------------------------------------- Cantonese (Jyutping)
JP_INIT = [('gw', 'kʷ'), ('kw', 'kʷʰ'), ('ng', 'ŋ'), ('b', 'p'), ('p', 'pʰ'), ('m', 'm'), ('f', 'f'), ('d', 't'), ('t', 'tʰ'),
           ('n', 'n'), ('l', 'l'), ('g', 'k'), ('k', 'kʰ'), ('h', 'h'), ('w', 'w'), ('z', 'ts'), ('c', 'tsʰ'), ('s', 's'), ('j', 'j')]
JP_NUC = [('aa', 'aː'), ('a', 'ɐ'), ('eo', 'ɵ'), ('oe', 'œː'), ('e', 'ɛː'), ('i', 'iː'), ('o', 'ɔː'), ('u', 'uː'), ('yu', 'yː')]
JP_TONE = {1: '˥', 2: '˧˥', 3: '˧', 4: '˨˩', 5: '˩˧', 6: '˨', 0: ''}

def jp_syllable(s):
    m = re.match(r'^([a-z]+)([1-6]?)$', s)
    if not m: return None
    s, tone = m.group(1), int(m.group(2) or 0)
    if s in ('m', 'ng', 'hm', 'hng'): return {'m': 'm̩', 'ng': 'ŋ̩', 'hm': 'hm̩', 'hng': 'hŋ̩'}[s] + JP_TONE[tone]
    ini, ipa0 = '', ''
    for a, b in JP_INIT:
        if s.startswith(a) and len(s) > len(a):
            ini, ipa0 = a, b; break
    rest = s[len(ini):]
    nuc = None
    for a, b in sorted(JP_NUC, key=lambda x: -len(x[0])):
        if rest.startswith(a): nuc, nipa = a, b; break
    if nuc is None: return None
    coda = rest[len(nuc):]
    cmap = {'': '', 'i': 'i', 'u': 'u', 'm': 'm', 'n': 'n', 'ng': 'ŋ', 'p': 'p', 't': 't', 'k': 'k', 'y': 'y'}
    if coda not in cmap: return None
    if nuc == 'e' and coda == 'i': nipa = 'e'
    if nuc == 'o' and coda == 'u': nipa = 'o'
    if nuc == 'i' and coda in ('ng', 'k'): nipa = 'ɪ'
    if nuc == 'u' and coda in ('ng', 'k'): nipa = 'ʊ'
    if nuc == 'eo' and coda == 'i': coda = 'y'
    if nuc in ('oe', 'eo') and coda == 'i': coda = 'y'
    c = cmap[coda]
    if nuc == 'u' and coda == 'i': c = 'y'
    if nuc == 'o' and coda == 'i': c = 'y'
    if coda in ('i', 'u', 'y') and nipa.endswith('ː') and nuc not in ('aa',): nipa = nipa.rstrip('ː')
    return ipa0 + nipa + c + JP_TONE[tone]

def jyutping_ipa(jp):
    words = []
    for w in re.split(r"[\s,.;:!?，。？！、…()（）/]+", jp.lower()):
        if not w: continue
        sy = [jp_syllable(x) for x in re.findall(r'[a-z]+[1-6]?', w)]
        sy = [x for x in sy if x]
        if sy: words.append('.'.join(sy))
    return ' '.join(words)

_pyc = None
def yue_ipa(text, reading):
    global _pyc
    if reading and re.search(r'[a-z]+[1-6]', reading):
        return jyutping_ipa(reading)
    if _pyc is None:
        import pycantonese; _pyc = pycantonese
    parts = []
    for chunk in re.split(r'([㐀-鿿]+)', text):
        if not chunk.strip(): continue
        if re.match(r'[㐀-鿿]', chunk):
            sy = []
            for word, jp in _pyc.characters_to_jyutping(chunk):
                if jp: sy.append(jyutping_ipa(jp).replace(' ', '.'))
            parts.append('.'.join(x for x in sy if x))
        elif re.search(r'[A-Za-z]', chunk):
            parts.append(syllabify(espeak(chunk, 'en-us')))
    return ' '.join(p for p in parts if p)

# ---------------------------------------------------------------- Korean (Hangul rules)
KO_I = ['k', 'k͈', 'n', 't', 't͈', 'ɾ', 'm', 'p', 'p͈', 's', 's͈', '', 'tɕ', 'tɕ͈', 'tɕʰ', 'kʰ', 'tʰ', 'pʰ', 'h']
KO_V = ['a', 'ɛ', 'ja', 'jɛ', 'ʌ', 'e', 'jʌ', 'je', 'o', 'wa', 'wɛ', 'we', 'jo', 'u', 'wʌ', 'we', 'wi', 'ju', 'ɯ', 'ɯi', 'i']
# finals by index: 0 none, 1 ㄱ 2 ㄲ 3 ㄳ 4 ㄴ 5 ㄵ 6 ㄶ 7 ㄷ 8 ㄹ 9 ㄺ 10 ㄻ 11 ㄼ 12 ㄽ 13 ㄾ 14 ㄿ 15 ㅀ 16 ㅁ 17 ㅂ 18 ㅄ 19 ㅅ 20 ㅆ 21 ㅇ 22 ㅈ 23 ㅊ 24 ㅋ 25 ㅌ 26 ㅍ 27 ㅎ
# each final: (coda sound, sound that moves to a following ㅇ onset, carries h)
KO_F = [('', None, 0), ('k', 'k', 0), ('k', 'k͈', 0), ('k', 's͈', 0), ('n', 'n', 0), ('n', 'tɕ', 0), ('n', 'n', 1), ('t', 't', 0),
        ('l', 'ɾ', 0), ('k', 'k', 0), ('m', 'm', 0), ('l', 'p', 0), ('l', 's', 0), ('l', 'tʰ', 0), ('p', 'pʰ', 0), ('l', 'ɾ', 1),
        ('m', 'm', 0), ('p', 'p', 0), ('p', 's͈', 0), ('t', 's', 0), ('t', 's͈', 0), ('ŋ', None, 0), ('t', 'tɕ', 0), ('t', 'tɕʰ', 0),
        ('k', 'kʰ', 0), ('t', 'tʰ', 0), ('p', 'pʰ', 0), ('', None, 1)]
ASP = {'k': 'kʰ', 't': 'tʰ', 'p': 'pʰ', 'tɕ': 'tɕʰ'}
TENSE = {'k': 'k͈', 't': 't͈', 'p': 'p͈', 's': 's͈', 'tɕ': 'tɕ͈'}

def ko_word(w):
    syl = []
    for ch in w:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            syl.append([KO_I[o // 588], KO_V[(o % 588) // 28], o % 28])
    if not syl: return ''
    res = []  # [onset, vowel, coda]
    for i, (on, v, f) in enumerate(syl):
        res.append([on, v, f])
    out = []
    for i in range(len(res)):
        on, v, f = res[i]
        coda, move, hflag = KO_F[f] if isinstance(f, int) else (f, None, 0)
        if i + 1 < len(res):
            non = res[i + 1][0]
            if non == '' and move is not None:          # liaison
                mv = move
                if f in (7, 25) and res[i + 1][1].startswith(('i', 'j')): mv = 'tɕ' if f == 7 else 'tɕʰ'   # palatalization
                if f in (3, 5, 9, 10, 11, 12, 13, 14, 18):
                    coda = {3: 'k', 5: 'n', 9: 'l', 10: 'l', 11: 'l', 12: 'l', 13: 'l', 14: 'l', 18: 'p'}[f]
                else:
                    coda = ''
                res[i + 1][0] = mv
            elif non == '' and hflag:                 # ㅎ before a vowel drops
                if f == 27: coda = ''
                elif f == 6: coda = ''; res[i + 1][0] = 'n'
                elif f == 15: coda = ''; res[i + 1][0] = 'ɾ'
            elif non == 'h' and coda in ('k', 't', 'p') and f not in (27,):
                res[i + 1][0] = ASP[coda]; coda = ''
            elif hflag and non in ASP:
                res[i + 1][0] = ASP[non]
                if f == 27: coda = ''
            elif hflag and non == 's':
                res[i + 1][0] = 's͈'
                if f == 27: coda = ''
            else:
                if coda in ('k', 't', 'p') and non in ('n', 'm'):
                    coda = {'k': 'ŋ', 't': 'n', 'p': 'm'}[coda]
                elif coda in ('k', 't', 'p') and non == 'ɾ':
                    coda = {'k': 'ŋ', 't': 'n', 'p': 'm'}[coda]; res[i + 1][0] = 'n'
                elif coda in ('m', 'ŋ') and non == 'ɾ':
                    res[i + 1][0] = 'n'
                elif coda == 'n' and non == 'ɾ':
                    coda = 'l'; res[i + 1][0] = 'l'
                elif coda == 'l' and non == 'ɾ':
                    res[i + 1][0] = 'l'
                elif coda == 'l' and non == 'n':
                    res[i + 1][0] = 'l'
                elif coda in ('k', 't', 'p') and non in TENSE:
                    res[i + 1][0] = TENSE[non]
            if f == 27 and coda: coda = ''
        else:
            if f == 27: coda = ''
        res[i][2] = coda
    for i, (on, v, coda) in enumerate(res):
        o = on
        # lenis stops voice between voiced sounds
        if i > 0 and o in ('k', 't', 'p', 'tɕ') and (res[i - 1][2] in ('', 'n', 'm', 'ŋ', 'l')):
            o = {'k': 'g', 't': 'd', 'p': 'b', 'tɕ': 'dʑ'}[o]
        if o == 's' and v.startswith(('i', 'j', 'wi')): o = 'ɕ'
        if o == 'ɾ' and i == 0: o = 'ɾ'
        if v == 'ɯi' and o: v = 'i'
        out.append(o + v + (coda if coda != 'l' else 'l'))
    return '.'.join(out)

def ko_ipa(text):
    return ' '.join(x for x in (ko_word(w) for w in re.split(r'[^가-힣]+', text)) if x)

# ---------------------------------------------------------------- Arabic (romanization -> IPA)
AR_DI = [('kh', 'x'), ('gh', 'ɣ'), ('sh', 'ʃ'), ('th', 'θ'), ('dh', 'ð'), ('aa', 'aː'), ('ii', 'iː'), ('uu', 'uː'), ('ee', 'eː'), ('oo', 'oː'),
         ('ā', 'aː'), ('ī', 'iː'), ('ū', 'uː'), ('ṭ', 't'), ("'", 'ʔ'), ('’', 'ʔ'), ('ʿ', 'ʕ'), ('`', 'ʕ'),
         ('a', 'a'), ('i', 'i'), ('u', 'u'), ('e', 'e'), ('o', 'o'), ('b', 'b'), ('t', 't'), ('j', 'dʒ'), ('h', 'h'), ('d', 'd'),
         ('r', 'r'), ('z', 'z'), ('s', 's'), ('f', 'f'), ('q', 'q'), ('k', 'k'), ('l', 'l'), ('m', 'm'), ('n', 'n'), ('w', 'w'),
         ('y', 'j'), ('g', 'g'), ('v', 'v'), ('p', 'p'), ('c', 'k'), ('x', 'ks')]

def ar_word_ipa(w):
    w = w.lower().strip("-.?!")
    segs = []
    i = 0
    while i < len(w):
        for a, b in AR_DI:
            if w.startswith(a, i):
                segs.append(b); i += len(a); break
        else:
            i += 1
    # w/y between a vowel and a non-vowel is an offglide: keep as consonant (ay -> aj) - fine for the syllabifier
    s = ''.join(segs)
    syl = syllabify_word(s)
    parts = syl.split('.')
    if len(parts) > 1:
        # stress: final superheavy, else penult if heavy or word has 2 syllables, else antepenult
        def heavy(p):
            v = re.search(r'[aeiou]ː?', p)
            return bool(v and (v.group(0).endswith('ː') or re.search(r'[aeiou]ː?[^aeiouː]', p)))
        k = len(parts) - 2
        last = parts[-1]
        if re.search(r'(ː[^aeiouː]|[aeiou][^aeiouː]{2,})$', last): k = len(parts) - 1
        elif len(parts) >= 3 and not heavy(parts[-2]): k = len(parts) - 3
        parts[k] = 'ˈ' + parts[k]
        syl = ''
        for j, p in enumerate(parts):
            syl += p if (j == 0 or p.startswith('ˈ')) else '.' + p
    return syl

def ar_rom_ipa(rom):
    out = []
    for w in re.split(r'[\s,;:!?()]+', rom):
        if not w: continue
        m = re.match(r'^(a[ln])-(.+)$', w.lower())           # article: al-bayt, ash-shams
        if m:
            art = 'al' if m.group(1) == 'al' else 'a'
            rest = m.group(2)
            if m.group(1) != 'al': art = 'a'
            out.append(ar_word_ipa(art + rest if art == 'al' else 'a' + rest))
            continue
        m = re.match(r'^a([tdsrzn]|th|dh|sh)-(.+)$', w.lower())
        if m:
            out.append(ar_word_ipa('a' + m.group(1) + m.group(2)))
            continue
        out.append(ar_word_ipa(w.replace('-', '')))
    return ' '.join(x for x in out if x)

# ---------------------------------------------------------------- word lexicons for sentence text (ar, gr)
AR_STRIP = re.compile(r'[ً-ْٰـ]')
def ar_norm(w):
    w = AR_STRIP.sub('', w)
    return re.sub('[أإآ]', 'ا', w).replace('ة', 'ه').replace('ى', 'ي')

def build_lexicon(items, lang, reading_to_words):
    lex = {}
    for t, r in items.items():
        if not r: continue
        tw = [x for x in re.split(r'[\s،,.;:!?؟()\[\]«»"“”/]+', t) if x]
        rw = reading_to_words(r)
        if len(tw) == len(rw):
            for a, b in zip(tw, rw):
                k = ar_norm(a) if lang == 'ar' else a.lower()
                lex.setdefault(k, b)
    return lex

def ar_text_ipa(text, reading, lex):
    if reading: return ar_rom_ipa(reading)
    out = []
    for w in [x for x in re.split(r'[\s،,.;:!?؟()\[\]«»"“”/]+', text) if x]:
        k = ar_norm(w)
        if k in lex: out.append(ar_rom_ipa(lex[k])); continue
        done = False
        for pre, pipa in (('وال', 'wal'), ('بال', 'bil'), ('لل', 'lil'), ('ال', 'al'), ('و', 'wa'), ('ب', 'bi'), ('ل', 'li'), ('ف', 'fa'), ('ك', 'ka')):
            if k.startswith(pre) and k[len(pre):] in lex:
                rest = lex[k[len(pre):]]
                out.append(ar_rom_ipa(pipa + rest.split('-')[-1] if pre.endswith('ال') or pre == 'لل' else pipa + rest)); done = True; break
            if k.startswith(pre) and ('ال' + k[len(pre):]) in lex and not pre.endswith('ال'):
                rest = lex['ال' + k[len(pre):]]
                out.append(ar_rom_ipa(pipa + rest.replace('-', ''))); done = True; break
        if not done:
            out.append(syllabify(espeak(w, 'ar')))
    return ' '.join(x for x in out if x)

def gr_text_ipa(text, reading, lex):
    if reading: return syllabify(reading.replace('|', ' '))
    out = []
    for w in [x for x in re.split(r'[\s,.;:!?()\[\]«»"“”/]+', text) if x]:
        k = w.lower().strip("'’")
        if k in lex: out.append(syllabify(lex[k])); continue
        out.append(syllabify(espeak(re.sub('sc', 'sg', k), 'gd')))
    return ' '.join(x for x in out if x)

# ---------------------------------------------------------------- per-language dispatcher
def clean_espeak(ipa, lang):
    if lang == 'vi': ipa = re.sub(r'[\dɜ]', '', ipa).replace('y', 'ɨ')
    if lang == 'sv': ipa = ipa.replace('sx', 'ɧ')
    if lang == 'ru': ipa = ipa.replace('y', 'ɨ').replace('ɵ', 'o')
    if lang == 'eng': ipa = ipa.replace('ɾ', 't')
    ipa = ipa.replace('ɚ', 'ɚ')
    return ipa

def plain(text):
    t = re.sub(r'\{([^|}]*)\|[^}]*\}', r'\1', text)
    return t.replace('…', ' ').replace('___', ' ')

def transcribe(lang, text, reading, ctx):
    if lang == 'ja': return ja_ipa(text) or syllabify(espeak(re.sub(r'(?<=[A-Z])(?=[A-Z])', ' ', plain(text)), 'en-us'))
    if lang == 'zh': return zh_ipa(text, reading)
    if lang == 'yue': return yue_ipa(text, reading)
    if lang == 'ko': return ko_ipa(text)
    if lang == 'ar': return ar_text_ipa(text, reading, ctx['ar_lex'])
    if lang == 'gr': return gr_text_ipa(text, reading, ctx['gr_lex'])
    t = plain(text)
    t = re.sub(r'\s*/\s*', ', ', t)
    return syllabify(clean_espeak(espeak(t, ESPEAK_VOICE[lang]), lang))

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    fresh = '--fresh' in sys.argv
    items = collect()
    langs = args or list(items.keys())
    os.makedirs(OUT, exist_ok=True)
    ctx = {}
    if 'ar' in langs:
        ctx['ar_lex'] = build_lexicon(items['ar'], 'ar', lambda r: [x for x in re.split(r'[\s,;:!?()]+', r) if x])
    if 'gr' in langs:
        ctx['gr_lex'] = build_lexicon(items['gr'], 'gr', lambda r: [x for x in re.split(r'[\s|]+', r) if x])
    for lang in langs:
        path = os.path.join(OUT, lang + '.json')
        old = {}
        if not fresh and os.path.exists(path):
            old = json.load(open(path, encoding='utf-8')).get('ipa', {})
        ipa, made = {}, 0
        for t, r in items[lang].items():
            if t in old: ipa[t] = old[t]; continue
            try:
                x = transcribe(lang, t, r, ctx)
            except Exception as e:
                print('  !', lang, repr(t), e); x = ''
            if x: ipa[t] = x; made += 1
        json.dump({'lang': lang, 'ipa': ipa}, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        print('%-4s %5d strings, %5d new, %4d KB' % (lang, len(ipa), made, os.path.getsize(path) // 1024))

if __name__ == '__main__':
    main()
