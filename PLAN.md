# CS162 AI application assignment - plan

Guide: ~/cs162/assignments/ai_application_assoginment.md

## What we're doing

Build the same small web app twice with Claude Code (Opus 5.5):

1. `feature_build/` - prompts describe only what the app does (no stack, schema or files).
2. `engineering_build/` - prompts describe how to build it (stack, data model, files, auth).

App: a running plan generator and tracker for a 5k, 10k, half or full marathon.

## App spec (what it does)

Same feature list for both builds. Build 1 gets only this; Build 2 gets this plus the engineering notes below.

**Accounts**
- Sign up and log in with username + password. Log out.
- Each user only sees their own plan and runs.

**Setup (one page right after signup, editable later)**
- Experience: new runner, or have run before.
- Availability: which days of the week they can run (at least 3), and which of those is the long-run day.
- Goal: race distance (5k, 10k, half, full), training start date, race date.
- If the time between start and race is shorter than recommended for that distance, show a warning but still allow it.
- Saving the setup generates the plan. Editing it later regenerates the plan (warn that edits to runs will be replaced).

**Plan generation (rules, no AI)**
- Weekly distance starts low (lower for new runners) and grows about 10% a week.
- Every 4th week is a lighter cutback week.
- The last 1-2 weeks taper down before the race.
- Long run on the chosen day, about 30% of the week's distance, building to a peak per distance (about 8 / 14 / 18 / 32 km).
- One tempo or interval run a week (alternating); the other days are easy runs.
- Race day is in the plan as its own run.
- Numbers come from one public source (e.g. Hal Higdon novice plans), named in the README.

**Dashboard (week view, inspired by Google Calendar)**
- 7 day columns, no times.
- Header like "Oct 19 - Oct 25 · Week 4".
- Previous / next week and a Today button.
- Weekly total: planned km and completed km.
- Run cards color-coded by type: easy, long, tempo, intervals, race.

**Runs**
- Click a card to see details: type, distance, date, short description, notes.
- Edit a run: change date (this is how you move it), distance, notes.
- Mark a run done / not done.
- "Add to Google Calendar" link on each run (plain link, no Google account connection).

**Out of scope (cut on purpose)**
- Sex, age, weight, height; past race times; paces.
- Custom distances; miles (km only).
- Multi-step onboarding wizard.
- Drag and drop (maybe later, if time).
- Google Calendar API / sync; .ics export (maybe later, if time).

## Engineering notes (Build 2 only)

To be turned into the Build 2 prompt: Flask app, Jinja templates + plain CSS, Flask-SQLAlchemy + SQLite, Flask-Login + Werkzeug password hashing, requirements.txt. Data model roughly User, Plan (setup answers), Run (date, type, distance, notes, done). Plan generator as one plain function in its own file. File layout to decide when writing the prompt.

## Phases

1. Spec + write both prompts
2. Build 1: feature-wise
3. Build 2: engineering-wise
4. Compare: tokens, time, separation of concerns, heuristics log
5. Deliverables: zip, run instructions, demo video, PDF report (800 words max)

## Rules

- Only class-covered tech (sessions 1-15): Flask, Jinja, HTML/CSS, Flask-SQLAlchemy + SQLite, Flask-Login, Werkzeug hashing, venv + requirements.txt. No Docker, pytest, CI, JS frameworks.
- Keep both apps as basic as possible: readable code, a few comments that explain why, nothing restating the line.
- Runs locally, no API keys.
- I write the build prompts myself.

## Process

Prompting approach (same for both builds): one main prompt with the whole spec, then follow-up prompts only to fix what's broken or wrong. Every follow-up goes in the heuristics log with a reason. Why: keeps the only difference between builds "what vs how", fewer prompts = fewer tokens (each prompt resends the whole conversation), and the AI sees the full design up front.

1. Plan here, write both prompts below.
2. Exit, then `cd ~/cs162-ai-app/feature_build && claude`, run Build 1. Note start/end time. (Fresh folder = no saved memory, so the AI only knows what the prompts say.)
3. Exit, then `cd ~/cs162-ai-app/engineering_build && claude`, run Build 2. Note start/end time.
4. Back in the main session (read this file first), analysis: token counts from both transcripts, report, zip, demo video.

Before every `/clear`: save anything important to this file.

## Prompts

### Build 1 (feature-wise)

