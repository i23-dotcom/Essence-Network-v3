#!/usr/bin/env python3
import base64, hashlib, hmac, json, mimetypes, os, secrets, shutil, subprocess, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('ESSENCE_DATA_DIR', str(ROOT/'data')))
WEB=ROOT/'web'; CONFIG=ROOT/'config'/'station.json'
MEDIA=DATA/'media'; HLS=DATA/'hls'; LOGS=DATA/'logs'; CF_FILE=DATA/'cloudflare_inputs.json'; STATE_FILE=DATA/'studio_state.json'
PORT=int(os.environ.get('PORT','8080')); MAX_UPLOAD=int(os.environ.get('MAX_UPLOAD_MB','2048'))*1024*1024
for d in (DATA,MEDIA,HLS,LOGS): d.mkdir(parents=True, exist_ok=True)
seed=ROOT/'media'/'essence-demo.mp4'; demo=MEDIA/'essence-demo.mp4'
if seed.exists() and not demo.exists(): shutil.copy2(seed,demo)
CFG=json.loads(CONFIG.read_text(encoding='utf-8'))
ADMIN_EMAIL=os.environ.get('ESSENCE_ADMIN_EMAIL','admin@essencenetwork.tv')
ADMIN_PASSWORD=os.environ.get('ESSENCE_ADMIN_PASSWORD','change-me-now')
SESSION_SECRET=os.environ.get('ESSENCE_SESSION_SECRET','change-this-secret')
AUTO_START=os.environ.get('ESSENCE_AUTO_START','1')=='1'
AUTO_CLOUDFLARE=os.environ.get('ESSENCE_AUTO_CLOUDFLARE','1')=='1'
MAX_AGE=60*60*12
lock=threading.RLock(); sessions={}

def default_channel(c):
    return {'status':'OFF AIR','current':'No program','next':'No next item','pid':None,'proc':None,'started_at':None,'restarts':0,'playlist':[],
            'visual':{'watermark':True,'fit':'scale'},'graphics':{'lower_third':'','ticker':'','enabled':False},
            'audio':{'volume':100,'muted':False}}

state={'channels':{c['id']:default_channel(c) for c in CFG['channels']}}
if STATE_FILE.exists():
    try:
        saved=json.loads(STATE_FILE.read_text(encoding='utf-8'))
        for cid, v in saved.get('channels',{}).items():
            if cid in state['channels']:
                for k in ('playlist','visual','graphics','audio','current','next'):
                    if k in v: state['channels'][cid][k]=v[k]
    except Exception: pass

def persist():
    with lock:
        out={'channels':{cid:{k:v for k,v in s.items() if k!='proc'} for cid,s in state['channels'].items()}}
    STATE_FILE.write_text(json.dumps(out,indent=2),encoding='utf-8')

def ch(cid): return next((c for c in CFG['channels'] if c['id']==cid),None)
def slug(s): return ''.join(x if x.isalnum() or x in '-_' else '-' for x in s.lower().replace(' ','-'))
def sign(v): return hmac.new(SESSION_SECRET.encode(),v.encode(),hashlib.sha256).hexdigest()
def new_session(): sid=secrets.token_urlsafe(32); sessions[sid]=time.time()+MAX_AGE; return sid
def authed(handler):
    raw=handler.headers.get('Cookie','')
    sid=next((x.split('=',1)[1] for x in raw.split('; ') if x.startswith('essence_session=')),None)
    return bool(sid and sid in sessions and sessions[sid] >= time.time())
def stream_url(cid):
    env='ESSENCE_'+cid.upper().replace('-','_')+'_HLS_URL'
    return os.environ.get(env) or ('/hls/'+cid+'/index.m3u8')

def media_path(name):
    p=(MEDIA/Path(name).name).resolve()
    return p if p.parent==MEDIA.resolve() and p.exists() else None

def kill_process(cid):
    with lock:
        s=state['channels'][cid]; p=s.get('proc')
        if p and p.poll() is None:
            try: p.terminate(); p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass
        s.update({'pid':None,'proc':None,'status':'OFF AIR'})

