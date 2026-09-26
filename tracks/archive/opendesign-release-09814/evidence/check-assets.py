#!/usr/bin/env python3
"""Verify the exact prepared release bytes and source identity before publication."""
from pathlib import Path
import hashlib, json, re, subprocess
ROOT = Path(__file__).resolve().parents[3]
ASSETS = Path('/root/opendesign-release14')
manifest = json.loads((Path(__file__).parent / 'asset-manifest.json').read_text())
version = manifest['version']
web = re.search(r'^VERSION = "([^"]+)"', (ROOT/'bin/ds_web.py').read_text(), re.M).group(1)
package = json.loads((ROOT/'desktop/package.json').read_text())
lock = json.loads((ROOT/'desktop/package-lock.json').read_text())
assert web == package['version'] == lock['version'] == lock['packages']['']['version'] == version
print('OK versions', version)
subprocess.run(['git','diff','--exit-code',manifest['head'],'HEAD','--','.',':(exclude)tracks'],cwd=ROOT,check=True)
print('OK product source equals tested CI commit',manifest['head'])
for name, expected in manifest['assets'].items():
    p = ASSETS/name if name == 'latest.yml' else ASSETS/'artifact'/name
    assert p.stat().st_size == expected['size'], name
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected['sha256'], name
    print('OK bytes',name,expected['size'],expected['sha256'])
installer=ASSETS/'artifact'/('OpenDesign-'+version+'-electron-setup.exe')
for feed in [ASSETS/'artifact/latest.yml',ASSETS/'latest.yml']:
    subprocess.run(['node',str(ROOT/'desktop/scripts/release-feed.mjs'),'verify',str(feed),str(installer)],check=True)
text=(ASSETS/'latest.yml').read_text()
assert 'https://github.com/SunJ1ayu/OpenDesign/releases/download/v'+version+'/' in text
print('OK release feed uses versioned official URL')
