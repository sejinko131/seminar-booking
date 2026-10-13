"""Seminar booking: Python stdlib HTTP server and transactional SQLite storage."""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))
DAYS = ['월','화','수','목','금','토','일']


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def text(data, key, limit=100):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > limit:
        raise ApiError(400, '입력 길이와 형식을 확인해주세요.')
    return value.strip()


def password_hash(value, salt):
    return hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def person(data):
    if not isinstance(data, dict):
        raise ApiError(400, '이용자 정보를 확인해주세요.')
    name, sid = text(data, 'name', 40), text(data, 'studentId', 8)
    if not name or any(c in name for c in ',()') or not re.fullmatch(r'[0-9]{8}', sid):
        raise ApiError(400, '이름과 숫자 8자리 학번을 입력해주세요.')
    return dict(name=name, studentId=sid)


class Store:
    def __init__(self, path, clock=None):
        self.path = str(path)
        self.clock = clock or (lambda: datetime.now(KST))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript("""
                CREATE TABLE IF NOT EXISTS bookings(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                    name TEXT NOT NULL, student_id TEXT NOT NULL, attendees TEXT NOT NULL,
                    group_name TEXT NOT NULL, contact TEXT NOT NULL, purpose TEXT NOT NULL,
                    period_start TEXT NOT NULL, period_end TEXT NOT NULL, weekdays TEXT NOT NULL,
                    start_time TEXT NOT NULL, end_time TEXT NOT NULL,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS occurrences(
                    booking_id TEXT NOT NULL REFERENCES bookings(id), starts TEXT NOT NULL,
                    ends TEXT NOT NULL, PRIMARY KEY(booking_id, starts));
                CREATE INDEX IF NOT EXISTS occurrence_times ON occurrences(starts, ends);
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY, booking_id TEXT NOT NULL,
                    action TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL);
                INSERT OR IGNORE INTO settings VALUES(1,1);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        return db

    def candidate(self, data, kind, editing=False):
        try:
            start_date = datetime.strptime(text(data, 'periodStart', 10), '%Y-%m-%d').date()
            end_date = datetime.strptime(text(data, 'periodEnd', 10), '%Y-%m-%d').date()
            start = datetime.strptime(text(data, 'startTime', 5), '%H:%M').time()
            end = datetime.strptime(text(data, 'endTime', 5), '%H:%M').time()
        except ValueError:
            raise ApiError(400, '날짜와 시간을 확인해주세요.')
        today = self.clock().date()
        if start.minute % 10 or end.minute % 10:
            raise ApiError(400, '시간은 10분 단위로 입력해주세요.')
        minutes = ((end.hour*60+end.minute)-(start.hour*60+start.minute)) % 1440
        if not 10 <= minutes <= 180:
            raise ApiError(400, '이용 시간은 10분 이상 3시간 이하입니다.')
        rep = person(data)
        if kind == 'general':
            if start_date != end_date or not today <= start_date <= today+timedelta(weeks=3):
                raise ApiError(400, '일반예약은 오늘부터 3주 이내로 신청해주세요.')
            attendees = data.get('attendees')
            if not isinstance(attendees, list) or not 2 <= len(attendees) <= 30:
                raise ApiError(400, '서로 다른 이용자를 2~30명 입력해주세요.')
            attendees = [person(p) for p in attendees]
            if attendees[0] != rep or len({p['studentId'] for p in attendees}) != len(attendees):
                raise ApiError(400, '첫 번째 이용자는 대표자여야 하며 학번은 중복할 수 없습니다.')
            days = [DAYS[start_date.weekday()]]
        elif kind == 'regular':
            if start_date > end_date or (start_date.year,start_date.month) != (today.year,today.month) or (end_date.year,end_date.month) != (today.year,today.month):
                raise ApiError(400, '정기대관은 이번 달 안에서 신청해주세요.')
            days = data.get('weekdays')
            if not isinstance(days,list) or not days or any(d not in DAYS for d in days) or len(set(days)) != len(days):
                raise ApiError(400, '이용 요일을 선택해주세요.')
            attendees = [rep]
            if not text(data,'groupName',80) or not text(data,'contact',30) or not text(data,'purpose',1000):
                raise ApiError(400, '단체명·연락처·사용목적을 입력해주세요.')
        else:
            raise ApiError(400, '예약 유형을 확인해주세요.')
        occurrences = []
        cur = start_date
        while cur <= end_date:
            if DAYS[cur.weekday()] in days:
                s = datetime.combine(cur,start,KST)
                e = datetime.combine(cur,end,KST)
                if e <= s:
                    e += timedelta(days=1)
                if e > self.clock():
                    occurrences.append((s.isoformat(), e.isoformat()))
            cur += timedelta(days=1)
        if not occurrences:
            raise ApiError(400, '현재 또는 향후 이용 회차가 없습니다.')
        return dict(kind=kind, name=rep['name'], student_id=rep['studentId'],
                    attendees=json.dumps(attendees,ensure_ascii=False),
                    group_name=text(data,'groupName',80), contact=text(data,'contact',30),
                    purpose=text(data,'purpose',1000), period_start=start_date.isoformat(),
                    period_end=end_date.isoformat(), weekdays=json.dumps(days,ensure_ascii=False),
                    start_time=start.strftime('%H:%M'), end_time=end.strftime('%H:%M'),
                    occurrences=occurrences)

    def check(self, db, candidate, exclude=''):
        for s,e in candidate['occurrences']:
            hit = db.execute("""SELECT 1 FROM occurrences o JOIN bookings b ON b.id=o.booking_id
                WHERE b.status='approved' AND b.id!=? AND o.starts<? AND o.ends>? LIMIT 1""",
                (exclude,e,s)).fetchone()
            if hit:
                raise ApiError(409, '이미 확정된 예약과 시간이 겹칩니다.')
        if candidate['kind'] != 'general':
            return
        people = {p['studentId'] for p in json.loads(candidate['attendees'])}
        totals = {}
        existing = db.execute("""SELECT o.starts,o.ends,b.attendees FROM occurrences o
            JOIN bookings b ON b.id=o.booking_id
            WHERE b.status='approved' AND b.kind='general' AND b.id!=?""", (exclude,)).fetchall()
        entries = [(s,e,people) for s,e in candidate['occurrences']]
        entries += [(r['starts'],r['ends'],{p['studentId'] for p in json.loads(r['attendees'])}&people) for r in existing]
        relevant_dates=set()
        for ss,ee in candidate['occurrences']:
            cur=datetime.fromisoformat(ss)
            end=datetime.fromisoformat(ee)
            while cur<end:
                relevant_dates.add(cur.date())
                cur=datetime.combine(cur.date()+timedelta(days=1),datetime.min.time(),KST)
        for ss,ee,ids in entries:
            s,e = datetime.fromisoformat(ss),datetime.fromisoformat(ee)
            while s < e:
                midnight = datetime.combine(s.date()+timedelta(days=1),datetime.min.time(),KST)
                boundary = min(e,midnight)
                minutes = int((boundary-s).total_seconds()/60)
                for sid in ids if s.date() in relevant_dates else ():
                    key = (sid,s.date())
                    totals[key] = totals.get(key,0)+minutes
                    if totals[key] > 180:
                        raise ApiError(409, '이용자별 1일 총 3시간 한도를 초과합니다.')
                s = boundary

    def record_audit(self, db, bid, action):
        db.execute('INSERT INTO audit(booking_id,action,created_at) VALUES(?,?,?)',
                   (bid,action,self.clock().isoformat()))

    def create(self, data):
        candidate = self.candidate(data,text(data,'kind',10))
        password = text(data,'password',128)
        if len(password) < 8:
            raise ApiError(400, '예약 관리 비밀번호를 8자 이상 입력해주세요.')
        salt = secrets.token_hex(16)
        hashed = password_hash(password,salt)
        bid = secrets.token_urlsafe(18)
        status = 'approved' if candidate['kind']=='general' else 'pending'
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT enabled FROM settings WHERE id=1').fetchone()[0]:
                raise ApiError(403,'현재 신규 예약 접수가 중지되어 있습니다.')
            # Pending requests do not block others; approval rechecks all conflicts.
            self.check(db,candidate)
            fields = [k for k in candidate if k != 'occurrences']
            cols = ','.join(fields)
            db.execute(f'INSERT INTO bookings(id,status,{cols},salt,password_hash,created_at) VALUES({",".join("?" for _ in range(len(fields)+5))})',
                       [bid,status]+[candidate[k] for k in fields]+[salt,hashed,self.clock().isoformat()])
            db.executemany('INSERT INTO occurrences VALUES(?,?,?)',[(bid,s,e) for s,e in candidate['occurrences']])
            self.record_audit(db,bid,'created')
            db.commit()
            return dict(ok=True,id=bid,status=status)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def authenticate(self, data):
        bid = text(data,'id',100)
        with self.connect() as db:
            row = db.execute('SELECT * FROM bookings WHERE id=?',(bid,)).fetchone()
        # Constant cost also for missing IDs.
        salt = row['salt'] if row else '0'*32
        actual = password_hash(text(data,'password',128),salt)
        if not row or not hmac.compare_digest(actual,row['password_hash']):
            raise ApiError(401,'예약번호 또는 관리 비밀번호가 일치하지 않습니다.')
        return bid

    def private(self, row):
        item = dict(row)
        for key in ('salt','password_hash'):
            item.pop(key,None)
        item['attendees'] = json.loads(item['attendees'])
        item['weekdays'] = json.loads(item['weekdays'])
        return item

    def get(self,bid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM bookings WHERE id=?',(bid,)).fetchone()
            if not row:
                raise ApiError(404,'예약을 찾을 수 없습니다.')
            return self.private(row)

    def edit(self,bid,data,admin=False):
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM bookings WHERE id=?',(bid,)).fetchone()
            if not old:
                raise ApiError(404,'예약을 찾을 수 없습니다.')
            if data.get('version') != old['version']:
                raise ApiError(409,'예약이 변경되었습니다. 다시 조회해주세요.')
            if old['status'] in ('cancelled','rejected'):
                raise ApiError(409,'종료된 신청은 변경할 수 없습니다.')
            last=db.execute('SELECT MAX(ends) FROM occurrences WHERE booking_id=?',(bid,)).fetchone()[0]
            if not last or datetime.fromisoformat(last)<=self.clock():
                raise ApiError(409,'이용이 종료된 예약은 변경할 수 없습니다.')
            action=text(data,'action',10)
            if action=='cancel':
                db.execute("UPDATE bookings SET status='cancelled',version=version+1 WHERE id=?",(bid,))
            elif action in ('approve','reject'):
                if not admin or old['kind']!='regular':
                    raise ApiError(403,'관리자만 정기대관을 심사할 수 있습니다.')
                if old['status']!='pending':
                    raise ApiError(409,'대기 중인 신청만 심사할 수 있습니다.')
                if action=='approve':
                    candidate=dict(old)
                    candidate['occurrences']=[(r['starts'],r['ends']) for r in db.execute('SELECT * FROM occurrences WHERE booking_id=? AND ends>?',(bid,self.clock().isoformat()))]
                    self.check(db,candidate,bid)
                db.execute('UPDATE bookings SET status=?,version=version+1 WHERE id=?',
                           ('approved' if action=='approve' else 'rejected',bid))
            elif action=='edit':
                candidate=self.candidate(data,old['kind'],True)
                if candidate['name']!=old['name'] or candidate['student_id']!=old['student_id'] or candidate['attendees']!=old['attendees']:
                    raise ApiError(400,'대표자와 이용자 명단은 변경할 수 없습니다.')
                self.check(db,candidate,bid)
                status='pending' if old['kind']=='regular' else 'approved'
                fields=[k for k in candidate if k!='occurrences']
                db.execute('UPDATE bookings SET '+','.join(k+'=?' for k in fields)+',status=?,version=version+1 WHERE id=?',
                           [candidate[k] for k in fields]+[status,bid])
                db.execute('DELETE FROM occurrences WHERE booking_id=?',(bid,))
                db.executemany('INSERT INTO occurrences VALUES(?,?,?)',[(bid,s,e) for s,e in candidate['occurrences']])
            else:
                raise ApiError(400,'변경 작업을 확인해주세요.')
            self.record_audit(db,bid,action)
            db.commit()
            return self.get(bid)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def public(self):
        with self.connect() as db:
            rows=db.execute("""SELECT b.kind,b.name,b.group_name,o.starts,o.ends FROM occurrences o
                JOIN bookings b ON b.id=o.booking_id WHERE b.status='approved' AND o.ends>?
                ORDER BY o.starts""",(self.clock().isoformat(),)).fetchall()
            enabled=bool(db.execute('SELECT enabled FROM settings WHERE id=1').fetchone()[0])
            return dict(enabled=enabled,updatedAt=self.clock().isoformat(),
                        events=[dict(kind=r['kind'],label=r['group_name'] if r['kind']=='regular' else r['name'][:1]+'**',
                                     starts=r['starts'],ends=r['ends']) for r in rows])

    def admin_rows(self):
        with self.connect() as db:
            return [self.private(r) for r in db.execute('SELECT * FROM bookings ORDER BY created_at DESC')]


class State:
    def __init__(self,store,admin_password=None):
        self.store=store
        self.sessions={}
        self.rates={}
        self.lock=threading.Lock()
        self.admin_salt=secrets.token_hex(16)
        password=admin_password if admin_password is not None else os.environ.get('SEMINAR_ADMIN_PASSWORD','')
        self.admin_hash=password_hash(password,self.admin_salt) if len(password)>=12 else None
        self.admin_id=os.environ.get('SEMINAR_ADMIN_ID','admin')

    def rate(self,ip):
        with self.lock:
            now=time.monotonic()
            self.rates={k:v for k,v in self.rates.items() if now-v[0]<300}
            started,count=self.rates.get(ip,(now,0))
            if count>=20:
                raise ApiError(429,'요청이 너무 많습니다. 잠시 후 다시 시도해주세요.')
            self.rates[ip]=(started,count+1)

    def login(self,data):
        if text(data,'role',10)=='admin':
            hashed=password_hash(text(data,'password',128),self.admin_salt)
            if self.admin_hash is None or text(data,'username',40)!=self.admin_id or not hmac.compare_digest(hashed,self.admin_hash):
                raise ApiError(401,'관리자 로그인 정보를 확인해주세요.')
            role,bid='admin',''
        else:
            role,bid='booking',self.store.authenticate(data)
        token=secrets.token_urlsafe(32)
        with self.lock:
            self.sessions={k:v for k,v in self.sessions.items() if v[2]>time.time()}
            self.sessions[token]=(role,bid,time.time()+1800)
        return token,dict(role=role,booking=self.store.get(bid) if bid else None)

    def session(self,token,admin=False):
        with self.lock:
            entry=self.sessions.get(token)
        if not entry or entry[2]<=time.time() or (admin and entry[0]!='admin'):
            raise ApiError(401,'로그인이 필요합니다.')
        return entry


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass
    def setup(self):
        self.request.settimeout(15)
        super().setup()
    def token(self):
        c=SimpleCookie()
        try: c.load(self.headers.get('Cookie',''))
        except Exception: return ''
        return c['seminar_session'].value if 'seminar_session' in c else ''
    def send(self,body,status=200,mime='application/json; charset=utf-8',token=None):
        payload=json.dumps(body,ensure_ascii=False).encode() if isinstance(body,dict) else body
        self.send_response(status)
        for k,v in {'Content-Type':mime,'Content-Length':str(len(payload)),'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                    'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}.items():
            self.send_header(k,v)
        if token is not None:
            secure='; Secure' if self.server.origin.startswith('https://') else ''
            self.send_header('Set-Cookie',f'seminar_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={1800 if token else 0}{secure}')
        self.end_headers()
        self.wfile.write(payload)
    def host(self):
        if self.headers.get('Host')!=urlsplit(self.server.origin).netloc:
            raise ApiError(403,'접속 주소를 확인해주세요.')
    def do_GET(self):
        try:
            self.host()
            path=urlsplit(self.path).path
            state=self.server.state
            if path=='/api/status':
                self.send(state.store.public())
            elif path=='/api/me':
                role,bid,_=state.session(self.token())
                self.send(dict(role=role,booking=state.store.get(bid) if bid else None))
            elif path=='/api/admin':
                state.session(self.token(),True)
                self.send(dict(bookings=state.store.admin_rows()))
            elif path in ('/','/index.html','/app.js','/style.css'):
                name='index.html' if path=='/' else path[1:]
                mime={'html':'text/html','js':'application/javascript','css':'text/css'}[name.split('.')[-1]]
                self.send((ROOT/'public'/name).read_bytes(),mime=mime+'; charset=utf-8')
            else:
                raise ApiError(404,'페이지를 찾을 수 없습니다.')
        except ApiError as e: self.send(dict(error=e.message),e.status)
        except (sqlite3.Error,OSError): self.send(dict(error='자료를 불러올 수 없습니다.'),503)
    def do_POST(self):
        self.close_connection=True
        try:
            self.host()
            if self.headers.get('Origin')!=self.server.origin:
                raise ApiError(403,'요청 출처를 확인할 수 없습니다.')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                raise ApiError(415,'JSON 요청이 필요합니다.')
            try: length=int(self.headers.get('Content-Length','0'))
            except ValueError: raise ApiError(400,'잘못된 요청입니다.')
            if not 0<length<=16384: raise ApiError(413,'요청 크기를 확인해주세요.')
            try: data=json.loads(self.rfile.read(length))
            except (ValueError,UnicodeError): raise ApiError(400,'잘못된 요청입니다.')
            if not isinstance(data,dict): raise ApiError(400,'잘못된 요청입니다.')
            path=urlsplit(self.path).path
            state=self.server.state
            state.rate(self.client_address[0])
            if path=='/api/book':
                self.send(state.store.create(data))
            elif path=='/api/login':
                token,response=state.login(data)
                self.send(response,token=token)
            elif path=='/api/logout':
                with state.lock: state.sessions.pop(self.token(),None)
                self.send(dict(ok=True),token='')
            elif path=='/api/edit':
                role,bid,_=state.session(self.token())
                if role!='booking': raise ApiError(403,'예약 관리 로그인이 필요합니다.')
                self.send(dict(booking=state.store.edit(bid,data)))
            elif path=='/api/admin/action':
                state.session(self.token(),True)
                self.send(dict(booking=state.store.edit(text(data,'id',100),data,True)))
            elif path=='/api/admin/settings':
                state.session(self.token(),True)
                if not isinstance(data.get('enabled'),bool): raise ApiError(400,'접수 설정을 확인해주세요.')
                with state.store.connect() as db:
                    db.execute('UPDATE settings SET enabled=? WHERE id=1',(int(data['enabled']),))
                self.send(dict(ok=True))
            else: raise ApiError(404,'잘못된 요청입니다.')
        except ApiError as e: self.send(dict(error=e.message),e.status)
        except sqlite3.Error: self.send(dict(error='기록을 저장할 수 없습니다. 다시 시도해주세요.'),503)


def make_server(port=8769,db_path=None,origin=None,admin_password=None):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.origin=origin or f'http://127.0.0.1:{server.server_port}'
    server.state=State(Store(db_path or ROOT/'private-data'/'seminar.sqlite'),admin_password)
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8769)
    parser.add_argument('--db',default=str(ROOT/'private-data'/'seminar.sqlite'))
    parser.add_argument('--origin',default=os.environ.get('SEMINAR_ORIGIN'))
    args=parser.parse_args()
    server=make_server(args.port,args.db,args.origin)
    print(f'Seminar booking: {server.origin}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
