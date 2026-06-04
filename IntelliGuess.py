"""
Number Quest v2 — Flask Web Application
Features: Auth, Difficulty Levels, Live Timer, Leaderboard
Run:  python number_guessing_web.py
Open: http://localhost:5000
Default login: admin / 1234
"""

import os
import random
import time
import psycopg2
import psycopg2.extras
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "numquest-secret-v2-2024")


MAX_ATTEMPTS = 7

# ── PostgreSQL config ─────────────────────────────────────────────────
# Local fallback — only used if DATABASE_URL env var is not set
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "numberquest",
    "user":     "postgres",
    "password": os.environ.get("DB_PASSWORD", "your_db_password"),
}
# ─────────────────────────────────────────────────────────────────────

def get_db():
    """Open and return a new DB connection."""
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        # Render gives postgres:// — psycopg2 needs postgresql://
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        print(f"[DB] Connecting via DATABASE_URL...")
        return psycopg2.connect(db_url, sslmode="require")
    print("[DB] Connecting via local DB_CONFIG...")
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Create tables and seed admin user on first run."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            username   VARCHAR(50)  UNIQUE NOT NULL,
            password   VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id         SERIAL PRIMARY KEY,
            username   VARCHAR(50) NOT NULL,
            difficulty VARCHAR(10) NOT NULL,
            guesses    INTEGER     NOT NULL,
            time_secs  FLOAT       NOT NULL,
            played_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, difficulty)
        );
    """)
    cur.execute("""
        INSERT INTO users (username, password)
        VALUES ('admin', '1234')
        ON CONFLICT (username) DO NOTHING;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables ready.")

DIFFICULTIES = {
    "easy":   {"label": "Easy",   "min": 1,   "max": 50,  "emoji": "🟢"},
    "medium": {"label": "Medium", "min": 1,   "max": 100, "emoji": "🟡"},
    "hard":   {"label": "Hard",   "min": 1,   "max": 200, "emoji": "🔴"},
}

# ───────────────────────────── BASE SHELL ─────────────────────────────

BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>NumberQuest</title>

