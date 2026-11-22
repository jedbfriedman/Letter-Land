"""Stamp every voice/word file's content hash into index.html (VHASH).
Unchanged files keep the same address, so devices keep their offline copy across updates.
Run before every deploy:  python3 tools/stamp.py"""
import hashlib, glob, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = ['voice.js', 'svoice.js', 'pvoice.js', 'words.js'] + sorted('v/' + os.path.basename(f) for f in glob.glob(os.path.join(ROOT, 'v', '*.js')))
H = {f: hashlib.md5(open(os.path.join(ROOT, f), 'rb').read()).hexdigest()[:10] for f in files if os.path.exists(os.path.join(ROOT, f))}
p = os.path.join(ROOT, 'index.html'); s = open(p).read()
new, n = re.subn(r'const VHASH=\{[^}]*\};/\*VHASH\*/', 'const VHASH=' + json.dumps(H, separators=(',', ':')) + ';/*VHASH*/', s)
assert n == 1, 'VHASH marker not found'
open(p, 'w').write(new); print('stamped', len(H), 'files')
