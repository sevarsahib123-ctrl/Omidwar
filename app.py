import os, sqlite3, time, json, hmac, hashlib, base64, secrets
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import requests

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.getenv("DATABASE_PATH", "/app/data/omidwar.db")
os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)
ADMIN_USER=os.getenv("ADMIN_USER","admin")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","")
TOKEN_SECRET=os.getenv("TOKEN_SECRET","")
SMS_ENABLED=os.getenv("SMS_ENABLED","false").lower()=="true"
SMS_URL=os.getenv("SMS_API_URL","https://sms.baharfuture.com/send")
SMS_USER=os.getenv("SMS_USERNAME","")
SMS_PASS=os.getenv("SMS_PASSWORD","")
SMS_FROM=os.getenv("SMS_SENDER_ID","OMIDWAR")

app=FastAPI(title="Omidwar API",version="0.1.0")
app.mount("/static",StaticFiles(directory=BASE+"/static"),name="static")

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with conn() as c:
    c.execute("CREATE TABLE IF NOT EXISTS students(code TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,class_name TEXT NOT NULL DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS grades(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT NOT NULL,subject TEXT NOT NULL,exam TEXT NOT NULL,score REAL NOT NULL,max_score REAL NOT NULL,term TEXT DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS sms_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT,phone TEXT,subject TEXT,exam TEXT,message_id TEXT,status TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

def token_for(user):
    raw=base64.urlsafe_b64encode(json.dumps({"sub":user,"exp":int(time.time())+28800}).encode()).decode().rstrip("=")
    sig=hmac.new(TOKEN_SECRET.encode(),raw.encode(),hashlib.sha256).digest()
    return raw+"."+base64.urlsafe_b64encode(sig).decode().rstrip("=")
def verify_token(t):
    try:
        raw,sig=t.split(".",1); expected=hmac.new(TOKEN_SECRET.encode(),raw.encode(),hashlib.sha256).digest()
        got=base64.urlsafe_b64decode(sig+"="*(-len(sig)%4))
        if not hmac.compare_digest(expected,got): raise ValueError()
        p=json.loads(base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)))
        if p["exp"]<time.time(): raise ValueError()
        return p
    except Exception: raise HTTPException(401,"نشست نامعتبر است؛ دوباره وارد شوید.")
def auth(authorization:Optional[str]=Header(None)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"ابتدا وارد سیستم شوید.")
    return verify_token(authorization[7:])

class Login(BaseModel):
    username:str
    password:str
class Student(BaseModel):
    code:str=Field(min_length=1,max_length=50)
    name:str=Field(min_length=1,max_length=150)
    phone:str=Field(default="",max_length=30)
    class_name:str=Field(default="",max_length=100)
class Grade(BaseModel):
    code:str
    subject:str=Field(min_length=1,max_length=100)
    exam:str=Field(min_length=1,max_length=100)
    score:float=Field(ge=0)
    max_score:float=Field(gt=0)
    term:str=""
class SMSRequest(BaseModel):
    subject:str=""
    exam:str=""
    language:str="fa"
    confirm:bool=False