<style>:root{--font-mono:'Courier New',Courier,monospace;--font-display:'Arial Black',Impact,sans-serif;--bg:#080810;--panel:#10101c;--border:#252535;--acc:#f0c040;--red:#e05a5a;--grn:#50e0a0;--blue:#60a0f0;--text:#e8e8f0;--muted:#55556a;--glow:0 0 28px rgba(240,192,64,.4);}*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--text);font-family:var(--font-mono);min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:28px 20px;}body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;background-image:linear-gradient(rgba(240,192,64,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(240,192,64,.03) 1px,transparent 1px);background-size:52px 52px;}.wrap{position:relative;z-index:1;width:100%;max-width:500px}/* LOGO */.logo{font-family:var(--font-display);font-size:2.4rem;color:var(--acc);text-shadow:var(--glow);text-align:center;letter-spacing:2px;animation:flicker 5s infinite}.logo em{color:var(--red);font-style:normal}.tagline{text-align:center;color:var(--muted);font-size:.7rem;letter-spacing:3px;text-transform:uppercase;margin:4px 0 32px}@keyframes flicker{0%,94%,96%,98%,100%{opacity:1}95%{opacity:.6}97%{opacity:.8}99%{opacity:.5}}/* CARD */.card{background:var(--panel);border:1px solid var(--border);border-radius:4px;padding:32px 28px;position:relative;margin-bottom:16px}.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--red),var(--acc),var(--grn));border-radius:4px 4px 0 0}/* NAV */.nav{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.nav-user{font-size:.72rem;color:var(--muted)}.nav-user strong{color:var(--acc)}.nav-links{display:flex;gap:14px}.nav-links a{font-size:.68rem;letter-spacing:1px;color:var(--muted);text-decoration:none;border-bottom:1px solid var(--border);padding-bottom:1px;transition:color .2s,border-color .2s}.nav-links a:hover,.nav-links a.active-nav{color:var(--acc);border-color:var(--acc)}/* TABS */.tabs{display:flex;gap:4px;margin-bottom:24px;border-bottom:1px solid var(--border)}.tab-btn{background:none;border:none;color:var(--muted);font-family:var(--font-mono);font-size:.72rem;letter-spacing:2px;text-transform:uppercase;padding:9px 16px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .2s,border-color .2s}.tab-btn.active{color:var(--acc);border-color:var(--acc)}.tab-btn:hover:not(.active){color:var(--text)}/* INPUTS */label{display:block;font-size:.65rem;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin:16px 0 5px}label:first-of-type{margin-top:0}input[type=text],input[type=password],input[type=number]{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:3px;color:var(--text);font-family:var(--font-mono);font-size:1rem;padding:10px 13px;outline:none;transition:border-color .2s,box-shadow .2s}input:focus{border-color:var(--acc);box-shadow:0 0 0 2px rgba(240,192,64,.15)}input[type=number]{font-size:1.5rem;text-align:center;letter-spacing:4px}input[type=number]::-webkit-inner-spin-button{-webkit-appearance:none}input[type=number]{-moz-appearance:textfield}/* DIFFICULTY CARDS */.diff-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.diff-card{background:var(--bg);border:2px solid var(--border);border-radius:4px;padding:16px 8px;text-align:center;cursor:pointer;transition:border-color .2s,box-shadow .2s;position:relative}.diff-card input[type=radio]{position:absolute;opacity:0;width:0;height:0}.diff-card:hover{border-color:var(--acc)}.sel-easy{border-color:var(--grn)!important;box-shadow:0 0 14px rgba(80,224,160,.25)}.sel-medium{border-color:var(--acc)!important;box-shadow:0 0 14px rgba(240,192,64,.25)}.sel-hard{border-color:var(--red)!important;box-shadow:0 0 14px rgba(224,90,90,.25)}.diff-emoji{font-size:1.6rem;margin-bottom:6px}.diff-lbl{font-family:var(--font-display);font-size:.88rem;letter-spacing:1px}.diff-range{font-size:.62rem;color:var(--muted);margin-top:4px;letter-spacing:1px}/* BUTTONS */.btn{display:block;width:100%;margin-top:20px;padding:13px;font-family:var(--font-display);font-size:.95rem;letter-spacing:2px;border:none;border-radius:3px;cursor:pointer;transition:transform .1s,box-shadow .2s}.btn:hover{transform:translateY(-1px)}.btn:active{transform:translateY(0)}.btn-acc{background:var(--acc);color:#080810}.btn-acc:hover{box-shadow:var(--glow)}.btn-grn{background:var(--grn);color:#080810}.btn-grn:hover{box-shadow:0 0 20px rgba(80,224,160,.4)}.btn-out{background:transparent;border:1px solid var(--border);color:var(--text);font-family:var(--font-mono);font-size:.78rem;letter-spacing:1px}.btn-out:hover{border-color:var(--acc);color:var(--acc);box-shadow:none}/* FLASH */.flash{padding:10px 13px;border-radius:3px;font-size:.78rem;letter-spacing:1px;margin-bottom:18px;border-left:3px solid}.flash.error{background:rgba(224,90,90,.1);border-color:var(--red);color:#f09090}.flash.success{background:rgba(80,224,160,.1);border-color:var(--grn);color:var(--grn)}.flash.info{background:rgba(240,192,64,.08);border-color:var(--acc);color:var(--acc)}/* HUD */.hud{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:20px}.hud-box{background:var(--bg);border:1px solid var(--border);border-radius:3px;padding:10px 6px;text-align:center}.hud-lbl{font-size:.58rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase}.hud-val{font-size:1.35rem;font-family:var(--font-display);margin-top:3px}#timer-display{color:var(--blue)}#timer-display.warn{color:var(--acc);animation:blink .7s infinite}#timer-display.danger{color:var(--red);animation:blink .4s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}/* PIPS */.pips{display:flex;gap:5px;margin:16px 0 6px;justify-content:center}.pip{flex:1;max-width:44px;height:9px;border-radius:2px;background:var(--border);transition:background .3s}.pip.ph{background:var(--red)}.pip.pl{background:var(--grn)}.pip.pc{background:var(--acc);animation:blink .9s infinite}.pip-leg{display:flex;gap:14px;justify-content:center;font-size:.6rem;letter-spacing:1px;color:var(--muted);margin-bottom:18px}.pip-leg span::before{display:inline-block;width:9px;height:5px;border-radius:1px;content:'';margin-right:4px;vertical-align:middle}.l-h::before{background:var(--red)}.l-l::before{background:var(--grn)}.l-c::before{background:var(--acc)}/* HISTORY */.history{margin-top:18px;max-height:160px;overflow-y:auto}.history::-webkit-scrollbar{width:3px}.history::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}.h-row{display:flex;align-items:center;gap:10px;padding:6px 10px;border-radius:2px;font-size:.78rem;margin-bottom:3px;background:var(--bg);border:1px solid var(--border)}.h-num{font-family:var(--font-display);font-size:.95rem;flex:0 0 50px}.h-dir{flex:1}.h-dir.high{color:var(--red)}.h-dir.low{color:var(--grn)}.h-att{color:var(--muted);font-size:.65rem}/* RESULT */.result-icon{font-size:3.5rem;text-align:center;margin-bottom:10px}.result-title{font-family:var(--font-display);font-size:1.7rem;text-align:center;margin-bottom:6px}.result-title.win{color:var(--grn)}.result-title.lose{color:var(--red)}.result-sub{text-align:center;color:var(--muted);font-size:.8rem;margin-bottom:22px}.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:22px}.stat-box{background:var(--bg);border:1px solid var(--border);border-radius:3px;padding:12px 6px;text-align:center}.stat-box .val{font-family:var(--font-display);font-size:1.4rem;color:var(--acc)}.stat-box .lbl{font-size:.58rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-top:3px}/* BADGE */.badge{display:inline-block;padding:2px 8px;border-radius:2px;font-size:.62rem;letter-spacing:1px;margin-left:6px}.badge-easy{background:rgba(80,224,160,.15);color:var(--grn)}.badge-medium{background:rgba(240,192,64,.15);color:var(--acc)}.badge-hard{background:rgba(224,90,90,.15);color:var(--red)}/* LEADERBOARD */.lb-tabs{display:flex;gap:6px;margin-bottom:18px}.lb-tab{flex:1;padding:9px 6px;background:var(--bg);border:1px solid var(--border);border-radius:3px;color:var(--muted);font-size:.68rem;letter-spacing:1px;text-transform:uppercase;cursor:pointer;text-align:center;transition:all .2s;font-family:var(--font-mono)}.lb-tab:hover{border-color:var(--acc);color:var(--acc)}.lb-tab.lb-on{border-color:var(--acc);color:var(--acc);background:rgba(240,192,64,.08)}.lb-table{width:100%;border-collapse:collapse}.lb-table th{font-size:.62rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;padding:6px 10px;text-align:left;border-bottom:1px solid var(--border)}.lb-table td{padding:9px 10px;font-size:.82rem;border-bottom:1px solid var(--border)}.lb-table tr:last-child td{border-bottom:none}.lb-rank{font-family:var(--font-display);color:var(--muted)}.r1{color:gold}.r2{color:silver}.r3{color:#cd7f32}.lb-you{color:var(--acc)}.lb-empty{text-align:center;color:var(--muted);padding:30px;font-size:.8rem}.sec-title{font-family:var(--font-display);font-size:.95rem;letter-spacing:1px;margin-bottom:16px}</style>
</head>
<body>
<div class="wrap">
  <div class="logo">NUMBER<em>QUEST</em></div>
  <div class="tagline">▸ guess · race · conquer ◂</div>
  {% block content %}{% endblock %}
</div>
{% block scripts %}{% endblock %}
</body>
</html>"""

# ───────────────────────────── HELPERS ────────────────────────────────

def render(tpl, **ctx):
    full = BASE.replace("{% block content %}{% endblock %}", tpl)\
               .replace("{% block scripts %}{% endblock %}",
                        ctx.pop("_scripts", ""))
    return render_template_string(full, **ctx)

def new_game(difficulty="medium"):
    d = DIFFICULTIES[difficulty]
    return {
        "number":        random.randint(d["min"], d["max"]),
        "difficulty":    difficulty,
        "min":           d["min"],
        "max":           d["max"],
        "attempts_left": MAX_ATTEMPTS,
        "high": 0, "low": 0,
        "history":       [],
        "start_time":    time.time(),
    }

def fmt_time(sec):
    s, ds = int(sec), int((sec % 1) * 10)
    return f"{s//60}m {s%60:02d}s" if s >= 60 else f"{s}.{ds}s"

def try_set_record(username, difficulty, guesses, elapsed):
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT guesses, time_secs FROM leaderboard WHERE username=%s AND difficulty=%s",
            (username, difficulty)
        )
        prev = cur.fetchone()
        is_record = (
            prev is None
            or guesses < prev["guesses"]
            or (guesses == prev["guesses"] and elapsed < prev["time_secs"])
        )
        if is_record:
            cur.execute("""
                INSERT INTO leaderboard (username, difficulty, guesses, time_secs)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username, difficulty)
                DO UPDATE SET guesses=EXCLUDED.guesses,
                              time_secs=EXCLUDED.time_secs,
                              played_at=CURRENT_TIMESTAMP
            """, (username, difficulty, guesses, elapsed))
            conn.commit()
        cur.close(); conn.close()
        return is_record
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False

def lb_rows(difficulty):
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT username, guesses, time_secs
            FROM leaderboard
            WHERE difficulty=%s
            ORDER BY guesses ASC, time_secs ASC
        """, (difficulty,))
        rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return []

