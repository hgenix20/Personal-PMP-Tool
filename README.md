# Personal PMP Tool (Local-only)

Run locally in a browser. No external services.

## Quickstart
```bash
python app.py
# open http://127.0.0.1:5050
```

## Storage
- SQLite DB: `pmp.db` (created automatically)
- You can also export/import CSV/JSON later.

## Features
- Dashboard with weekly quick Gantt, task load, due lists, issues, risks, and **PI/Sprint status pies**
- Backlog list + **Kanban** with drag and drop, **modal editor** (title/type/status/priority/planned+actual dates/deps)
- Project Increments & Sprints (flexible dates) + Time Off
- Interactive Gantt with **zoom**, search highlight, and **PI/Sprint bands**
- Risk Register (simple list with review dates)
- Automations: drop `.py` files in `automations/` and they appear as buttons

## Sample Data
Click "🌱 Seed sample data" in the sidebar.
