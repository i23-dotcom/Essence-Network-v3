#!/usr/bin/env python3
import base64, hashlib, hmac, json, mimetypes, os, secrets, shutil, subprocess, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('ESSENCE_DATA_DIR',str(ROOT/'data')))
WEB=ROOT/'web'; CONFIG=ROOT/'config'/'station.json'
MEDIA=DATA/'media'; HLS=DATA/'hls'; LOGS=DATA/'logs'; CF_FILE=DATA/'cloudflare_inputs.json'
PORT=int(os.environ.get('PORT','8080')); MAX_UPLOAD=int(os.environ.get('MAX_UPLOAD_MB','2048'))*1024*1024
for d in (DATA,MEDIA,HLS,LOGS): d.mkdir(parents=True,exist_ok=True)
# seed demo asset into persistent data
seed=ROOT/'media'/'essence-demo.mp4'; demo=MEDIA/'essence-demo.mp4'
if seed.exists() and not demo.exists(): shutil.copy2(seed,demo)
CFG=json.loads(CONFIG.read_text(encoding='utf-8'))
ADMIN_EMAIL=os.environ.get('ESSENCE_ADMIN_EMAIL','admin@essencenetwork.tv')
ADMIN_PASSWORD=os.environ.get('ESSENCE_ADMIN_PASSWORD','change-me-now')
SESSION_SECRET=os.environ.get('ESSENCE_SESSION_SECRET','change-this-secret')
AUTO_START=os.environ.get('ESSENCE_AUTO_START','1')=='1'
AUTO_CLOUDFLARE=os.environ.get('ESSENCE_AUTO_CLOUDFLARE','1')=='1'
MAX_AGE=60*60*12
state={'channels':{c['id']:{'status':'OFF AIR','current':'No program','next':'Awaiting schedule','pid':None,'proc':None,'started_at':None,'restarts':0} for c in CFG['channels']}}
lock=threading.RLock(); sessions={}

def ch(cid): return next((c for c in CFG['channels'] if c['id']==cid),None)
def slug(s): return ''.join(x if x.isalnum() or x in '-_' else '-' for x in s.lower().replace(' ','-'))
def sign(v): return hmac.new(SESSION_SECRET.encode(),v.encode(),hashlib.sha256).hexdigest()
def new_session():
    sid=secrets.token_urlsafe(32); sessions[sid]=time.time()+MAX_AGE; return sid
def authed(handler):
    raw=handler.headers.get('Cookie','')
    sid=next((x.split('=',1)[1] for x in raw.split('; ') if x.startswith('essence_session=')),None)
    if not sid or sid not in sessions or sessions[sid]<time.time(): return False
    return True
def stream_url(cid):
    # External HLS is preferred for public delivery; otherwise local station HLS is used.
    env='ESSENCE_'+cid.upper().replace('-','_')+'_HLS_URL'
    return os.environ.get(env) or ('/hls/'+cid+'/index.m3u8')
def kill_process(cid):
    with lock:
        s=state['channels'][cid]; p=s.get('proc')
        if p and p.poll() is None:
            try: p.terminate(); p.wait(timeout=3)
            except Exception:
                try: p.kill()
                except Exception: pass
        s.update({'pid':None,'proc':None,'status':'OFF AIR'})
def start_channel(cid, restart=False):
    c=ch(cid)
    if not c: return False,'Unknown channel'
    kill_process(cid)
    out=HLS/cid; out.mkdir(parents=True,exist_ok=True)
    for x in out.glob('*'):
        try:x.unlink()
        except:pass
    # 24/7 demo playout. When a Cloudflare Live Input exists, send the same encoded
    # program to Cloudflare while also keeping a local HLS backup for the public player.
    target=out/'index.m3u8'
    rtmp=os.environ.get('ESSENCE_'+cid.upper().replace('-','_')+'_RTMPS_URL')
    if not rtmp and CF_FILE.exists():
        try:
            cf=json.loads(CF_FILE.read_text(encoding='utf-8'))
            inp=cf.get(cid,{})
            r=inp.get('rtmps',{}) if isinstance(inp,dict) else {}
            if r.get('url') and r.get('streamKey'):
                rtmp=r['url']+r['streamKey']
        except Exception:
            rtmp=None
    base=['ffmpeg','-hide_banner','-loglevel','warning','-stream_loop','-1','-re','-i',str(demo),'-c:v','libx264','-preset','veryfast','-tune','zerolatency','-pix_fmt','yuv420p','-r','25','-g','50','-keyint_min','50','-sc_threshold','0','-c:a','aac','-b:a','128k','-ar','48000']
    if rtmp:
        # One encoder, two outputs: local HLS plus Cloudflare RTMPS.
        cmd=base+['-map','0:v:0','-map','0:a:0','-f','tee',f'[f=hls:hls_time=2:hls_list_size=8:hls_flags=delete_segments+append_list]{target}|[f=flv]{rtmp}']
    else:
        cmd=base+['-f','hls','-hls_time','2','-hls_list_size','8','-hls_flags','delete_segments+append_list',str(target)]
    log=open(LOGS/f'{cid}.log','a',buffering=1)
    p=subprocess.Popen(cmd,stdout=log,stderr=log)
    with lock:
        s=state['channels'][cid]; s.update({'status':'ON AIR','current':'Essence Demo / 24-7 playout','next':'Looping demo asset','pid':p.pid,'proc':p,'started_at':time.time()})
        if restart:s['restarts']+=1
    return True,'Started'
