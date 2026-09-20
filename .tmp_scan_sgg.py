import requests,re,os,urllib.parse
from pathlib import Path
html=requests.get('https://www.start.gg/admin/tournament/testfnc/brackets/1640502/2307972/3339325',timeout=30).text
srcs=re.findall(r'<script[^>]+src="([^"]+)"',html)
base='https://www.start.gg'
out=Path('.tmp_sgg_chunks'); out.mkdir(exist_ok=True)
print('scripts',len(srcs))
for i,src in enumerate(srcs):
 u=urllib.parse.urljoin(base,src)
 try:
  rr=requests.get(u,timeout=30)
  if rr.ok:
   (out/f'{i:03d}.js').write_text(rr.text,encoding='utf-8')
 except Exception as e: pass
print('downloaded',len(list(out.glob('*.js'))))
patterns=['resetBracket','Reset Bracket','resetPhase','resetPhaseGroup','Start Bracket','startBracket','updatePhaseGroups','resetSet','resetDependentSets']
for p in patterns:
 hits=[]
 for f in out.glob('*.js'):
  s=f.read_text(encoding='utf-8',errors='ignore')
  if p in s: hits.append(str(f))
 print(p, hits)
for f in out.glob('*.js'):
 s=f.read_text(encoding='utf-8',errors='ignore')
 for p in patterns[:7]:
  pos=s.find(p)
  if pos>=0:
   print('\nFOUND',p,f,'at',pos, '\n', s[max(0,pos-500):pos+1200])