# ───────────────────────────── TEMPLATES ──────────────────────────────

AUTH_T = """
<div class="card">
  <div class="tabs">
    <button class="tab-btn {% if tab=='login' %}active{% endif %}" onclick="showTab('login')">Login</button>
    <button class="tab-btn {% if tab=='signup' %}active{% endif %}" onclick="showTab('signup')">Sign Up</button>
  </div>
  {% if msg %}<div class="flash {{ msg_type }}">{{ msg }}</div>{% endif %}

  <div id="t-login" {% if tab=='signup' %}style="display:none"{% endif %}>
    <form method="POST" action="/login">
      <label>Username</label>
      <input type="text" name="username" required placeholder="enter username" autocomplete="username"/>
      <label>Password</label>
      <input type="password" name="password" required placeholder="••••••••" autocomplete="current-password"/>
      <button class="btn btn-acc" type="submit">▶ Login</button>
    </form>
  </div>

  <div id="t-signup" {% if tab=='login' %}style="display:none"{% endif %}>
    <form method="POST" action="/signup">
      <label>Choose Username</label>
      <input type="text" name="username" required placeholder="pick a name" autocomplete="username"/>
      <label>Choose Password</label>
      <input type="password" name="password" required placeholder="min 4 characters" autocomplete="new-password"/>
      <button class="btn btn-acc" type="submit">✦ Create Account</button>
    </form>
  </div>
</div>
<script>
function showTab(n){
  document.getElementById('t-login').style.display  = n==='login'  ? '' : 'none';
  document.getElementById('t-signup').style.display = n==='signup' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach((b,i)=>{
    b.classList.toggle('active',(i===0&&n==='login')||(i===1&&n==='signup'));
  });
}
</script>
"""