@app.get("/")
def index(): return FileResponse(BASE+"/static/index.html")
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(BASE+"/manifest.webmanifest", media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker():
    return FileResponse(BASE+"/static/sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})

@app.get("/health")
def health(): return {"ok":True,"sms_enabled":SMS_ENABLED}
@app.post("/api/login")
def login(x:Login):
    if not ADMIN_PASSWORD or not TOKEN_SECRET: raise HTTPException(503,"ADMIN_PASSWORD و TOKEN_SECRET را در تنظیمات سرور تعیین کنید.")
    if not hmac.compare_digest(x.username,ADMIN_USER) or not hmac.compare_digest(x.password,ADMIN_PASSWORD): raise HTTPException(401,"نام کاربری یا رمز عبور نادرست است.")
    return {"access_token":token_for(x.username),"token_type":"bearer"}
@app.get("/api/students")
def students(user=Depends(auth)):
    with conn() as c: rows=c.execute("SELECT * FROM students ORDER BY name").fetchall()
    return [dict(r) for r in rows]
@app.post("/api/students")
def add_student(x:Student,user=Depends(auth)):
    try:
        with conn() as c: c.execute("INSERT INTO students(code,name,phone,class_name) VALUES(?,?,?,?)",(x.code.strip(),x.name.strip(),x.phone.strip(),x.class_name.strip()))
    except sqlite3.IntegrityError: raise HTTPException(409,"شماره محصل تکراری است.")
    return {"saved":True}
@app.get("/api/grades")
def grades(user=Depends(auth)):
    with conn() as c: rows=c.execute("SELECT g.*,s.name,s.phone FROM grades g JOIN students s ON s.code=g.code ORDER BY g.id DESC").fetchall()
    return [dict(r) for r in rows]
@app.post("/api/grades")
def add_grade(x:Grade,user=Depends(auth)):
    if x.score>x.max_score: raise HTTPException(422,"نمره از حداکثر نمره بیشتر است.")
    with conn() as c:
        if not c.execute("SELECT 1 FROM students WHERE code=?",(x.code,)).fetchone(): raise HTTPException(404,"محصل پیدا نشد.")
        c.execute("INSERT INTO grades(code,subject,exam,score,max_score,term) VALUES(?,?,?,?,?,?)",(x.code,x.subject,x.exam,x.score,x.max_score,x.term))
    return {"saved":True}
def norm_phone(p):
    d="".join(ch for ch in p if ch.isdigit())
    if d.startswith("0"): d="93"+d[1:]
    if d.startswith("7") and len(d)==9: d="93"+d
    return d
def roshan(p):
    # Prefixes listed in the selected provider's public docs; verify with provider before use.
    return norm_phone(p).startswith(("9372","9379"))
def message(name,subject,exam,score,maximum,lang):
    if lang=="en": return f"Dear {name}, your {subject} result ({exam}) is {score:g} out of {maximum:g}. Best wishes."
    if lang=="ps": return f"ګرانه {name}! د {subject} د {exam} نمرې: {score:g} له {maximum:g} څخه."
    return f"محصل محترم {name}! نمره شما در مضمون {subject} ({exam})، {score:g} از {maximum:g} می‌باشد. موفق باشید."
def build_preview(x):
    with conn() as c:
        rows=c.execute("""SELECT g.code,s.name,s.phone,g.subject,g.exam,g.score,g.max_score FROM grades g JOIN students s ON s.code=g.code WHERE (?='' OR g.subject=?) AND (?='' OR g.exam=?) ORDER BY g.id DESC""",(x.subject,x.subject,x.exam,x.exam)).fetchall()
    latest={}
    for r in rows: latest.setdefault(r["code"],dict(r))
    out=[]
    for r in latest.values():
        phone=norm_phone(r["phone"])
        out.append({**r,"phone_normalized":phone,"message":message(r["name"],r["subject"],r["exam"],r["score"],r["max_score"],x.language),"ready":bool(phone) and roshan(phone)})
    return out
@app.post("/api/sms/preview")
def preview(x:SMSRequest,user=Depends(auth)):
    out=build_preview(x)
    return {"count":len(out),"ready_count":sum(m["ready"] for m in out),"sms_enabled":SMS_ENABLED,"messages":out}
@app.post("/api/sms/send")
def send(x:SMSRequest,user=Depends(auth)):
    if not x.confirm: raise HTTPException(400,"برای ارسال باید confirm=true باشد.")
    if not SMS_ENABLED: raise HTTPException(503,"ارسال واقعی خاموش است؛ حساب سرویس و Sender ID را آزمایش کنید، سپس SMS_ENABLED=true کنید.")
    if not SMS_USER or not SMS_PASS: raise HTTPException(503,"اعتبارنامه پیامک تنظیم نشده است.")
    targets=[m for m in build_preview(x) if m["ready"]]
    if not targets: raise HTTPException(400,"شماره‌ای با پیش‌شماره روشن و نمره مناسب پیدا نشد.")
    results=[]
    for m in targets:
        payload={"username":SMS_USER,"password":SMS_PASS,"to":m["phone_normalized"],"from":SMS_FROM,"content":m["message"],"dlr":"yes"}
        try:
            r=requests.post(SMS_URL,data=payload,timeout=20); body=r.text[:400]
            ok=r.status_code==200 and not body.lower().startswith("error")
            mid=body.strip().strip('"') if ok else ""
            status="accepted" if ok else "failed"
        except requests.RequestException:
            body="خطای اتصال به سرویس"; mid=""; status="failed"
        with conn() as c:
            c.execute("INSERT INTO sms_logs(code,phone,subject,exam,message_id,status,detail) VALUES(?,?,?,?,?,?,?)",(m["code"],m["phone_normalized"],m["subject"],m["exam"],mid,status,body))
        results.append({"code":m["code"],"status":status,"detail":body})
    return {"submitted":len(results),"accepted":sum(r["status"]=="accepted" for r in results),"failed":sum(r["status"]=="failed" for r in results),"results":results}
@app.get("/api/sms/logs")
def logs(user=Depends(auth)):
    with conn() as c: rows=c.execute("SELECT * FROM sms_logs ORDER BY id DESC LIMIT 1000").fetchall()
    return [dict(r) for r in rows]