def stop_channel(cid): kill_process(cid); return True,'Stopped'

def watchdog():
    while True:
        time.sleep(5)
        with lock:
            ids=list(state['channels'])
        for cid in ids:
            with lock: p=state['channels'][cid].get('proc'); running=state['channels'][cid]['status']=='ON AIR'
            if running and p is not None and p.poll() is not None:
                start_channel(cid,restart=True)
threading.Thread(target=watchdog,daemon=True).start()
if AUTO_START:
    threading.Thread(target=lambda:[start_channel(c['id']) for c in CFG['channels']],daemon=True).start()

def cf_request(method,path,body=None):
    token=os.environ.get('CLOUDFLARE_API_TOKEN'); account=os.environ.get('CLOUDFLARE_ACCOUNT_ID')
    if not token or not account: return None,'Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID first.'
    url=f'https://api.cloudflare.com/client/v4/accounts/{account}/stream/live_inputs{path}'
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read()),None
    except Exception as e:return None,str(e)
def provision_cloudflare():
    existing=json.loads(CF_FILE.read_text()) if CF_FILE.exists() else {}
    out={}
    for c in CFG['channels']:
        cid=c['id']
        if cid in existing: out[cid]=existing[cid]; continue
        data,err=cf_request('POST','',{'meta':{'name':c['name']},'recording':{'mode':'automatic'}})
        if err: return False,err,out
        if not data or not data.get('success'): return False,str(data),out
        r=data['result']; code=os.environ.get('CLOUDFLARE_CUSTOMER_CODE','')
        manifest=(f'https://customer-{code}.cloudflarestream.com/{r.get("uid")}/manifest/video.m3u8' if code else '')
        out[cid]={'uid':r.get('uid'),'rtmps':r.get('rtmps',{}),'created':time.time(),'manifest':manifest}
    CF_FILE.write_text(json.dumps(out,indent=2),encoding='utf-8'); return True,'Provisioned',out

# On production Render deployments, provision Cloudflare inputs automatically when credentials are present.
# This makes a fresh deploy self-starting; without Cloudflare credentials the local HLS demo still runs.
if AUTO_CLOUDFLARE and os.environ.get('CLOUDFLARE_API_TOKEN') and os.environ.get('CLOUDFLARE_ACCOUNT_ID'):
    try:
        ok,msg,data=provision_cloudflare()
        print('Cloudflare provisioning:', ok, msg)
    except Exception as e:
        print('Cloudflare provisioning failed:', e)