def ffmpeg_filter(cid):
    s=state['channels'][cid]; g=s['graphics']; v=s['visual']; a=s['audio']
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    parts=[]
    if v.get('watermark') and (ROOT/'web'/'essence-logo.png').exists():
        parts.append('[0:v][1:v]overlay=24:24:format=auto[v0]')
        chain='[v0]'
    else:
        chain='[0:v]'
    if g.get('enabled') and g.get('lower_third'):
        txt=str(g['lower_third']).replace('\\',' ').replace(':','\\:').replace("'","\\'")
        parts.append(f"{chain}drawtext=fontfile={font}:text='{txt}':x=40:y=h-100:fontsize=34:fontcolor=white:box=1:boxcolor=0x0B4F8A@0.88:boxborderw=18[v1]")
        chain='[v1]'
    if g.get('enabled') and g.get('ticker'):
        txt=str(g['ticker']).replace('\\',' ').replace(':','\\:').replace("'","\\'")
        parts.append(f"{chain}drawtext=fontfile={font}:text='{txt}':x=w-mod(t*180\\,w+tw):y=h-45:fontsize=22:fontcolor=white:box=1:boxcolor=0x080B12@0.85:boxborderw=8[v2]")
        chain='[v2]'
    parts.append(chain+'null[vout]')
    vol='0' if a.get('muted') else str(max(0,min(150,int(a.get('volume',100))))/100)
    return ';'.join(parts),vol,bool(v.get('watermark') and (ROOT/'web'/'essence-logo.png').exists())

def start_channel(cid, restart=False, asset=None):
    c=ch(cid)
    if not c: return False,'Unknown channel'
    kill_process(cid)
    s=state['channels'][cid]
    chosen=asset or (s['playlist'][0] if s['playlist'] else 'essence-demo.mp4')
    mp=media_path(chosen) or demo
    out=HLS/cid; out.mkdir(parents=True,exist_ok=True)
    for x in out.glob('*'):
        try:x.unlink()
        except:pass
    target=out/'index.m3u8'
    rtmp=os.environ.get('ESSENCE_'+cid.upper().replace('-','_')+'_RTMPS_URL')
    if not rtmp and CF_FILE.exists():
        try:
            inp=json.loads(CF_FILE.read_text(encoding='utf-8')).get(cid,{})
            r=inp.get('rtmps',{}) if isinstance(inp,dict) else {}
            if r.get('url') and r.get('streamKey'): rtmp=r['url']+r['streamKey']
        except Exception: rtmp=None
    vf,vol,use_logo=ffmpeg_filter(cid)
    base=['ffmpeg','-hide_banner','-loglevel','warning','-re','-stream_loop','-1','-i',str(mp)]
    if use_logo:
        base += ['-loop','1','-i',str(ROOT/'web'/'essence-logo.png')]
    base += ['-filter_complex',vf,'-map','[vout]','-map','0:a:0?','-c:v','libx264','-preset','veryfast','-tune','zerolatency','-pix_fmt','yuv420p','-r','25','-g','50','-keyint_min','50','-sc_threshold','0','-c:a','aac','-b:a','128k','-ar','48000','-af',f'volume={vol}']
    if rtmp:
        cmd=base+['-f','tee',f'[f=hls:hls_time=2:hls_list_size=8:hls_flags=delete_segments+append_list]{target}|[f=flv]{rtmp}']
    else:
        cmd=base+['-f','hls','-hls_time','2','-hls_list_size','8','-hls_flags','delete_segments+append_list',str(target)]
    log=open(LOGS/f'{cid}.log','a',buffering=1)
    p=subprocess.Popen(cmd,stdout=log,stderr=log)
    with lock:
        s['status']='ON AIR'; s['current']=Path(mp).name; s['next']=s['playlist'][1] if len(s['playlist'])>1 else 'Standby'; s['pid']=p.pid; s['proc']=p; s['started_at']=time.time()
        if restart:s['restarts']+=1
    persist(); return True,'ON AIR'

def stop_channel(cid): kill_process(cid); persist(); return True,'OFF AIR'

def watchdog():
    while True:
        time.sleep(5)
        for cid in list(state['channels']):
            with lock: p=state['channels'][cid].get('proc'); running=state['channels'][cid]['status']=='ON AIR'
            if running and p is not None and p.poll() is not None: start_channel(cid,restart=True)
threading.Thread(target=watchdog,daemon=True).start()
if AUTO_START: threading.Thread(target=lambda:[start_channel(c['id']) for c in CFG['channels']],daemon=True).start()