DIFF_T = """
<div class="card">
  <div class="nav">
    <div class="nav-user">Welcome, <strong>{{ username }}</strong></div>
    <div class="nav-links">
      <a href="/leaderboard">🏆 Leaderboard</a>
      <a href="/logout">Logout</a>
    </div>
  </div>
  {% if msg %}<div class="flash {{ msg_type }}">{{ msg }}</div>{% endif %}
  <div class="sec-title">▸ Choose Difficulty</div>
  <form method="POST" action="/start">
    <div class="diff-grid">
      {% for key, d in diffs.items() %}
      <label class="diff-card" id="dc-{{ key }}" onclick="pick('{{ key }}')">
        <input type="radio" name="difficulty" value="{{ key }}" {% if key=='medium' %}checked{% endif %}/>
        <div class="diff-emoji">{{ d.emoji }}</div>
        <div class="diff-lbl" style="color:{% if key=='easy' %}var(--grn){% elif key=='medium' %}var(--acc){% else %}var(--red){% endif %}">
          {{ d.label }}
        </div>
        <div class="diff-range">{{ d.min }} – {{ d.max }}</div>
      </label>
      {% endfor %}
    </div>
    <button class="btn btn-acc" style="margin-top:22px" type="submit">▶ Start Game</button>
  </form>
</div>
<script>
const SEL = {easy:'sel-easy', medium:'sel-medium', hard:'sel-hard'};
function pick(k){
  document.querySelectorAll('.diff-card').forEach(c=>c.classList.remove(...Object.values(SEL)));
  document.getElementById('dc-'+k).classList.add(SEL[k]);
  document.querySelector('input[value="'+k+'"]').checked=true;
}
pick('medium');
</script>
"""