class H(BaseHTTPRequestHandler):
    server_version='EssenceOnline/4.0'
    def send(self,code,body=b'',ctype='application/json',cache='no-store'):
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Cache-Control',cache); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def js(self,o,code=200): self.send(code,json.dumps(o).encode())
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>MAX_UPLOAD:return None
        return self.rfile.read(n)
    def do_OPTIONS(self): self.send(204,b'')
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); p=u.path
        if p=='/api/health': return self.js({'ok':True,'service':'essence-online-broadcast','time':time.time()})
        if p=='/api/public':
            chans=[]
            for c in CFG['channels']:
                with lock:s=state['channels'][c['id']].copy(); s.pop('proc',None)
                chans.append({**c,**s,'stream_url':stream_url(c['id'])})
            return self.js({'brand':CFG['brand'],'channels':chans})
        if p=='/api/auth/status': return self.js({'authenticated':authed(self)})
        if p.startswith('/api/watch/'):
            cid=p.split('/')[-1]; c=ch(cid)
            if not c:return self.js({'ok':False},404)
            with lock:s=state['channels'][cid].copy();s.pop('proc',None)
            return self.js({'channel':{**c,**s,'stream_url':stream_url(cid)}})
        if p.startswith('/api/studio'):
            if not authed(self):return self.js({'ok':False,'message':'Unauthorized'},401)
            chans=[]
            for c in CFG['channels']:
                with lock:s=state['channels'][c['id']].copy();s.pop('proc',None)
                chans.append({**c,**s,'stream_url':stream_url(c['id'])})
            media=[]
            for f in sorted(MEDIA.iterdir()):
                if f.is_file(): media.append({'name':f.name,'size':f.stat().st_size,'type':mimetypes.guess_type(f.name)[0] or 'application/octet-stream'})
            cf=json.loads(CF_FILE.read_text()) if CF_FILE.exists() else {}
            return self.js({'brand':CFG['brand'],'channels':chans,'programs':CFG['programs'],'media':media,'cloudflare':cf})
        if p.startswith('/api/start/') or p.startswith('/api/stop/') or p in ('/api/start-all','/api/stop-all','/api/cloudflare/provision'):
            if not authed(self):return self.js({'ok':False,'message':'Unauthorized'},401)
        if p.startswith('/api/start/') or p.startswith('/api/stop/') or p in ('/api/start-all','/api/stop-all','/api/cloudflare/provision'):
            return self.js({'ok':False,'message':'Use POST for control actions'},405)
        if p.startswith('/api/stop/'):
            return self.js(dict(zip(('ok','message'),stop_channel(p.split('/')[-1]))))
        if p=='/api/start-all':
            r=[(c['id'],)+start_channel(c['id']) for c in CFG['channels']]; return self.js({'ok':all(x[1] for x in r),'results':r})
        if p=='/api/stop-all':
            for c in CFG['channels']:stop_channel(c['id'])
            return self.js({'ok':True})
        if p=='/api/cloudflare/provision':
            ok,msg,data=provision_cloudflare();return self.js({'ok':ok,'message':msg,'channels':data})
        if p.startswith('/hls/'):
            rel=p[5:].lstrip('/'); fp=(HLS/rel).resolve()
            if str(fp).startswith(str(HLS.resolve())) and fp.exists() and fp.is_file():
                ct='application/vnd.apple.mpegurl' if fp.suffix=='.m3u8' else 'video/mp2t'; return self.send(200,fp.read_bytes(),ct,'no-cache')
            return self.send(404,b'Not found','text/plain')
        # Public pages
        if p=='/login.html' or p=='/studio.html' or p=='/watch.html' or p=='/index.html' or p=='/':
            file='index.html' if p=='/' else p.lstrip('/')
            fp=WEB/file
        else: fp=(WEB/p.lstrip('/')).resolve()
        if isinstance(fp,Path) and fp.exists() and fp.is_file(): return self.send(200,fp.read_bytes(),mimetypes.guess_type(str(fp))[0] or 'application/octet-stream','public,max-age=60')
        return self.send(404,b'Not found','text/plain')
    def do_POST(self):
        u=urllib.parse.urlparse(self.path); p=u.path
        if p=='/api/login':
            try:d=json.loads(self.body() or b'{}')
            except:d={}
            if hmac.compare_digest(str(d.get('email','')),ADMIN_EMAIL) and hmac.compare_digest(str(d.get('password','')),ADMIN_PASSWORD):
                sid=new_session(); self.send_response(200);self.send_header('Content-Type','application/json'); secure='; Secure' if os.environ.get('HTTPS','1')=='1' else ''; self.send_header('Set-Cookie',f'essence_session={sid}; HttpOnly{secure}; SameSite=Lax; Max-Age={MAX_AGE}; Path=/');self.end_headers();self.wfile.write(b'{"ok":true}');return
            return self.js({'ok':False,'message':'Invalid credentials'},401)
        if p=='/api/logout':
            raw=self.headers.get('Cookie',''); sid=next((x.split('=',1)[1] for x in raw.split('; ') if x.startswith('essence_session=')),None); sessions.pop(sid,None)
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie','essence_session=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax');self.end_headers();self.wfile.write(b'{"ok":true}');return
        if not authed(self):return self.js({'ok':False,'message':'Unauthorized'},401)
        if p.startswith('/api/start/'):
            return self.js(dict(zip(('ok','message'),start_channel(p.split('/')[-1]))))
        if p.startswith('/api/stop/'):
            return self.js(dict(zip(('ok','message'),stop_channel(p.split('/')[-1]))))
        if p=='/api/start-all':
            r=[(c['id'],)+start_channel(c['id']) for c in CFG['channels']]; return self.js({'ok':all(x[1] for x in r),'results':r})
        if p=='/api/stop-all':
            for c in CFG['channels']:stop_channel(c['id'])
            return self.js({'ok':True})
        if p=='/api/cloudflare/provision':
            ok,msg,data=provision_cloudflare();return self.js({'ok':ok,'message':msg,'channels':data})
        if p=='/api/upload':
            data=self.body()
            if data is None:return self.js({'ok':False,'message':'File too large'},413)
            name=os.path.basename(urllib.parse.parse_qs(u.query).get('name',['upload.bin'])[0])
            if not name or name.startswith('.'):return self.js({'ok':False,'message':'Invalid filename'},400)
            target=MEDIA/name; target.write_bytes(data); return self.js({'ok':True,'name':name,'size':len(data)})
        return self.js({'ok':False,'message':'Unknown endpoint'},404)

def cleanup():
    for cid in state['channels']:kill_process(cid)
if __name__=='__main__':
    print(f'Essence Network Online Broadcast v4 on 0.0.0.0:{PORT}')
    try:ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
    except KeyboardInterrupt:cleanup()
