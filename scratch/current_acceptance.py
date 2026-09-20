import requests, json
base='http://127.0.0.1:5173'
s=requests.Session()
r=s.post(base+'/api/session/login',json={'email':'bashmix@gmail.com','password':'B@shmix123'},timeout=20)
print('login',r.status_code)
for path in ['/api/tournaments','/api/integrations','/api/stations','/api/active-matches','/api/organizer-console?view=all']:
    rr=s.get(base+path,timeout=20)
    print(path,rr.status_code)
    try:
      d=rr.json()
      if path=='/api/integrations':
        print('accounts',[(x.get('provider_type'),x.get('display_name'),x.get('status'),x.get('external_account_id')) for x in d.get('accounts',d if isinstance(d,list) else [])])
      elif path=='/api/tournaments':
        print('tournaments',[(x.get('slug'),x.get('provider_type'),x.get('provider_account_id'),x.get('provider_sync_status')) for x in d.get('tournaments',[])])
      elif path=='/api/stations':
        print('stations',[(x.get('id'),x.get('public_id'),x.get('name'),x.get('active_match_id'),x.get('active_overlay'),len(x.get('overlays',[]))) for x in d.get('stations',[])])
      elif path=='/api/active-matches':
        ms=d.get('matches',d if isinstance(d,list) else [])
        print('matches',[(m.get('set_id'),m.get('tournament_slug'),m.get('status'),m.get('p1_name'),m.get('p2_name'),m.get('p1_discord'),m.get('p2_discord'),m.get('discord_thread_id'),m.get('call_message_id'),m.get('is_stream_match')) for m in ms])
      else:
        print('keys', list(d)[:20] if isinstance(d,dict) else type(d).__name__)
    except Exception as e: print('jsonerr',str(e))
