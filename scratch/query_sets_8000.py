import requests
s=requests.Session(); base='http://127.0.0.1:8000'; print('login',s.post(base+'/api/session/login',json={'email':'bashmix@gmail.com','password':'B@shmix123'}).status_code)
for p in ['/api/tournaments/tournament%2Ftestfnc/sets','/api/tournaments/tournament%2Ftestfnc/sync-status','/api/tournaments/challonge%3A18449397/sets']:
 r=s.get(base+p); print(p,r.status_code); 
 try:
  d=r.json(); print('keys',list(d)[:15]);
  sets=d.get('sets',[]); print('count',len(sets));
  for x in sets[:30]:
   st=str(x)
   if any(n.lower() in st.lower() for n in ['bashmix','fncesports','ahmad21']): print(x)
 except Exception as e: print(r.text[:200])

