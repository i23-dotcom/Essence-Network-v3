const jwt=require('jsonwebtoken');
const bcrypt=require('crypto');
function hashPassword(p){return bcrypt.createHash('sha256').update(p).digest('hex')}
function sign(user){return jwt.sign({id:user.id,email:user.email,role:user.role},process.env.JWT_SECRET,{expiresIn:'12h'})}
function requireAuth(req,res,next){const h=req.headers.authorization||'';if(!h.startsWith('Bearer '))return res.status(401).json({error:'Authentication required'});try{req.user=jwt.verify(h.slice(7),process.env.JWT_SECRET);next()}catch(e){return res.status(401).json({error:'Invalid or expired token'})}}
module.exports={hashPassword,sign,requireAuth};