```
Build me a web app for planning and tracking training for a running race. It must run on my own computer with no API keys or paid services, keep data saved between restarts, and the code should be simple and readable.

Accounts
- Users sign up and log in with a username and password, and can log out.
- Each user only sees their own plan and runs.

Setup (one page right after signup, can be edited later)
- Experience: new runner, or have run before.
- Which days of the week they can run (at least 3), and which of those is the long-run day.
- Goal: race distance (5k, 10k, half marathon, marathon), training start date, race date.
- If the time between start and race is shorter than recommended for that distance, show a warning but still allow it.
- Saving the setup generates the plan. Editing the setup later regenerates the plan, with a warning that changes made to runs will be replaced.

How the plan is generated (fixed rules, no AI)
- Weekly distance starts low (lower for new runners) and grows about 10% a week.
- Every 4th week is a lighter cutback week.
- The last 1-2 weeks taper down before the race.
- The long run is on the chosen day, about 30% of the week's distance, building up to a peak of about 8 km (5k), 14 km (10k), 18 km (half) or 32 km (marathon).
- One tempo or interval run a week, alternating; the other days are easy runs.
- Race day is in the plan as its own run.

Dashboard (a week view, like Google Calendar's week view)
- 7 day columns, no times of day.
- A header like "Oct 19 - Oct 25 · Week 4" (week number of the plan).
- Previous week, next week and a Today button.
- The week's planned km and completed km.
- Run cards color-coded by type: easy, long, tempo, intervals, race.

Runs
- Click a run to see its details: type, distance, date, a short description of the workout, and notes.
- Edit a run: change its date (this is how you move it to another day), distance and notes.
- Mark a run as done or not done.
- Each run has an "Add to Google Calendar" link (just a link, no connecting a Google account).

Keep it to these features. Distances in km only.
```

### Build 2 (engineering-wise)

Same feature text as Build 1, then a "How to build it" section.

```
Build me a web app for planning and tracking training for a running race. It must run on my own computer with no API keys or paid services, keep data saved between restarts, and the code should be simple and readable.

Accounts
- Users sign up and log in with a username and password, and can log out.
- Each user only sees their own plan and runs.

Setup (one page right after signup, can be edited later)
- Experience: new runner, or have run before.
- Which days of the week they can run (at least 3), and which of those is the long-run day.
- Goal: race distance (5k, 10k, half marathon, marathon), training start date, race date.
- If the time between start and race is shorter than recommended for that distance, show a warning but still allow it.
- Saving the setup generates the plan. Editing the setup later regenerates the plan, with a warning that changes made to runs will be replaced.

How the plan is generated (fixed rules, no AI)
- Weekly distance starts low (lower for new runners) and grows about 10% a week.
- Every 4th week is a lighter cutback week.
- The last 1-2 weeks taper down before the race.
- The long run is on the chosen day, about 30% of the week's distance, building up to a peak of about 8 km (5k), 14 km (10k), 18 km (half) or 32 km (marathon).
- One tempo or interval run a week, alternating; the other days are easy runs.
- Race day is in the plan as its own run.

Dashboard (a week view, like Google Calendar's week view)
- 7 day columns, no times of day.
- A header like "Oct 19 - Oct 25 · Week 4" (week number of the plan).
- Previous week, next week and a Today button.
- The week's planned km and completed km.
- Run cards color-coded by type: easy, long, tempo, intervals, race.

Runs
- Click a run to see its details: type, distance, date, a short description of the workout, and notes.
- Edit a run: change its date (this is how you move it to another day), distance and notes.
- Mark a run as done or not done.
- Each run has an "Add to Google Calendar" link (just a link, no connecting a Google account).

Keep it to these features. Distances in km only.

How to build it
- Stack: Python with Flask, Jinja templates, plain HTML and CSS (no JavaScript), Flask-SQLAlchemy with SQLite, Flask-Login, Werkzeug password hashing. Pinned versions in requirements.txt, run in a venv.
- Data model (3 tables):
  - User: id, username (unique), password_hash
  - Plan: id, user_id (foreign key, one plan per user), experience, run_days (e.g. "Mon,Wed,Sat"), long_run_day, race_distance, start_date, race_date
  - Run: id, plan_id (foreign key), date, run_type, distance_km, description, notes, done
- Files:
  - app.py: creates the app, config, sets up the database and login manager, registers the blueprints
  - models.py: the three SQLAlchemy models
  - auth.py: blueprint for signup, login, logout
  - main.py: blueprint for setup, week view, run detail, edit run, mark done
  - plan_generator.py: one plain function that takes the setup answers and returns the list of runs; no Flask or database code in it
  - templates/: base.html (layout), login.html, signup.html, setup.html, week.html, run.html, edit_run.html
  - static/style.css: layout and run-type colors
- Auth: Flask-Login sessions, passwords stored only as salted hashes. Every page except login and signup needs login, and every query for a plan or run filters by current_user so users can't open each other's data by changing the URL.
- Regenerating a plan deletes that plan's runs and creates the new ones in one commit.
- Comments: a few short ones that explain why, not what each line does. No docstrings on simple functions.
- Add a short README with how to set up the venv and run the app.
```

## Heuristics log

One row per prompt, filled in during each build.

### Build 1

| # | Prompt (short) | Result | Accept / correct / re-prompt | Why |
|---|---|---|---|---|

### Build 2

| # | Prompt (short) | Result | Accept / correct / re-prompt | Why |
|---|---|---|---|---|

## Times

| Build | Start | End | Session id |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
