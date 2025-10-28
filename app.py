#!/usr/bin/env python3
import os, sys, json, sqlite3, datetime, subprocess, mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "pmp.db")
STATIC_DIR = os.path.join(APP_DIR, "static")
TPL_DIR = os.path.join(APP_DIR, "templates")
AUTOMATIONS_DIR = os.path.join(APP_DIR, "automations")

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_column(table, col, decl):
    conn = get_conn(); cur = conn.cursor()
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        conn.commit()
    conn.close()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'backlog',
        type TEXT DEFAULT 'task',
        priority TEXT DEFAULT 'medium',
        story_points INTEGER DEFAULT 0,
        parent_id INTEGER,
        due_date TEXT,
        start_date TEXT,
        end_date TEXT,
        pi_id INTEGER,
        sprint_id INTEGER,
        assignee TEXT,
        dependencies TEXT DEFAULT '[]',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS risks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        impact TEXT,
        probability TEXT,
        mitigation TEXT,
        owner TEXT,
        status TEXT DEFAULT 'open',
        review_date TEXT,
        resolved_date TEXT,
        project TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS program_increments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pi_id INTEGER,
        name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS time_off (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        category TEXT,
        note TEXT
    )
    """)

    conn.commit()
    conn.close()

    # lightweight migrations for new fields
    ensure_column('tasks','planned_start_date','TEXT')
    ensure_column('tasks','planned_end_date','TEXT')
    ensure_column('tasks','actual_end_date','TEXT')

class App(BaseHTTPRequestHandler):
    def _send_raw(self, data: bytes, status=200, ctype="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status=200, ctype="text/plain; charset=utf-8"):
        self._send_raw(text.encode("utf-8"), status, ctype)

    def _send_json(self, obj, status=200):
        self._send_text(json.dumps(obj), status, "application/json; charset=utf-8")

    def _parse_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def serve_index(self):
        path = os.path.join(TPL_DIR, "index.html")
        with open(path, "rb") as f:
            self._send_raw(f.read(), 200, "text/html; charset=utf-8")

    def serve_static(self, path: str):
        full = os.path.join(APP_DIR, path.lstrip("/"))
        if not full.startswith(STATIC_DIR):
            self._send_text("Forbidden", 403)
            return
        if not os.path.isfile(full):
            self._send_text("Not found", 404)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            self._send_raw(f.read(), 200, ctype)

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path

        if p == "/":
            return self.serve_index()
        if p.startswith("/static/"):
            return self.serve_static(p)

        if p == "/api/tasks":
            qs = parse_qs(parsed.query or "")
            status = qs.get("status", [None])[0]
            conn = get_conn(); cur = conn.cursor()
            q = "SELECT * FROM tasks"
            params = []
            if status:
                q += " WHERE status=?"
                params.append(status)
            q += " ORDER BY priority DESC, COALESCE(due_date, planned_end_date) ASC"
            rows = cur.execute(q, params).fetchall()
            conn.close()
            return self._send_json([dict(r) for r in rows])

        if p == "/api/risks":
            conn = get_conn(); cur = conn.cursor()
            rows = cur.execute("SELECT * FROM risks ORDER BY review_date ASC").fetchall()
            conn.close()
            return self._send_json([dict(r) for r in rows])

        if p == "/api/pis":
            conn = get_conn(); cur = conn.cursor()
            rows = cur.execute("SELECT * FROM program_increments ORDER BY start_date ASC").fetchall()
            conn.close()
            return self._send_json([dict(r) for r in rows])

        if p == "/api/sprints":
            conn = get_conn(); cur = conn.cursor()
            rows = cur.execute("SELECT * FROM sprints ORDER BY start_date ASC").fetchall()
            conn.close()
            return self._send_json([dict(r) for r in rows])

        if p == "/api/timeoff":
            conn = get_conn(); cur = conn.cursor()
            rows = cur.execute("SELECT * FROM time_off ORDER BY date ASC").fetchall()
            conn.close()
            return self._send_json([dict(r) for r in rows])

        if p == "/api/dashboard":
            conn = get_conn(); cur = conn.cursor()
            today = datetime.date.today()
            start_week = today - datetime.timedelta(days=today.weekday())
            end_week = start_week + datetime.timedelta(days=6)

            rows = cur.execute("SELECT * FROM tasks").fetchall()
            tasks = [dict(r) for r in rows]
            due_this_week = [t for t in tasks if (t.get("due_date") or t.get("planned_end_date")) and start_week.isoformat() <= (t.get("due_date") or t.get("planned_end_date")) <= end_week.isoformat()]
            open_issues = [t for t in tasks if t.get("type") == "bug" and t.get("status") not in ("done", "cancelled")]
            deps = 0
            for t in tasks:
                try: deps += len(json.loads(t.get("dependencies") or "[]"))
                except Exception: pass

            rrows = cur.execute("SELECT * FROM risks").fetchall()
            risks = [dict(r) for r in rrows]
            risks_due = [r for r in risks if r.get("review_date") and start_week.isoformat() <= r["review_date"] <= end_week.isoformat()]

            statuses = ["backlog","to-do","in progress","blocked","done","cancelled"]
            load = {s: 0 for s in statuses}
            for t in tasks:
                s = t.get("status")
                if s in load: load[s] += 1

            conn.close()
            return self._send_json({
                "week_start": start_week.isoformat(),
                "week_end": end_week.isoformat(),
                "due_this_week": due_this_week,
                "open_issues": open_issues,
                "dependency_count": deps,
                "risks_due": risks_due,
                "task_load": load
            })

        if p == "/api/automations":
            items = []
            if os.path.isdir(AUTOMATIONS_DIR):
                for fname in os.listdir(AUTOMATIONS_DIR):
                    if fname.endswith(".py") and not fname.startswith("_"):
                        items.append({"name": fname[:-3], "file": fname})
            return self._send_json(items)

        return self._send_text("Not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path
        data = self._parse_json()

        if p == "/api/seed":
            conn = get_conn(); cur = conn.cursor()
            for t in ("program_increments","sprints","tasks","risks","time_off"):
                cur.execute(f"DELETE FROM {t}")

            cur.execute("INSERT INTO program_increments (name,start_date,end_date) VALUES (?,?,?)", ("PI-1","2025-10-20","2025-12-14"))
            pi1 = cur.lastrowid
            cur.executemany("INSERT INTO sprints (pi_id,name,start_date,end_date) VALUES (?,?,?,?)", [
                (pi1,"Sprint 1","2025-10-20","2025-11-02"),
                (pi1,"Sprint 2","2025-11-03","2025-11-16"),
                (pi1,"Sprint 3","2025-11-17","2025-11-30"),
                (pi1,"Sprint 4","2025-12-01","2025-12-14"),
            ])

            now = now_iso()
            cur.executemany("""
            INSERT INTO tasks (title,description,status,type,priority,story_points,parent_id,due_date,start_date,end_date,planned_start_date,planned_end_date,actual_end_date,pi_id,sprint_id,assignee,dependencies,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, [
                ("Design Landing UI", "Create the dashboard hero and KPIs", "to-do", "task", "high", 3, None, "2025-11-02", "2025-10-26", None, "2025-10-26", "2025-11-02", None, pi1, 1, "Kameron", "[]", now, now),
                ("Build Kanban", "Drag-and-drop columns", "in progress", "task", "medium", 5, None, "2025-11-10", "2025-10-27", None, "2025-10-27", "2025-11-10", None, pi1, 2, "Kameron", "[1]", now, now),
                ("Bug: Gantt zoom glitch", "Zoom past month throws error", "backlog", "bug", "high", 1, None, "2025-11-05", None, None, None, None, None, pi1, 2, "Kameron", "[]", now, now),
                ("Integrate Outlook Draft", "Weekly report automation", "blocked", "task", "high", 2, None, "2025-11-07", None, None, None, None, None, pi1, 2, "Kameron", "[1,2]", now, now),
                ("Dependency: Seed Data", "Provide default datasets", "done", "dep", "low", 1, None, "2025-10-28", "2025-10-27", "2025-10-27", "2025-10-25", "2025-10-27", "2025-10-27", pi1, 1, "Kameron", "[]", now, now),
            ])

            cur.executemany("""
            INSERT INTO risks (title,description,impact,probability,mitigation,owner,status,review_date,project,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, [
                ("Schedule risk", "Competing school deadlines", "high", "medium", "Block calendar and reduce scope", "Kameron", "monitoring", "2025-10-30", "PMP Tool", now, now),
                ("Tech risk", "Outlook COM not available", "medium", "medium", "Fallback to .eml / text file", "Kameron", "open", "2025-11-01", "PMP Tool", now, now),
            ])

            cur.executemany("INSERT INTO time_off (date,category,note) VALUES (?,?,?)", [
                ("2025-11-28", "holiday", "Thanksgiving Friday"),
                ("2025-11-27", "holiday", "Thanksgiving Day")
            ])

            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/tasks":
            conn = get_conn(); cur = conn.cursor()
            now = now_iso()
            cur.execute("""
                INSERT INTO tasks (title,description,status,type,priority,story_points,parent_id,due_date,start_date,end_date,planned_start_date,planned_end_date,actual_end_date,pi_id,sprint_id,assignee,dependencies,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, [
                data.get("title"), data.get("description"), data.get("status", "backlog"), data.get("type","task"),
                data.get("priority","medium"), data.get("story_points",0), data.get("parent_id"),
                data.get("due_date"), data.get("start_date"), data.get("end_date"),
                data.get("planned_start_date"), data.get("planned_end_date"), data.get("actual_end_date"),
                data.get("pi_id"), data.get("sprint_id"), data.get("assignee"),
                json.dumps(data.get("dependencies", [])), now, now
            ])
            tid = cur.lastrowid
            conn.commit(); conn.close()
            return self._send_json({"id": tid})

        if p == "/api/risks":
            conn = get_conn(); cur = conn.cursor()
            now = now_iso()
            cur.execute("""
            INSERT INTO risks (title, description, impact, probability, mitigation, owner, status, review_date, resolved_date, project, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, [
                data.get("title"), data.get("description"), data.get("impact"), data.get("probability"),
                data.get("mitigation"), data.get("owner"), data.get("status","open"),
                data.get("review_date"), data.get("resolved_date"), data.get("project"), now, now
            ])
            rid = cur.lastrowid
            conn.commit(); conn.close()
            return self._send_json({"id": rid})

        if p == "/api/pis":
            conn = get_conn(); cur = conn.cursor()
            cur.execute("INSERT INTO program_increments (name,start_date,end_date) VALUES (?,?,?)",
                        (data.get("name"), data.get("start_date"), data.get("end_date")))
            pid = cur.lastrowid
            conn.commit(); conn.close()
            return self._send_json({"id": pid})

        if p == "/api/sprints":
            conn = get_conn(); cur = conn.cursor()
            cur.execute("INSERT INTO sprints (pi_id,name,start_date,end_date) VALUES (?,?,?,?)",
                        (data.get("pi_id"), data.get("name"), data.get("start_date"), data.get("end_date")))
            sid = cur.lastrowid
            conn.commit(); conn.close()
            return self._send_json({"id": sid})

        if p == "/api/timeoff":
            conn = get_conn(); cur = conn.cursor()
            cur.execute("INSERT INTO time_off (date,category,note) VALUES (?,?,?)",
                        (data.get("date"), data.get("category"), data.get("note")))
            tid = cur.lastrowid
            conn.commit(); conn.close()
            return self._send_json({"id": tid})

        if p == "/api/automations/run":
            name = (data.get("name") or "").strip()
            target = os.path.join(AUTOMATIONS_DIR, f"{name}.py")
            if not os.path.isfile(target):
                return self._send_json({"error":"Not found"}, 404)
            try:
                proc = subprocess.run([sys.executable, target, DB_PATH], capture_output=True, text=True, timeout=120)
                return self._send_json({"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        return self._send_text("Not found", 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        p = parsed.path
        data = self._parse_json()

        if p == "/api/tasks":
            tid = data.get("id")
            if not tid:
                return self._send_json({"error":"id required"}, 400)
            fields = [k for k in data.keys() if k != "id"]
            if not fields:
                return self._send_json({"error":"at least one field"}, 400)

            sets = []; params = []
            for f in fields:
                v = data[f]
                if f == "dependencies":
                    v = json.dumps(v)
                sets.append(f"{f}=?")
                params.append(v)
            params.append(tid)
            conn = get_conn(); cur = conn.cursor()
            cur.execute(f"UPDATE tasks SET {', '.join(sets)}, updated_at=? WHERE id=?", params[:-1] + [now_iso(), params[-1]])
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/risks":
            rid = data.get("id")
            if not rid:
                return self._send_json({"error":"id required"}, 400)
            fields = [k for k in data.keys() if k != "id"]
            sets = []; params = []
            for f in fields:
                sets.append(f"{f}=?")
                params.append(data[f])
            params.append(rid)
            conn = get_conn(); cur = conn.cursor()
            cur.execute(f"UPDATE risks SET {', '.join(sets)}, updated_at=? WHERE id=?", params[:-1] + [now_iso(), params[-1]])
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/pis":
            pid = data.get("id")
            if not pid: return self._send_json({"error":"id required"}, 400)
            sets = []; params = []
            for f in ("name","start_date","end_date"):
                if f in data:
                    sets.append(f"{f}=?")
                    params.append(data[f])
            params.append(pid)
            conn = get_conn(); cur = conn.cursor()
            cur.execute(f"UPDATE program_increments SET {', '.join(sets)} WHERE id=?", params)
            conn.commit(); conn.close()
            return self._send_json({"ok":True})

        if p == "/api/sprints":
            sid = data.get("id")
            if not sid: return self._send_json({"error":"id required"}, 400)
            sets = []; params = []
            for f in ("pi_id","name","start_date","end_date"):
                if f in data:
                    sets.append(f"{f}=?")
                    params.append(data[f])
            params.append(sid)
            conn = get_conn(); cur = conn.cursor()
            cur.execute(f"UPDATE sprints SET {', '.join(sets)} WHERE id=?", params)
            conn.commit(); conn.close()
            return self._send_json({"ok":True})

        return self._send_text("Not found", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        p = parsed.path
        data = self._parse_json()

        if p == "/api/tasks":
            tid = data.get("id")
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM tasks WHERE id=?", (tid,))
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/risks":
            rid = data.get("id")
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM risks WHERE id=?", (rid,))
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/pis":
            pid = data.get("id")
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM program_increments WHERE id=?", (pid,))
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/sprints":
            sid = data.get("id")
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM sprints WHERE id=?", (sid,))
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        if p == "/api/timeoff":
            tid = data.get("id")
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM time_off WHERE id=?", (tid,))
            conn.commit(); conn.close()
            return self._send_json({"ok": True})

        return self._send_text("Not found", 404)


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(TPL_DIR, exist_ok=True)
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    init_db()
    port = 5050
    httpd = HTTPServer(("127.0.0.1", port), App)
    print(f"Serving on http://127.0.0.1:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
