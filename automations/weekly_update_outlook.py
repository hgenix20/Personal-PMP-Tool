import sys, os, sqlite3, datetime
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'pmp.db')
conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
cur = conn.cursor()

 today = datetime.date.today()
start_week = today - datetime.timedelta(days=today.weekday())
end_week = start_week + datetime.timedelta(days=6)
rows = cur.execute("SELECT * FROM tasks").fetchall()
tasks = [dict(r) for r in rows]
done = [t for t in tasks if t.get('status') == 'done' and t.get('end_date') and start_week.isoformat() <= t['end_date'] <= end_week.isoformat()]
in_prog = [t for t in tasks if t.get('status') == 'in progress']
blocked = [t for t in tasks if t.get('status') == 'blocked']
next_up = [t for t in tasks if t.get('status') in ('to-do','backlog')][:10]
issues = [t for t in tasks if t.get('type') == 'bug' and t.get('status') != 'done']
rrows = cur.execute("SELECT * FROM risks").fetchall()
risks = [dict(r) for r in rrows]
risks_due = [r for r in risks if r.get('review_date') and start_week.isoformat() <= r['review_date'] <= end_week.isoformat()]
subject = f"Weekly Update | {start_week.isoformat()} - {end_week.isoformat()}"
lines = [subject, "", "Highlights:", f"- Completed: {len(done)}", f"- In Progress: {len(in_prog)}", f"- Blocked: {len(blocked)}", f"- Open Issues: {len(issues)}", f"- Risks to Review: {len(risks_due)}", "", "Completed:"] + [f"  • {t['title']} (ended {t['end_date']})" for t in done] + ["", "In Progress:"] + [f"  • {t['title']} (due {t.get('due_date') or 'n/a'})" for t in in_prog] + ["", "Blocked:"] + [f"  • {t['title']}" for t in blocked] + ["", "Next Up:"] + [f"  • {t['title']}" for t in next_up] + ["", "Issues:"] + [f"  • {t['title']} ({t['status']})" for t in issues] + ["", "Risks to Review:"] + [f"  • {r['title']} (review {r['review_date']})" for r in risks_due]
body = "\n".join(lines)
made_outlook = False
try:
    import win32com.client as win32
    outlook = win32.Dispatch('Outlook.Application')
    mail = outlook.CreateItem(0)
    mail.Subject = subject
    mail.Body = body
    mail.Save()
    made_outlook = True
    print('Outlook draft created.')
except Exception as e:
    print('Outlook not available, writing .txt draft instead:', e)
if not made_outlook:
    out_path = os.path.join(os.path.dirname(__file__), f"weekly_update_{start_week.isoformat()}_{end_week.isoformat()}.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(body)
    print('Draft written to', out_path)