def cf_request(method,path,body=None):
    token=os.environ.get('CLOUDFLARE_API_TOKEN'); account=os.environ.get('CLOUDFLARE_ACCOUNT_ID')
    if not token or not account:return None,'Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID first.'
    req=urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{account}/stream/live_inputs{path}',data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read()),None
    except Exception as e:return None,str(e)
def provision_cloudflare():
    existing=json.loads(CF_FILE.read_text()) if CF_FILE.exists() else {}; out={}
    for c in CFG['channels']:
        cid=c['id']
        if cid in existing:out[cid]=existing[cid];continue
        data,err=cf_request('POST','',{'meta':{'name':c['name']},'recording':{'mode':'automatic'}})
        if err:return False,err,out
        if not data or not data.get('success'):return False,str(data),out
        r=data['result']; out[cid]={'uid':r.get('uid'),'rtmps':r.get('rtmps',{}),'created':time.time()}
    CF_FILE.write_text(json.dumps(out,indent=2),encoding='utf-8'); return True,'Provisioned',out
if AUTO_CLOUDFLARE and os.environ.get('CLOUDFLARE_API_TOKEN') and os.environ.get('CLOUDFLARE_ACCOUNT_ID'):
    try: provision_cloudflare()
    except Exception: pass

class H(BaseHTTPRequestHandler):
    server_version='EssenceOnline/5.0'
    def send(self,code,body=b'',ctype='application/json',cache='no-store'):
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Cache-Control',cache);self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def js(self,o,code=200):self.send(code,json.dumps(o).encode())
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>MAX_UPLOAD:return None
        return self.rfile.read(n)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path);p=u.path
        if p=='/api/health':return self.js({'ok':True,'service':'essence-online-broadcast-studio','time':time.time()})
        if p=='/api/public':
            return self.js({'brand':CFG['brand'],'channels':[self.public_channel(c) for c in CFG['channels']]})
        if p=='/api/auth/status':return self.js({'authenticated':authed(self)})
        if p.startswith('/api/watch/'):
            cid=p.split('/')[-1];c=ch(cid)
            return self.js({'ok':bool(c),'channel':self.public_channel(c) if c else None},200 if c else 404)
        if p.startswith('/media/'):
            mp=media_path(urllib.parse.unquote(p[len('/media/'):]))
            if not mp:return self.send(404,b'Not found','text/plain')
            return self.send(200,mp.read_bytes(),mimetypes.guess_type(mp.name)[0] or 'application/octet-stream','public, max-age=3600')
        if p.startswith('/hls/'):
            rel=p[len('/hls/'):];fp=(HLS/rel).resolve()
            if fp.exists() and HLS.resolve() in fp.parents:
                return self.send(200,fp.read_bytes(),mimetypes.guess_type(fp.name)[0] or 'application/octet-stream','no-cache')
            return self.send(404,b'Not found','text/plain')
        if p.startswith('/api/studio'):
            if not authed(self):return self.js({'ok':False,'message':'Unauthorized'},401)
            chans=[self.public_channel(c,full=True) for c in CFG['channels']]
            media=[]
            for f in sorted(MEDIA.iterdir()):
                if f.is_file():media.append({'name':f.name,'size':f.stat().st_size,'type':mimetypes.guess_type(f.name)[0] or 'application/octet-stream','url':'/media/'+urllib.parse.quote(f.name)})
            return self.js({'brand':CFG['brand'],'channels':chans,'programs':CFG['programs'],'media':media})
        if p in ('/','/index.html'):return self.file('index.html')
        if p=='/login.html':return self.file('login.html')
        if p=='/studio.html':return self.file('studio.html')
        if p=='/watch.html':return self.file('watch.html')
        if p=='/essence-logo.png':return self.file('essence-logo.png')
        return self.js({'ok':False,'message':'Not found'},404)
    def public_channel(self,c,full=False):
        with lock:s=state['channels'][c['id']].copy();s.pop('proc',None)
        out={**c,**s,'stream_url':stream_url(c['id']),'program_url':('/media/'+urllib.parse.quote(Path(s['current']).name)) if media_path(s['current']) else None}
        if not full: out.pop('playlist',None);out.pop('visual',None);out.pop('graphics',None);out.pop('audio',None)
        return out
    def file(self,name):
        fp=WEB/name
        if not fp.exists():return self.send(404,b'Not found','text/plain')
        return self.send(200,fp.read_bytes(),mimetypes.guess_type(fp.name)[0] or 'text/html')
    def do_POST(self):
        u=urllib.parse.urlparse(self.path);p=u.path
        if p=='/api/login':
            try: data=json.loads(self.body() or b'{}')
            except: data={}
            if hmac.compare_digest(str(data.get('email','')),ADMIN_EMAIL) and hmac.compare_digest(str(data.get('password','')),ADMIN_PASSWORD):
                sid=new_session();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie',f'essence_session={sid}; HttpOnly; SameSite=Lax; Max-Age={MAX_AGE}; Path=/');self.end_headers();self.wfile.write(b'{"ok":true}');return
            return self.js({'ok':False,'message':'Invalid credentials'},401)
        if p=='/api/logout':
            raw=self.headers.get('Cookie','');sid=next((x.split('=',1)[1] for x in raw.split('; ') if x.startswith('essence_session=')),None);sessions.pop(sid,None);self.js({'ok':True});return
        if not authed(self):return self.js({'ok':False,'message':'Unauthorized'},401)
        if p.startswith('/api/start/'):
            cid=p.split('/')[-1]; return self.js(dict(zip(('ok','message'),start_channel(cid))))
        if p.startswith('/api/stop/'):
            cid=p.split('/')[-1]; return self.js(dict(zip(('ok','message'),stop_channel(cid))))
        if p=='/api/start-all':
            r=[(c['id'],)+start_channel(c['id']) for c in CFG['channels']];return self.js({'ok':all(x[1] for x in r),'results':r})
        if p=='/api/stop-all':
            for c in CFG['channels']:stop_channel(c['id'])
            return self.js({'ok':True})
        if p=='/api/upload':
            data=self.body()
            if data is None:return self.js({'ok':False,'message':'File too large'},413)
            name=os.path.basename(urllib.parse.parse_qs(u.query).get('name',['upload.bin'])[0])
            ext=Path(name).suffix.lower()
            allowed={'.mp4','.mov','.mkv','.webm','.m4v','.mp3','.wav','.jpg','.jpeg','.png'}
            if ext not in allowed:return self.js({'ok':False,'message':'Unsupported media type'},400)
            target=MEDIA/name;target.write_bytes(data);return self.js({'ok':True,'name':name,'size':len(data),'url':'/media/'+urllib.parse.quote(name)})
        if p=='/api/channel/config':
            try:d=json.loads(self.body() or b'{}')
            except:return self.js({'ok':False,'message':'Invalid JSON'},400)
            cid=d.get('channel');s=state['channels'].get(cid)
            if not s:return self.js({'ok':False,'message':'Unknown channel'},404)
            if 'playlist' in d:s['playlist']=[Path(x).name for x in d['playlist'] if media_path(x)]
            if 'graphics' in d:s['graphics']={**s['graphics'],**d['graphics']}
            if 'visual' in d:s['visual']={**s['visual'],**d['visual']}
            if 'audio' in d:s['audio']={**s['audio'],**d['audio']}
            persist();return self.js({'ok':True,'channel':self.public_channel(ch(cid),True)})
        if p=='/api/channel/take':
            try:d=json.loads(self.body() or b'{}')
            except:return self.js({'ok':False,'message':'Invalid JSON'},400)
            cid=d.get('channel');asset=Path(str(d.get('asset',''))).name
            if cid not in state['channels'] or not media_path(asset):return self.js({'ok':False,'message':'Channel or media not found'},400)
            if asset not in state['channels'][cid]['playlist']:state['channels'][cid]['playlist'].insert(0,asset)
            return self.js(dict(zip(('ok','message'),start_channel(cid,asset=asset))))
        if p=='/api/cloudflare/provision':
            ok,msg,data=provision_cloudflare();return self.js({'ok':ok,'message':msg,'channels':data})
        return self.js({'ok':False,'message':'Unknown endpoint'},404)

def cleanup():
    for cid in state['channels']:kill_process(cid)
if __name__=='__main__':
    print(f'Essence Network Production Studio on 0.0.0.0:{PORT}')
    try:ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
    except KeyboardInterrupt:cleanup()
