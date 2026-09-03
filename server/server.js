require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const db = require('./db');
const { hashPassword, sign, requireAuth } = require('./auth');

if (!db || typeof db.prepare !== 'function') throw new TypeError('Database connection is invalid: db.prepare() is unavailable.');
if (!process.env.JWT_SECRET) throw new Error('JWT_SECRET is required');

function bootstrapAdmin() {
  const email = String(process.env.ADMIN_EMAIL || '').trim().toLowerCase();
  const password = String(process.env.ADMIN_PASSWORD || '');
  if (!email || !password) return console.warn('ADMIN_EMAIL/ADMIN_PASSWORD not set; no administrator was bootstrapped.');
  const existing = db.prepare('SELECT id, role FROM users WHERE email=?').get(email);
  if (existing) {
    if (existing.role !== 'admin') db.prepare('UPDATE users SET role=? WHERE id=?').run('admin', existing.id);
    return console.log(`Admin account ready: ${email}`);
  }
  db.prepare('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)').run(email, hashPassword(password), 'admin');
  console.log(`Admin account created: ${email}`);
}
bootstrapAdmin();

const app = express();
app.use(cors({ origin: process.env.CORS_ORIGIN || true }));
app.use(express.json({ limit: '4mb' }));
const uploadDir = path.join(__dirname, '..', 'uploads');
fs.mkdirSync(uploadDir, { recursive: true });
const upload = multer({ dest: uploadDir, limits: { fileSize: 25 * 1024 * 1024 } });
app.use('/uploads', express.static(uploadDir));
app.use(express.static(path.join(__dirname, '..', 'public')));

app.get('/api/health', (req,res)=>res.json({ok:true,service:'Essence Network API',version:'3.1.0',time:new Date().toISOString()}));

app.post('/api/auth/login',(req,res)=>{
  const email=String(req.body?.email||'').trim().toLowerCase(), password=String(req.body?.password||'');
  if(!email||!password)return res.status(400).json({error:'Email and password are required'});
  const u=db.prepare('SELECT * FROM users WHERE email=?').get(email);
  if(!u||u.role!=='admin'||hashPassword(password)!==u.password_hash)return res.status(401).json({error:'Invalid email or password'});
  res.json({token:sign(u),user:{id:u.id,email:u.email,role:u.role}});
});
app.get('/api/auth/me',requireAuth,(req,res)=>res.json({user:req.user}));

app.get('/api/public',(req,res)=>{
  const channels=db.prepare('SELECT id,name,description,stream_url AS stream,logo_url AS logo,enabled,sort_order FROM channels WHERE enabled=1 ORDER BY sort_order,id').all();
  const programmes=db.prepare('SELECT p.*,c.name channel_name FROM programmes p LEFT JOIN channels c ON c.id=p.channel_id ORDER BY p.start_time').all();
  const videos=db.prepare('SELECT * FROM videos WHERE published=1 ORDER BY id DESC').all();
  const news=db.prepare('SELECT * FROM news WHERE published=1 ORDER BY id DESC').all();
  res.json({channels,programmes,videos,news});
});

const resources={
  channels:{table:'channels',allowed:['name','description','stream_url','logo_url','enabled','sort_order'],required:['name','stream_url']},
  programmes:{table:'programmes',allowed:['channel_id','start_time','end_time','title','description'],required:['channel_id','start_time','end_time','title']},
  videos:{table:'videos',allowed:['title','description','video_url','thumbnail_url','published'],required:['title','video_url']},
  news:{table:'news',allowed:['category','headline','summary','image_url','published'],required:['category','headline']}
};

app.use('/api/admin',requireAuth);
app.get('/api/admin/overview',(req,res)=>{
  const count=t=>db.prepare(`SELECT COUNT(*) c FROM ${t}`).get().c;
  const publishedVideos=db.prepare('SELECT COUNT(*) c FROM videos WHERE published=1').get().c;
  const publishedNews=db.prepare('SELECT COUNT(*) c FROM news WHERE published=1').get().c;
  const enabledChannels=db.prepare('SELECT COUNT(*) c FROM channels WHERE enabled=1').get().c;
  const upcoming=db.prepare("SELECT COUNT(*) c FROM programmes WHERE start_time >= datetime('now')").get().c;
  const recent=db.prepare("SELECT 'channel' type,id,name title,created_at FROM channels UNION ALL SELECT 'video',id,title,created_at FROM videos UNION ALL SELECT 'news',id,headline,created_at FROM news ORDER BY created_at DESC LIMIT 8").all();
  res.json({counts:{channels:count('channels'),programmes:count('programmes'),videos:count('videos'),news:count('news'),users:count('users')},publishedVideos,publishedNews,enabledChannels,upcomingProgrammes:upcoming,recent});
});

