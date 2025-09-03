
from http.server import SimpleHTTPRequestHandler, HTTPServer
import json
import os
import urllib.parse as urlparse
from datetime import datetime, timedelta
import hashlib, hmac, secrets

from .db import init_db, execute, query_one, query_all, connect
from .tests_engine import score_aptitude, score_personality
from .logic import pick_personality, recommend_courses, filter_colleges, COURSE_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')

# ---------- Utilities ----------

def json_response(handler, status=200, data=None):
    payload = json.dumps(data or {}, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(payload)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(payload)


def parse_body(handler):
    length = int(handler.headers.get('Content-Length', '0'))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def pbkdf2_hash(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return dk.hex()


def make_token() -> str:
    return secrets.token_hex(32)


def require_auth(handler):
    token = handler.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    row = query_one('SELECT user_id FROM sessions WHERE token=? AND expires_at>datetime("now")', (token,))
    return row['user_id'] if row else None

# ---------- HTTP Handler ----------

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve frontend files as default
        webroot = FRONTEND_DIR
        if path.startswith('/api/'):
            return super().translate_path(path)
        # Map '/' to index.html
        path = path.split('?',1)[0]
        if path == '/' or path == '':
            return os.path.join(webroot, 'index.html')
        return os.path.join(webroot, path.lstrip('/'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/signup':
            data = parse_body(self)
            email = (data.get('email') or '').strip().lower()
            password = data.get('password') or ''
            if not email or not password:
                return json_response(self, 400, {'error':'email and password required'})
            salt = secrets.token_bytes(16)
            pwd = pbkdf2_hash(password, salt)
            try:
                uid = execute('INSERT INTO users(email,password_hash,salt) VALUES(?,?,?)', (email, pwd, salt.hex()))
            except Exception:
                return json_response(self, 400, {'error':'email already exists'})
            return json_response(self, 200, {'ok': True})

        if self.path == '/api/login':
            data = parse_body(self)
            email = (data.get('email') or '').strip().lower()
            password = data.get('password') or ''
            row = query_one('SELECT id,password_hash,salt FROM users WHERE email=?', (email,))
            if not row:
                return json_response(self, 401, {'error':'invalid credentials'})
            pwd = pbkdf2_hash(password, bytes.fromhex(row['salt']))
            if hmac.compare_digest(pwd, row['password_hash']):
                token = make_token()
                expires = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                execute('INSERT INTO sessions(user_id, token, expires_at) VALUES(?,?,?)', (row['id'], token, expires))
                return json_response(self, 200, {'token': token})
            return json_response(self, 401, {'error':'invalid credentials'})

        if self.path == '/api/form':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error':'unauthorized'})
            data = parse_body(self)
            execute('INSERT INTO profiles(user_id, highest_qualification, stream, board_marks, city, country, abroad, budget, dream_course) VALUES(?,?,?,?,?,?,?,?,?)', (
                uid,
                data.get('highest_qualification',''),
                data.get('stream',''),
                float(data.get('board_marks') or 0),
                data.get('city',''),
                data.get('country',''),
                1 if data.get('abroad') else 0,
                int(data.get('budget') or 0),
                data.get('dream_course') or None
            ))
            return json_response(self, 200, {'ok': True})

        if self.path == '/api/test/start':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error':'unauthorized'})
            data = parse_body(self)
            kind = data.get('kind')
            if kind not in ('aptitude','personality'):
                return json_response(self, 400, {'error':'invalid kind'})
            # Select 20 questions of that kind
            rows = query_all('SELECT id,question,options_json FROM test_questions WHERE kind=? ORDER BY id LIMIT 20', (kind,))
            # Create session row
            sid = execute('INSERT INTO test_sessions(user_id,kind,total_marks) VALUES(?,?,?)', (uid, kind, len(rows)))
            for r in rows:
                r['options'] = json.loads(r.pop('options_json'))
            return json_response(self, 200, {'session_id': sid, 'questions': rows})

        if self.path == '/api/test/submit':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error':'unauthorized'})
            data = parse_body(self)
            sid = int(data.get('session_id')) # pyright: ignore[reportArgumentType]
            answers = data.get('answers') or {}
            row = query_one('SELECT kind,total_marks FROM test_sessions WHERE id=? AND user_id=?', (sid, uid))
            if not row:
                return json_response(self, 400, {'error':'invalid session'})
            kind = row['kind']
            if kind == 'aptitude':
                score = score_aptitude({int(k): v for k,v in answers.items()})
                execute('UPDATE test_sessions SET score=?, result_json=? WHERE id=?', (score, json.dumps({"score":score}), sid))
                return json_response(self, 200, {'score': score, 'out_of': row['total_marks']})
            else:
                traits = score_personality({int(k): v for k,v in answers.items()})
                execute('UPDATE test_sessions SET score=?, result_json=? WHERE id=?', (0, json.dumps(traits), sid))
                return json_response(self, 200, {'traits': traits})
        
        if self.path == '/api/recommendations':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error': 'unauthorized'})

        # Get latest profile
            profile = query_one(
                'SELECT * FROM profiles WHERE user_id=? ORDER BY id DESC LIMIT 1',
                (uid,)
            )
            if not profile:
                return json_response(self, 400, {'error': 'please submit form first'})

        # ------------------ Get latest tests ------------------
            apt = query_one(
                'SELECT * FROM test_sessions WHERE user_id=? AND kind="aptitude" ORDER BY id DESC LIMIT 1',
                (uid,)
            )
            per = query_one(
                'SELECT * FROM test_sessions WHERE user_id=? AND kind="personality" ORDER BY id DESC LIMIT 1',
                (uid,)
        )

        # Safe defaults
            aptitude20 = 0
            personality_type = 'Analytical'

            # ---- Parse aptitude result safely ----
            if apt:
                try:
                    total = int(apt.get('total_marks') or 20)
                except Exception:
                    total = 20

                apt_score_raw = 0
                apt_result_json = apt.get('result_json')

                if apt_result_json:
                    try:
                        parsed = json.loads(apt_result_json)
                        if isinstance(parsed, dict):
                            apt_score_raw = parsed.get('score', 0)
                        elif isinstance(parsed, (int, float)):
                            apt_score_raw = parsed
                    except Exception:
                        apt_score_raw = 0

                try:
                    apt_score_num = float(apt_score_raw)
                except Exception:
                    apt_score_num = 0.0

                try:
                    aptitude20 = int(round((apt_score_num / max(1, total)) * 20))
                except Exception:
                    aptitude20 = 0

                    # ---- Parse personality result safely ----
            if per:
                traits = {}
                per_result_json = per.get('result_json')
                if per_result_json:
                    try:
                        parsed_per = json.loads(per_result_json)
                        if isinstance(parsed_per, dict):
                            traits = parsed_per
                    except Exception:
                        traits = {}
                personality_type = pick_personality(traits)

         # ------------------ Build recommendations ------------------
            courses_raw = recommend_courses(
                profile.get('stream'), # pyright: ignore[reportArgumentType]
                profile.get('board_marks', 0),
                aptitude20,
                personality_type,
                profile.get('dream_course')
            )

            # Format for frontend
            formatted = []
            for code, fit in courses_raw:
                formatted.append({
                    "code": code,
                    "name": COURSE_LABELS.get(code, code),
                    "fit": fit
                })

            return json_response(self, 200, {
                'aptitude20': aptitude20,
                'personality': personality_type,
                'courses': formatted
            })

            


        if self.path == '/api/resources':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error':'unauthorized'})
            data = parse_body(self)
            code = data.get('course_code')
            rows = query_all('SELECT title,url FROM resources WHERE course_code=? AND is_free=1', (code,))
            return json_response(self, 200, {'resources': rows})

        if self.path == '/api/colleges':
            uid = require_auth(self)
            if not uid:
                return json_response(self, 401, {'error':'unauthorized'})
            data = parse_body(self)
            code = data.get('course_code')
            city = data.get('city','')
            country = data.get('country','')
            abroad = bool(data.get('abroad'))
            budget = int(data.get('budget') or 0)
            include_private = bool(data.get('include_private', True))
            include_government = bool(data.get('include_government', True))
            allc = query_all('SELECT * FROM colleges')
            filt = filter_colleges(allc, code, city, country, abroad, budget, include_private, include_government) # pyright: ignore[reportArgumentType]
            for r in filt:
                r.pop('city_score', None)
            return json_response(self, 200, {'colleges': filt})

        return json_response(self, 404, {'error':'not found'})

    def do_GET(self):
        if self.path.startswith('/api/college?id='):
            qs = urlparse.urlparse(self.path).query
            q = urlparse.parse_qs(qs)
            cid = int(q.get('id',['0'])[0])
            row = query_one('SELECT * FROM colleges WHERE id=?', (cid,))
            if not row:
                return json_response(self, 404, {'error':'not found'})
            return json_response(self, 200, {'college': row})
        # Static files (frontend)
        return super().do_GET()


def start_server(host='127.0.0.1', port=8000):
    init_db()
    httpd = HTTPServer((host, port), Handler)
    print(f"Server running at http://{host}:{port}")
    httpd.serve_forever()

if __name__ == '__main__':
    start_server()