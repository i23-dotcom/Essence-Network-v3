require('dotenv').config();
const db = require('./db');
const { hashPassword } = require('./auth');

if (!db || typeof db.prepare !== 'function') {
  throw new TypeError('Database connection is invalid: db.prepare() is unavailable.');
}
if(!process.env.ADMIN_EMAIL||!process.env.ADMIN_PASSWORD){console.error('Set ADMIN_EMAIL and ADMIN_PASSWORD in .env');process.exit(1)}
const exists=db.prepare('SELECT id FROM users WHERE email=?').get(process.env.ADMIN_EMAIL);
if(exists){console.log('Admin already exists.');process.exit(0)}
db.prepare('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)').run(process.env.ADMIN_EMAIL,hashPassword(process.env.ADMIN_PASSWORD),'admin');
console.log('Admin created:',process.env.ADMIN_EMAIL);