GAME_T = """
<div class="card">
  <div class="nav">
    <div class="nav-user">
      <strong>{{ username }}</strong>
      <span class="badge badge-{{ diff }}">{{ diff_label }}</span>
    </div>
    <div class="nav-links">
      <a href="/leaderboard">🏆 Leaderboard</a>
      <a href="/difficulty">Change Diff</a>
      <a href="/logout">Logout</a>
    </div>
  </div>
  {% if msg %}<div class="flash {{ msg_type }}">{{ msg }}</div>{% endif %}

  <div class="hud">
    <div class="hud-box">
      <div class="hud-lbl">Attempts Left</div>
      <div class="hud-val">{{ attempts_left }}</div>
    </div>
    <div class="hud-box">
      <div class="hud-lbl">Too High</div>
      <div class="hud-val" style="color:var(--red)">{{ high }}</div>
    </div>
    <div class="hud-box">
      <div class="hud-lbl">Too Low</div>
      <div class="hud-val" style="color:var(--grn)">{{ low }}</div>
    </div>
    <div class="hud-box">
      <div class="hud-lbl">Time</div>
      <div class="hud-val" id="timer-display">0.0s</div>
    </div>
  </div>

  <div class="pips">
    {% for i in range(max_att) %}
      {% set used = max_att - attempts_left %}
      {% if i < used %}
        <div class="pip {% if history[i][1]=='high' %}ph{% else %}pl{% endif %}"></div>
      {% elif i == used %}
        <div class="pip pc"></div>
      {% else %}
        <div class="pip"></div>
      {% endif %}
    {% endfor %}
  </div>
  <div class="pip-leg">
    <span class="l-h">Too High</span>
    <span class="l-l">Too Low</span>
    <span class="l-c">Current</span>
  </div>

  <form method="POST" action="/guess">
    <label>Guess a number between {{ rmin }} and {{ rmax }}</label>
    <input type="number" name="guess" min="{{ rmin }}" max="{{ rmax }}"
           placeholder="?" autofocus required/>
    <button class="btn btn-acc" type="submit">Submit Guess</button>
  </form>

  {% if history %}
  <div class="history">
    {% for entry in history|reverse %}
    <div class="h-row">
      <div class="h-num">{{ entry[0] }}</div>
      <div class="h-dir {{ entry[1] }}">
        {% if entry[1]=='high' %}📉 Too High{% else %}📈 Too Low{% endif %}
      </div>
      <div class="h-att">#{{ loop.revindex }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</div>

<script>
const t0 = {{ start_time }} * 1000;
const el = document.getElementById('timer-display');
function tick(){
  const s = (Date.now()-t0)/1000;
  const m=Math.floor(s/60), sec=Math.floor(s%60), ds=Math.floor((s%1)*10);
  el.textContent = m ? m+'m '+String(sec).padStart(2,'0')+'s' : sec+'.'+ds+'s';
  el.className = s>60 ? 'danger' : s>30 ? 'warn' : '';
}
tick(); setInterval(tick,100);
</script>
"""

