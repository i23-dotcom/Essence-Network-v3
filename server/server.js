require('dotenv').config();
const express=require('express');const cors=require('cors');const path=require('path');const multer=require('multer');
const db = require('./db');
const { hashPassword, sign, requireAuth } = require('./auth');

if (!db || typeof db.prepare !== 'function') {
  throw new TypeError('Database connection is invalid: db.prepare() is unavailable. Check server/db.js in the deployed commit.');
}
if(!process.env.JWT_SECRET)throw new Error('JWT_SECRET is required');
const app=express();app.use(cors({origin:process.env.CORS_ORIGIN||true}));app.use(express.json({limit:'2mb'}));
const upload=multer({dest:path.join(__dirname,'..','uploads'),limits:{fileSize:25*1024*1024}});
app.use('/uploads',express.static(path.join(__dirname,'..','uploads')));app.use(express.static(path.join(__dirname,'..','public')));
app.get('/api/health',(req,res)=>res.json({ok:true,service:'Essence Network API',version:'3.0.1',time:new Date().toISOString()}));
app.post('/api/auth/login',(req,res)=>{const {email,password}=req.body||{};const u=db.prepare('SELECT * FROM users WHERE email=?').get(email);if(!u||hashPassword(password||'')!==u.password_hash)return res.status(401).json({error:'Invalid email or password'});res.json({token:sign(u),user:{id:u.id,email:u.email,role:u.role}})});
app.get('/api/public',(req,res)=>{const channels=db.prepare('SELECT id,name,description,stream_url AS stream,logo_url AS logo,enabled,sort_order FROM channels WHERE enabled=1 ORDER BY sort_order,id').all();const programmes=db.prepare('SELECT p.*,c.name channel_name FROM programmes p JOIN channels c ON c.id=p.channel_id ORDER BY p.start_time').all();const videos=db.prepare('SELECT * FROM videos WHERE published=1 ORDER BY id DESC').all();const news=db.prepare('SELECT * FROM news WHERE published=1 ORDER BY id DESC').all();res.json({channels,programmes,videos,news})});
const resources={channels:{table:'channels',allowed:['name','description','stream_url','logo_url','enabled','sort_order']},programmes:{table:'programmes',allowed:['channel_id','start_time','end_time','title','description']},videos:{table:'videos',allowed:['title','description','video_url','thumbnail_url','published']},news:{table:'news',allowed:['category','headline','summary','image_url','published']}};
app.use('/api/admin',requireAuth);
for(const [name,cfg] of Object.entries(resources)){
 app.get('/api/admin/'+name,(req,res)=>res.json(db.prepare(`SELECT * FROM ${cfg.table} ORDER BY id DESC`).all()));
 app.post('/api/admin/'+name,(req,res)=>{const body=req.body||{};const keys=cfg.allowed.filter(k=>body[k]!==undefined);if(!keys.length)return res.status(400).json({error:'No fields provided'});const vals=keys.map(k=>body[k]);const sql=`INSERT INTO ${cfg.table} (${keys.join(',')}) VALUES (${keys.map(()=>'?').join(',')})`;const info=db.prepare(sql).run(...vals);res.status(201).json(db.prepare(`SELECT * FROM ${cfg.table} WHERE id=?`).get(info.lastInsertRowid))});
 app.put('/api/admin/'+name+'/:id',(req,res)=>{const body=req.body||{};const keys=cfg.allowed.filter(k=>body[k]!==undefined);if(!keys.length)return res.status(400).json({error:'No fields provided'});const vals=keys.map(k=>body[k]);if(cfg.table==='channels'){keys.push('updated_at');vals.push(new Date().toISOString())}const set=keys.map(k=>`${k}=?`).join(',');const info=db.prepare(`UPDATE ${cfg.table} SET ${set} WHERE id=?`).run(...vals,req.params.id);if(!info.changes)return res.status(404).json({error:'Not found'});res.json(db.prepare(`SELECT * FROM ${cfg.table} WHERE id=?`).get(req.params.id))});
 app.delete('/api/admin/'+name+'/:id',(req,res)=>{const info=db.prepare(`DELETE FROM ${cfg.table} WHERE id=?`).run(req.params.id);if(!info.changes)return res.status(404).json({error:'Not found'});res.json({ok:true})});
}
app.post('/api/admin/upload',upload.single('file'),(req,res)=>{if(!req.file)return res.status(400).json({error:'No file'});res.json({url:'/uploads/'+req.file.filename,originalName:req.file.originalname,size:req.file.size})});
app.get('*',(req,res)=>res.sendFile(path.join(__dirname,'..','public','index.html')));
const port=process.env.PORT||3000;app.listen(port,()=>console.log(`Essence Network V3 running on http://localhost:${port}`));