for(const [name,cfg] of Object.entries(resources)){
  app.get('/api/admin/'+name,(req,res)=>res.json(db.prepare(`SELECT * FROM ${cfg.table} ORDER BY id DESC`).all()));
  app.post('/api/admin/'+name,(req,res)=>{
    const body=req.body||{};
    for(const k of cfg.required) if(body[k]===undefined||String(body[k]).trim()==='') return res.status(400).json({error:`${k} is required`});
    const keys=cfg.allowed.filter(k=>body[k]!==undefined); const vals=keys.map(k=>body[k]);
    const info=db.prepare(`INSERT INTO ${cfg.table} (${keys.join(',')}) VALUES (${keys.map(()=>'?').join(',')})`).run(...vals);
    res.status(201).json(db.prepare(`SELECT * FROM ${cfg.table} WHERE id=?`).get(info.lastInsertRowid));
  });
  app.put('/api/admin/'+name+'/:id',(req,res)=>{
    const body=req.body||{}; const keys=cfg.allowed.filter(k=>body[k]!==undefined); if(!keys.length)return res.status(400).json({error:'No fields provided'});
    const vals=keys.map(k=>body[k]);
    if(cfg.table==='channels'){keys.push('updated_at');vals.push(new Date().toISOString());}
    const info=db.prepare(`UPDATE ${cfg.table} SET ${keys.map(k=>`${k}=?`).join(',')} WHERE id=?`).run(...vals,req.params.id);
    if(!info.changes)return res.status(404).json({error:'Not found'});
    res.json(db.prepare(`SELECT * FROM ${cfg.table} WHERE id=?`).get(req.params.id));
  });
  app.delete('/api/admin/'+name+'/:id',(req,res)=>{
    const info=db.prepare(`DELETE FROM ${cfg.table} WHERE id=?`).run(req.params.id);
    if(!info.changes)return res.status(404).json({error:'Not found'}); res.json({ok:true});
  });
}

app.get('/api/admin/settings',(req,res)=>res.json(db.prepare('SELECT key,value FROM settings ORDER BY key').all()));
app.put('/api/admin/settings',(req,res)=>{
  const entries=req.body?.settings;
  if(!entries||typeof entries!=='object')return res.status(400).json({error:'settings object required'});
  const stmt=db.prepare('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value');
  const tx=db.transaction(obj=>Object.entries(obj).forEach(([k,v])=>stmt.run(String(k),String(v??'')))); tx(entries);
  res.json({ok:true});
});

app.post('/api/admin/account/password',(req,res)=>{
  const current=String(req.body?.currentPassword||''), next=String(req.body?.newPassword||'');
  if(next.length<8)return res.status(400).json({error:'New password must be at least 8 characters'});
  const u=db.prepare('SELECT * FROM users WHERE id=?').get(req.user.id);
  if(!u||hashPassword(current)!==u.password_hash)return res.status(401).json({error:'Current password is incorrect'});
  db.prepare('UPDATE users SET password_hash=? WHERE id=?').run(hashPassword(next),u.id);
  res.json({ok:true});
});

app.post('/api/admin/upload',upload.single('file'),(req,res)=>{
  if(!req.file)return res.status(400).json({error:'No file'});
  res.json({url:'/uploads/'+req.file.filename,originalName:req.file.originalname,size:req.file.size,mime:req.file.mimetype});
});

function parseM3U(text){
  const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean), out=[];
  let meta=null;
  for(const line of lines){
    if(line.startsWith('#EXTINF:')){
      const comma=line.indexOf(','); const attrs=line.slice(8,comma<0?undefined:comma); const name=(comma<0?'Channel':line.slice(comma+1)).trim();
      const get=a=>{const m=attrs.match(new RegExp(a+'="([^"]*)"','i'));return m?m[1]:''};
      meta={name,logo_url:get('tvg-logo'),group:get('group-title'),stream_url:null};
    }else if(!line.startsWith('#')&&meta){meta.stream_url=line;out.push(meta);meta=null;}
  }
  return out;
}
app.post('/api/admin/import/m3u',upload.single('file'),(req,res)=>{
  if(!req.file)return res.status(400).json({error:'Choose an M3U/M3U8 file'});
  try{
    const text=fs.readFileSync(req.file.path,'utf8'); const rows=parseM3U(text); if(!rows.length)return res.status(400).json({error:'No playable M3U entries found'});
    const insert=db.prepare('INSERT INTO channels(name,description,stream_url,logo_url,enabled,sort_order) VALUES(?,?,?,?,1,?)');
    const tx=db.transaction(items=>items.forEach((x,i)=>insert.run(x.name,x.group||'',x.stream_url,x.logo_url||'',i)));
    tx(rows); res.json({ok:true,imported:rows.length});
  }catch(e){res.status(400).json({error:'Unable to read M3U file'});}finally{try{fs.unlinkSync(req.file.path)}catch(e){}}
});

app.use((err,req,res,next)=>{console.error(err);if(res.headersSent)return next(err);res.status(500).json({error:'Server error'});});
app.get('*',(req,res)=>res.sendFile(path.join(__dirname,'..','public','index.html')));
const port=process.env.PORT||3000; app.listen(port,()=>console.log(`Essence Network V3 running on port ${port}`));