RESULT_T = """
<div class="card">
  <div class="result-icon">{{ icon }}</div>
  <div class="result-title {{ res_class }}">{{ title }}</div>
  <div class="result-sub">{{ subtitle }}</div>

  <div class="stats-grid">
    <div class="stat-box">
      <div class="val">{{ number }}</div>
      <div class="lbl">Answer</div>
    </div>
    <div class="stat-box">
      <div class="val" style="color:var(--blue)">{{ elapsed }}</div>
      <div class="lbl">Time</div>
    </div>
    <div class="stat-box">
      <div class="val" style="color:var(--red)">{{ high }}</div>
      <div class="lbl">Too High</div>
    </div>
    <div class="stat-box">
      <div class="val" style="color:var(--grn)">{{ low }}</div>
      <div class="lbl">Too Low</div>
    </div>
  </div>

  {% if won and is_record %}
  <div class="flash success" style="text-align:center;margin-bottom:18px">
    🏆 New personal best on {{ diff_label }}!
  </div>
  {% endif %}

  <form method="POST" action="/start">
    <input type="hidden" name="difficulty" value="{{ diff }}"/>
    <button class="btn btn-grn" type="submit">▶ Play Again ({{ diff_label }})</button>
  </form>
  <form method="GET" action="/difficulty" style="margin-top:8px">
    <button class="btn btn-out" type="submit">⇄ Change Difficulty</button>
  </form>
</div>
"""

LB_T = """
<div class="card">
  <div class="nav">
    <div class="nav-user">Logged in as <strong>{{ username }}</strong></div>
    <div class="nav-links">
      <a href="/difficulty">▶ Play</a>
      <a href="/logout">Logout</a>
    </div>
  </div>

  <div class="sec-title">🏆 Leaderboard</div>

  <div class="lb-tabs">
    {% for key, d in diffs.items() %}
    <button class="lb-tab {% if active==key %}lb-on{% endif %}" onclick="showDiff('{{ key }}')">
      {{ d.emoji }} {{ d.label }}
    </button>
    {% endfor %}
  </div>

  {% for key, d in diffs.items() %}
  <div id="lb-{{ key }}" {% if active!=key %}style="display:none"{% endif %}>
    {% set rows = lb_data[key] %}
    {% if rows %}
    <table class="lb-table">
      <thead><tr><th>#</th><th>Player</th><th>Guesses</th><th>Time</th></tr></thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td>
            <span class="lb-rank {% if loop.index==1 %}r1{% elif loop.index==2 %}r2{% elif loop.index==3 %}r3{% endif %}">
              {% if loop.index==1 %}🥇{% elif loop.index==2 %}🥈{% elif loop.index==3 %}🥉{% else %}{{ loop.index }}{% endif %}
            </span>
          </td>
          <td {% if row[0]==username %}class="lb-you"{% endif %}>
            {{ row[0] }}{% if row[0]==username %} ◀{% endif %}
          </td>
          <td>{{ row[1] }}</td>
          <td>{{ row[2] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="lb-empty">No scores yet for {{ d.label }}.<br>Be the first! 🎯</div>
    {% endif %}
  </div>
  {% endfor %}

  <form method="GET" action="/difficulty" style="margin-top:20px">
    <button class="btn btn-acc" type="submit">▶ Play Now</button>
  </form>
</div>
<script>
function showDiff(k){
  ['easy','medium','hard'].forEach(d=>{
    document.getElementById('lb-'+d).style.display = d===k?'':'none';
  });
  document.querySelectorAll('.lb-tab').forEach((b,i)=>{
    b.classList.toggle('lb-on',['easy','medium','hard'][i]===k);
  });
}
</script>
"""

