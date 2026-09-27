"""Verify the published source and unauthenticated automatic update downloads."""
import base64,hashlib,json,re,subprocess,time,urllib.request
from pathlib import Path

OUT=Path('/root/opendesign-release18')
REPO='SunJ1ayu/OpenDesign'
TAG='v0.98.18'
SHA='8986c7a99c3f4f9f73fa81850ab32ccafb1ebbd7'
manifest=json.loads((OUT/'manifest.json').read_text())
expected={f['name']:{'size':f['bytes'],'sha256':f['sha256']} for f in manifest['files']}
pubfeed=OUT/'publish/latest.yml'
expected['latest.yml']={'size':pubfeed.stat().st_size,'sha256':hashlib.sha256(pubfeed.read_bytes()).hexdigest()}
checks=[]
def need(cond,label):
    if not cond:raise AssertionError(label)
    checks.append(label);print('PASS',label,flush=True)
def api(path):
    return json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/{path}']))
def fetch(url,keep=False):
    last=None
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'OpenDesign-release-smoke'})
            h256,h512=hashlib.sha256(),hashlib.sha512();n=0;parts=[]
            with urllib.request.urlopen(request,timeout=60) as response:
                need(response.status==200,'HTTP 200 '+url)
                while block:=response.read(1024*1024):
                    n+=len(block);h256.update(block);h512.update(block)
                    if keep:parts.append(block)
            return n,h256.hexdigest(),base64.b64encode(h512.digest()).decode(),b''.join(parts)
        except Exception as exc:
            last=exc
            if attempt<2:time.sleep(3)
    raise last

release=api('releases/tags/'+TAG)
need(not release['draft'] and not release['prerelease'] and release['published_at'],'formal release published')
need(release['body'].replace('\r\n','\n').strip()==(OUT/'release-notes.md').read_text().strip(),'published notes match approved notes')
need(api('releases/latest')['tag_name']==TAG,'official latest release is '+TAG)
need(api('git/ref/heads/main')['object']['sha']==SHA,'main points to the tested build commit')
ref=api('git/ref/tags/'+TAG)['object']
while ref['type']=='tag':ref=api('git/tags/'+ref['sha'])['object']
need(ref['type']=='commit' and ref['sha']==SHA,'release tag points to tested commit '+SHA)
pr=api('pulls/4')
need(pr['merged'] and pr['merged_at'],'PR #4 merged')
assets={a['name']:a for a in release['assets']}
need(set(assets)==set(expected),'exactly three expected release assets')
n,h,_,feed=fetch(f'https://github.com/{REPO}/releases/latest/download/latest.yml',True)
need(n==expected['latest.yml']['size'] and h==expected['latest.yml']['sha256'],'unauthenticated latest feed matches verified bytes')
text=feed.decode()
need(re.search(r'^version: 0\.98\.18\s*$',text,re.M),'automatic update feed is 0.98.18')
exe=None
for name,ex in expected.items():
    asset=assets[name];url=f'https://github.com/{REPO}/releases/download/{TAG}/{name}'
    need(asset['browser_download_url']==url and asset['state']=='uploaded','official asset URL '+name)
    result=fetch(url)
    need(result[0]==ex['size']==asset['size'] and result[1]==ex['sha256'],'public bytes match verified asset '+name)
    if name.endswith('.exe'):exe=result;need(url in text,'feed points to verified installer')
need(exe is not None,'public installer downloaded and hashed')
need(set(re.findall(r'^\s*sha512:\s*(\S+)\s*$',text,re.M))=={exe[2]},'live SHA-512 matches public installer')
need(set(re.findall(r'^\s*size:\s*(\d+)\s*$',text,re.M))=={str(exe[0])},'live size matches public installer')
old=f'https://github.com/{REPO}/releases/download/v0.98.16/OpenDesign-0.98.16-electron-setup.exe.blockmap'
need(fetch(old)[0]>0,'0.98.16 blockmap remains downloadable for differential update')
receipt={'tag':TAG,'commit':SHA,'releaseUrl':release['html_url'],'publishedAt':release['published_at'],'mergedAt':pr['merged_at'],'checks':checks,'assets':expected}
(OUT/'evidence/production-smoke.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print('PRODUCTION SMOKE PASS',release['html_url'],flush=True)
