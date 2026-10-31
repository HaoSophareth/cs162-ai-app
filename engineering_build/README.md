# Race Training Planner

A small Flask app that generates a training plan for a 5k, 10k, half marathon or marathon and lets you track your runs in a calendar-style week view. Runs locally, no API keys.

## Setup

Needs Python 3.10 or newer.

```bash
cd engineering_build
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open http://127.0.0.1:5050, sign up, answer the profile questions, then create a plan from the calendar.

Data is stored in SQLite at `instance/running.db`, so it is kept between restarts. Delete that file to start over. The tables are only created when missing, so after a change to the data model you also need to delete it.

## Files

- `app.py` - creates the app, database and login manager
- `models.py` - User, Plan and Run tables
- `auth.py` - sign up, log in, log out
- `main.py` - profile, plans (create/edit in 3 steps, summary, activate, delete), scrolling week view, run detail/edit/done
- `plan_generator.py` - the plan rules and race-time estimates (plain Python, no Flask)
- `templates/`, `static/style.css` - pages and styling