# ───────────────────────────── ROUTES ─────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("difficulty") if "username" in session else url_for("auth"))

@app.route("/auth")
def auth():
    tab = request.args.get("tab", "login")
    msg = session.pop("message", None)
    msg_type = session.pop("msg_type", "info")
    return render(AUTH_T, tab=tab, msg=msg, msg_type=msg_type)



@app.route("/signup", methods=["POST"])
def signup():
    u = request.form.get("username", "").strip()
    p = request.form.get("password", "").strip()

    if not u or not p:
        session["message"]  = "Username and password are required."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="signup"))

    if len(p) < 4:
        session["message"]  = "Password must be at least 4 characters."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="signup"))

    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (u, p))
        conn.commit()
        cur.close(); conn.close()
        session["message"]  = "✅ Account created! Please log in."
        session["msg_type"] = "success"
        return redirect(url_for("auth", tab="login"))
    except psycopg2.errors.UniqueViolation:
        session["message"]  = f"Username '{u}' is already taken."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="signup"))
    except Exception as e:
        print(f"[DB ERROR] {e}")
        session["message"]  = "Database error. Please try again."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="signup"))


@app.route("/login", methods=["POST"])
def login():
    u = request.form.get("username", "").strip()
    p = request.form.get("password", "").strip()
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, p))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user:
            session["username"] = u
            return redirect(url_for("difficulty"))
        session["message"]  = "Wrong username or password."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="login"))
    except Exception as e:
        print(f"[DB ERROR] {e}")
        session["message"]  = "Database error. Please try again."
        session["msg_type"] = "error"
        return redirect(url_for("auth", tab="login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth"))

@app.route("/difficulty")
def difficulty():
    if "username" not in session:
        return redirect(url_for("auth"))
    msg = session.pop("message", None)
    msg_type = session.pop("msg_type", "info")
    return render(DIFF_T, username=session["username"],
                  diffs=DIFFICULTIES, msg=msg, msg_type=msg_type)

@app.route("/start", methods=["GET", "POST"])
def start():
    if "username" not in session:
        return redirect(url_for("auth"))
    diff = request.form.get("difficulty", "medium")
    if diff not in DIFFICULTIES:
        diff = "medium"
    session["game"] = new_game(diff)
    session.pop("result", None)
    return redirect(url_for("game"))

@app.route("/game")
def game():
    if "username" not in session:
        return redirect(url_for("auth"))
    g = session.get("game")
    if not g:
        return redirect(url_for("difficulty"))
    msg = session.pop("message", None)
    msg_type = session.pop("msg_type", "info")
    d = DIFFICULTIES[g["difficulty"]]
    return render(GAME_T,
        username=session["username"],
        diff=g["difficulty"], diff_label=d["label"],
        attempts_left=g["attempts_left"], max_att=MAX_ATTEMPTS,
        high=g["high"], low=g["low"],
        history=g["history"],
        rmin=g["min"], rmax=g["max"],
        start_time=g["start_time"],
        msg=msg, msg_type=msg_type,
    )

@app.route("/guess", methods=["POST"])
def guess():
    if "username" not in session:
        return redirect(url_for("auth"))
    g = session.get("game")
    if not g:
        return redirect(url_for("difficulty"))

    try:
        user_num = int(request.form.get("guess", ""))
    except ValueError:
        session["message"] = "⚠ Please enter a whole number."
        session["msg_type"] = "error"
        return redirect(url_for("game"))

    if user_num < g["min"] or user_num > g["max"]:
        session["message"] = f"⚠ Number must be between {g['min']} and {g['max']}."
        session["msg_type"] = "error"
        return redirect(url_for("game"))

    number = g["number"]

    if user_num == number:
        elapsed = time.time() - g["start_time"]
        total   = g["high"] + g["low"] + 1
        is_rec  = try_set_record(session["username"], g["difficulty"], total, elapsed)
        session["result"] = {
            "won": True, "number": number,
            "high": g["high"], "low": g["low"],
            "total": total, "elapsed": elapsed,
            "difficulty": g["difficulty"], "is_record": is_rec,
        }
        session.pop("game", None)
        return redirect(url_for("result"))

    if user_num > number:
        g["high"] += 1
        g["history"].append((user_num, "high"))
        session["message"] = "📉 Too HIGH! Try lower."
    else:
        g["low"] += 1
        g["history"].append((user_num, "low"))
        session["message"] = "📈 Too LOW! Try higher."

    g["attempts_left"] -= 1
    session["game"] = g
    session["msg_type"] = "info"

    if g["attempts_left"] == 0:
        elapsed = time.time() - g["start_time"]
        session["result"] = {
            "won": False, "number": number,
            "high": g["high"], "low": g["low"],
            "total": g["high"] + g["low"],
            "elapsed": elapsed,
            "difficulty": g["difficulty"], "is_record": False,
        }
        session.pop("game", None)
        return redirect(url_for("result"))

    return redirect(url_for("game"))

@app.route("/result")
def result():
    if "username" not in session:
        return redirect(url_for("auth"))
    r = session.get("result")
    if not r:
        return redirect(url_for("difficulty"))
    d = DIFFICULTIES.get(r["difficulty"], DIFFICULTIES["medium"])
    if r["won"]:
        icon, title = "🎉", "You Cracked It!"
        subtitle = f"Found in {r['total']} guess{'es' if r['total']!=1 else ''} · {fmt_time(r['elapsed'])}"
        res_class = "win"
    else:
        icon, title = "💀", "Game Over"
        subtitle = f"The number was {r['number']} · {fmt_time(r['elapsed'])}"
        res_class = "lose"
    return render(RESULT_T,
        icon=icon, title=title, subtitle=subtitle, res_class=res_class,
        number=r["number"], elapsed=fmt_time(r["elapsed"]),
        high=r["high"], low=r["low"],
        won=r["won"], is_record=r.get("is_record", False),
        diff=r["difficulty"], diff_label=d["label"],
    )

@app.route("/leaderboard")
def leaderboard_page():
    if "username" not in session:
        return redirect(url_for("auth"))
    active = request.args.get("diff", "medium")
    lb_data = {}
    for key in DIFFICULTIES:
        rows = lb_rows(key)
        lb_data[key] = [(u, g, fmt_time(t)) for u, g, t in rows]
    return render(LB_T,
        username=session["username"],
        diffs=DIFFICULTIES, active=active, lb_data=lb_data,
    )

# ───────────────────────────── MAIN ───────────────────────────────────

# Run init_db when app starts (works with both gunicorn and direct python)
try:
    init_db()
except Exception as e:
    print(f"[DB INIT ERROR] {e}")

if __name__ == "__main__":
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   NUMBER QUEST v2 — Web Edition      ║")
    print("  ║   Open  http://localhost:5000         ║")
    print("  ║   Default login:  admin / 1234        ║")
    print("  ╚══════════════════════════════════════╝\n")
    app.run(debug=False, port=5000, threaded=True)
