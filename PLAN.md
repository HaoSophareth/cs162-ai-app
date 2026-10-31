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

## Spec change (31 Oct, after the first build)

Sent to both builds as one re-prompt (logged as "spec change"):
- Onboarding after signup is a quick profile only: sex, age, weight (kg), height (cm). Profile only, it does not change the plan.
- Then the dashboard, with a "Create plan" button. Plan questions are asked only when creating a plan: run before? (if yes, optional recent 5k/10k/half/full times), current weekly distance (km), run days (at least 3) + long-run day, race distance, start date, race date.
- A user can have several plans, one active at a time. The calendar shows the active plan; a plans list lets you switch, edit or delete.
- Plan uses current weekly distance (and experience) for its starting point. km only.

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
| 1 | Full spec (feature-wise) | Flask + raw sqlite3 + Flask session login; 2 .py files (app.py 371 lines, plan.py 185); self-tested | TBD after review | |
| 2 | "Page blinks on every click, make it smoother" | Added CSS view transitions + html background (no JS), 19s, 1,611 out tokens | Re-prompt (UX preference, not a bug) | Full page reload on every click because no JS |
| 3 | "Add month view; week view scrollable to next week" (new scope) | Month view + swipe/arrow keys between weeks; added static/calendar.js (~60 lines JS) without being asked; read "scrollable" as sideways swipe; tested on a copy of the DB; 136s, 14,291 out tokens | Accept | First JS in Build 1 (no constraint in feature prompt) |
| 4 | "Done should be a checkbox, crossed out + faded; remove color legend" | Real checkbox (shared template piece), 40% opacity; 120s, 10,660 out tokens | Re-prompt (UI preference) | |
| 5 | Spec change: quick profile onboarding, plan questions only when creating a plan, multiple plans (one active) | Done; new DB file planner.db (old one left); race times saved but unused; 302s, 32,585 out tokens | Re-prompt (spec change) | |
| 6 | Plan form in 3 steps (Step 1 of 3) | Done, 141s, 14,617 out | Re-prompt (UX) | |
| 7 | Goal-first order + plan summary with Riegel finish range + remove Week/Month from top bar | Done; put formula in new estimates.py on its own; 188s, 20,256 out | Re-prompt (new scope + Build 1-only nav fix) | Top-bar duplicate only existed in Build 1 |
| 8 | Week view scrolls down through all plan weeks | Done, checked in a real browser itself; 141s, 12,819 out | Re-prompt (UX) | Replaced its own sideways-swipe JS |
| 9 | Neutral race-time hints + remove month view | Done; deleted calendar.js, so Build 1 has no JS again; 93s, 8,322 out | Re-prompt | Placeholder times biased to fast runners (and repeated) |
| 10 | No plan yet: prompt to create one instead of empty calendar | Done | Re-prompt (UX) | |
| 11 | Forms: times and weekly km only after Yes, no boxes, consistent styling | Done; 162s, 15,667 out | Re-prompt (UX) | |
| 12 | This week rename + longest recent run + long run reaches peak + remove emoji | Done; added itself a cap so no run beats the long run; migrates its own DB on start; still has a small script in week.html since the month-view round; 209s, 19,111 out | Re-prompt (mixed) | Long run made consistent across builds |
| 13 | Race times: Yes/No, then ticked distances | Done; 104s, 10,339 out | Re-prompt (UX) | |
| 14 | All seven days on one line | Done; 34s, 2,482 out | Re-prompt (UX) | |
| 15 | Summary link opens Experience step | Done; 75s, 6,960 out | Re-prompt (BUG, Build 1 only) | |
| 16 | * on mandatory fields, no word optional | Done; 41s, 4,120 out | Re-prompt (UX) | |
| 17 | Calendar and title do nothing on calendar; fixed top bar | Done; 134s, 8,113 out | Re-prompt (UX) | |
| 18 | Running history on profile | Done; 77s, 7,652 out | Re-prompt (new scope) | |
| 19 | Remove username from top bar | Done; 30s, 1,841 out | Re-prompt (UX) | |
| 20 | Export plan button (.ics file) | Done; download checked with curl, Google import not tried yet; 96s, 10,449 out | Re-prompt (new scope) | One link can only add one event |
| 21 | Long run at most about half the week; weekly total may rise past 10% | Session hit the usage limit before finishing or reporting (result is_error); code and README edits were complete and committed; I checked plan shares by running it myself; the build's own tests not confirmed; 79s, 7,605 out | Re-prompt (plan logic) | |
| 22 | Finish the cut-off balanced-weeks prompt | No code change, edits were complete; all 9 of its test suites pass on copies; 49s, 4,978 out | Re-prompt (usage limit) | Limit error did not block this retry |
| 23 | Import hint: own Google calendar, file named after plan | Done; 30s, 2,788 out | Re-prompt (UX) | Google adds imported events to the chosen calendar; a separate calendar gives tick and whole-plan removal |
| 24 | Remove Export plan completely; keep per-run link | Done; 47s, 4,291 out | Re-prompt (scope cut) | One link can't add a whole plan; import steps too complicated for the user |
| 25 | Add 15K race distance | Done; 66s, 6,692 out | Re-prompt (new scope) | Custom distance rejected as too many special cases |
| 26 | 15K peak long run 16 km, not 12 | Done; 22s, 2,279 out | Correct | My 12 km in the prompt was wrong; both builds flagged it |
| 27 | Rename Calendar to Home in top bar | Done; 27s, 1,984 out | Re-prompt (UX) | |
| 28 | Delete account on profile, confirmed by typing username | Done; 113s, 11,365 out | Re-prompt (new scope) | |
| 29 | First-time profile: hide running history and delete account | Done; 29s, 2,525 out | Re-prompt (UX, Build 1 bug) | Build 1 showed them on onboarding |
| 30 | Race times: separate boxes with the colon shown | Done; 168s, 18,027 out | Re-prompt (UX) | Auto-inserting a colon while typing needs JavaScript |
| 31 | Edit plan button on the summary page | Done; 32s, 2,136 out | Re-prompt (UX) | User wants to change the plan straight after seeing its stats |
| 32 | Ticking done keeps the page in place | Done; 79s, 6,925 out | Re-prompt (UX) | Page jumped to the ticked week |
| 33 | Top bar marks the current page | Done; 47s, 3,940 out | Re-prompt (UX) | No signal of current page; smooth page changes work in Chrome, not Arc |
| 34 | training start date can't be in the past | Done; 68s, 6,617 out | Re-prompt (UX) | |
| 35 | training start date defaults to Today | Done; 121s, 11,823 out | Re-prompt (UX) | |

### Build 2

| # | Prompt (short) | Result | Accept / correct / re-prompt | Why |
|---|---|---|---|---|
| 1 | Full spec + how to build | Followed stack/files exactly; 5 .py files (440 lines); self-tested | TBD after review | |
| 2 | Same + "without adding JavaScript" | Same CSS fix as Build 1, 17s, 1,310 out tokens | Re-prompt (UX preference, not a bug) | Same cause |
| 3 | Same + "same stack and file layout, no JavaScript" (new scope) | Month view + two weeks side by side with CSS scroll-snap; refactored week logic into helpers; DELETED the real app database while testing (user data lost, no backup); 100s, 11,147 out tokens | Accept code; incident logged | Data loss = AI test habit; saved a "never delete the DB" memory that Build 1 can also see (shared memory per repo) |
| 4 | Same as Build 1 + "no JavaScript" | Button styled as checkbox (no JS), 45% opacity; 74s, 8,190 out tokens | Re-prompt (UI preference) | |
| 5 | Same spec change + data model/files/routes | Done; profile gate on every page; times hide with CSS only; 207s, 24,728 out tokens | Re-prompt (spec change) | |
| 6 | Same + keep answers in Flask session | Done, 118s, 14,123 out | Re-prompt (UX) | |
| 7 | Goal-first order + plan summary (formula in plan_generator.py) | Done; step order set in one place (PLAN_STEPS); 135s, 15,442 out | Re-prompt (new scope) | |
| 8 | Same + page anchor, no JS | Done; 117s, 12,894 out | Re-prompt (UX) | |
| 9 | Same as Build 1 | Done; 58s, 5,868 out | Re-prompt | |
| 10 | Same as Build 1 | Done | Re-prompt (UX) | |
| 11 | Same + CSS only | Done; 155s, 15,894 out | Re-prompt (UX) | |
| 12 | Same minus emoji + keep rules in plan_generator.py | Done; added itself the same cap; no migration, app broke on old DB until a column was added by hand (data kept); 166s, 16,780 out | Re-prompt (mixed) | Long run made consistent across builds |
| 13 | Race times: Yes/No, then ticked distances | Done; 98s, 10,539 out | Re-prompt (UX) | |
| 14 | All seven days on one line | Done; 50s, 4,038 out | Re-prompt (UX) | |
| 15 | * on mandatory fields, no word optional | Done; 53s, 5,202 out | Re-prompt (UX) | |
| 16 | Calendar and title do nothing on calendar; fixed top bar | Done; 85s, 7,807 out | Re-prompt (UX) | |
| 17 | Running history on profile | Done; 100s, 8,890 out | Re-prompt (new scope) | |
| 18 | Remove username from top bar | Done; 23s, 993 out | Re-prompt (UX) | |
| 19 | Export plan button (.ics file) | Done; download checked with curl, Google import not tried yet; 78s, 8,371 out | Re-prompt (new scope) | One link can only add one event |
| 20 | Long run at most about half the week; weekly total may rise past 10% | Done; 79s, 7,241 out | Re-prompt (plan logic) | |
| 21 | Import hint: own Google calendar, file named after plan | Done; 41s, 3,835 out | Re-prompt (UX) | Google adds imported events to the chosen calendar; a separate calendar gives tick and whole-plan removal |
| 22 | Remove Export plan completely; keep per-run link | Done; 36s, 3,721 out | Re-prompt (scope cut) | One link can't add a whole plan; import steps too complicated for the user |
| 23 | Add 15K race distance | Done; 69s, 7,338 out | Re-prompt (new scope) | Custom distance rejected as too many special cases |
| 24 | 15K peak long run 16 km, not 12 | Done; 17s, 1,286 out | Correct | My 12 km in the prompt was wrong; both builds flagged it |
| 25 | Too-short warning counts weeks like the summary | Done; 32s, 2,874 out | Re-prompt (BUG, Build 2 only) | Found by Build 2 itself |
| 26 | Rename Calendar to Home in top bar | Done; 14s, 907 out | Re-prompt (UX) | |
| 27 | Delete question below an even button row | Done; 54s, 4,835 out | Re-prompt (UI bug, Build 2 only) | CSS-only confirm stretched the buttons; Build 1 uses a JS confirm() |
| 28 | Delete account on profile, confirmed by typing username | Done; 65s, 6,424 out | Re-prompt (new scope) | |
| 29 | First-time profile: hide running history and delete account | Done; 23s, 2,191 out | Unneeded prompt | No code change: Build 2 already hid them; the screenshot was from Build 1 |
| 30 | Race times: separate boxes with the colon shown | Done; 144s, 14,699 out | Re-prompt (UX) | Auto-inserting a colon while typing needs JavaScript |
| 31 | Edit plan button on the summary page | Done; 37s, 3,124 out | Re-prompt (UX) | User wants to change the plan straight after seeing its stats |
| 32 | Ticking done keeps the page in place | Done; 209s, 16,658 out | Re-prompt (UX) | Page jumped to the ticked week |
| 33 | Top bar marks the current page | Done; 52s, 4,884 out | Re-prompt (UX) | No signal of current page; smooth page changes work in Chrome, not Arc |
| 34 | training start date can't be in the past | Done; 59s, 5,410 out | Re-prompt (UX) | |
| 35 | training start date defaults to Today | Done; 88s, 8,197 out | Re-prompt (UX) | |

## Manual edits (not by the build sessions)

- Both `templates/base.html`: added "· Build 1 (feature-wise)" / "· Build 2 (engineering-wise)" next to the header title and in the tab title, so the demo video shows which build is which. Edited by hand from the planning session, not an AI build prompt.
- Both `app.py`: gave each build its own session cookie name (SESSION_COOKIE_NAME), because running both on one computer logged the user out of the other. Edited by hand from the planning session, not an AI build prompt.

## Notes

- Blink: smooth page changes work in Chrome, not Arc (user confirmed). Use Chrome for the demo.
- Ticking done (prompt 32): Build 1 used background JavaScript; Build 2's no-JS rule forced one iframe per week, which adds Back-button history steps and fixed week heights. Build 1 JavaScript is now in at least 3 places: check against the class-covered rule.

- Prompts 13 onward are one change per prompt, one commit per build. Build 1 total differs by one because the summary link bug only existed there.
- Running both builds on 127.0.0.1 makes them overwrite each other's login cookie (same host, same cookie name). Use 127.0.0.1:5051 and localhost:5050.

- Build 2 database: added `longest_run_km` by hand with ALTER TABLE after prompt 12 instead of recreating it. Local data only.
- Build 1 still has a 3-line script in week.html (scroll to current week). Earlier note that it had no JS was wrong.

- Blink fix (row 2) didn't seem to work in Arc (default browser); likely needs Chrome 126+/Safari 18.2+. Check in Chrome before counting it as failed.
- Git history rebuilt from transcripts after the fact: one commit per prompt/manual edit (de089b9..4b12ce3).

- Local-only dev change (never committed, git skip-worktree): login form prefilled with phareth/123456 in both builds. Remove/undo before zipping (zip from git, so it's excluded anyway).

## Times

Both run as headless `claude -p` sessions (Opus 5.5) started from the planning session, at the same time. Tokens (from result JSON): Build 1 = 40 in, 67,702 cache write, 1,160,446 cache read, 31,708 out, 33 turns. Build 2 = 36 in, 61,449 cache write, 1,019,169 cache read, 26,687 out, 33 turns.


| Build | Start | End | Session id |
|---|---|---|---|
| 1 | 15:08:11 UTC | 15:13:21 UTC (5m 10s) | af4e88fc-883e-4236-bb50-a4ab62fc1759 |
| 2 | 15:08:11 UTC | 15:12:13 UTC (4m 2s) | 23c947a3-0d0d-4733-b9a1-52de17b00f2f |

## Handoff: where things stand (saved 31 Oct, about 13:35 local)

If a new session picks this up: read this section, then the logs above. `process/prompts/` has every prompt sent after the first build's planning, `process/results/` has every result JSON (tokens, time, the build's own summary).

### How we run builds
- Each build is one resumed headless session, run from its own folder:
  `claude -p "$(cat prompt)" --resume <session_id> --model claude-opus-5-5 --output-format json --permission-mode acceptEdits --allowedTools "Bash Read Write Edit Glob Grep" > result.json 2>&1 < /dev/null`
- Build 1 session af4e88fc-883e-4236-bb50-a4ab62fc1759, Build 2 session 23c947a3-0d0d-4733-b9a1-52de17b00f2f. Never start fresh sessions for them.
- One change per prompt. One commit per build per prompt, Build 1 and Build 2 separately. Commit message style: `Build 1: ... (re-prompt)`. Commits under the user's name only, no Co-Authored-By. Push to HaoSophareth/cs162-ai-app main (HaoSophareth account only, never shao@better.com).
- Same feature wording for both builds. Build 2 also gets the how: same stack and file layout, no JavaScript. Fix something in only one build if only that build has the problem.
- Build 1 prompts stay plain: "my data", "login pages", not `instance/` or "templates".
- Each prompt ends with: test on a copy, don't touch the login and signup pages.
- A build can only take one prompt at a time. Queue the rest.
- After every prompt: read the result, commit, restart both servers, then push and log. Servers crash on pages whose template changed before Python restarted (seen once on Plans), so restart when a prompt finishes.

### Local running
- Build 1: http://127.0.0.1:5051 (`cd feature_build && venv/bin/flask --app app run --port 5051`). Data in instance/planner.db.
- Build 2: http://localhost:5050 (`cd engineering_build && venv/bin/flask --app app run --port 5050`). Data in instance/running.db.
- Each build now has its own login cookie name, so any address works.
- Port 5001 is skills_marketplace, don't use it.
- Test account phareth / 123456 on both. Login form is prefilled by local-only edits to feature_build/templates/auth.html and engineering_build/templates/login.html, hidden from git with skip-worktree. Git won't notice changes there, so check them before commits. Zip from git so the prefill is left out.

### User decisions so far
- Blink: better now, accepted.
- Long run consistent in both: builds to the race peak, may exceed 30%. Weekly total may rise so the long run stays about half the week or less.
- Longest recent run: added, optional, after Yes.
- 🏃 emoji removed from Build 1. Username removed from top bars.
- Top-left title and Calendar both go to the calendar; do nothing when already there; top bar always fixed.
- Race times: Yes/No first, then ticked distances, then only those boxes.
- `*` on mandatory fields, never the word optional.
- Running history on profile is read-only, derived from existing data. No time recorded per run.
- Export plan was built, then removed at the user's request (import too complicated, one link can't add a whole plan). Per-run Add to Google Calendar link stays.
- User rejected cheap models: builds use Claude Opus 5.5.

### Token and time totals (verified)
Summed from every result file and matched exactly against each build's transcript (per API call, deduplicated by message id). Result usage is per prompt, not cumulative. `total_cost_usd` IS cumulative per session, so the final value is the total; the earlier $7.44 figure was only a midpoint.

| | Build 1 | Build 2 | Build 2 vs Build 1 |
|---|---|---|---|
| Prompts | 26 | 25 | -1 |
| AI working time | 45m 54s | 36m 25s | -21% |
| Input | 394 | 330 | |
| Cache write | 972,051 | 823,553 | -15% |
| Cache read | 55,204,016 | 42,860,808 | -22% |
| Output | 267,125 | 229,092 | -14% |
| All tokens | 56,443,586 | 43,913,783 | -22% |
| Reported cost | $24.16 | $19.74 | -18% |

Both builds together: 100,357,369 tokens, $43.91 equivalent. Recomputed from process/results after the 15K round; add any later prompts. Excludes the planning sessions. Start to finish on the clock was 83 minutes for both, because they ran side by side while the user tested. Build 1 has one extra prompt: it had the link bug and the usage-limit retry, Build 2 had the too-short warning bug.

### Interrupted prompt
Build 1 prompt 21 (balanced weeks) ended with "You've hit your 5-hour limit, resets 6pm". Commit b3ca87b holds its edits. Retried as prompt 22 at about 14:02, which was not blocked; it confirmed the edits were complete and tests pass.

### Report points
- Build 1: Flask, raw sqlite3, Flask sessions, split on its own into app.py, plan.py, estimates.py, calendar_export.py; still long app.py. Structure from AI defaults. Build 2: app.py, models.py, auth.py, main.py, plan_generator.py from the prompt.
- Build 1 first build: 5m 10s, 31,708 out. Build 2: 4m 2s, 26,687 out. Later rounds: Build 2 is often faster and cheaper but NOT every time (forms 15,667 vs 15,894; stacked weeks 12,819 vs 12,894).
- Bugs/incidents: Build 2 too-short warning off by one week (found by itself). Build 2 deleted the real database once while testing (no backup). Build 1 only: summary link went to the wrong step, top-bar duplicate. Build 2's new column broke the old database, fixed by hand with ALTER TABLE, backup kept; Build 1 migrates itself on start.
- Both builds independently added a rule capping other runs at the long run, and found the 30% rule contradicts the peak distances.
- JavaScript: Build 1 added calendar.js then removed it; still has a 3-line script in templates/week.html and an inline confirm() on Delete (check for more before the zip). Build 2 has none. Check against class-covered rule.
- Be honest in the report: some Build 1 re-prompts used engineering words (`instance/`, templates, Riegel formula); Build 2 saved a memory note Build 1 could see; prompts were refined with AI, not written alone; git history before de089b9..4b12ce3 rebuilt from transcripts; title labels are manual edits.
- Free tier: user hit the 5-hour usage limit at 1:02 PM and the builds report $43.91 in total ($24.16 and $19.74), so tip 4 applies: list alternatives (Claude.ai free, Copilot via Education Pack, DeepSeek, Gemini free) and why not used.

### Remaining work
1. (Export removed, no import to test.)
2. Fill "TBD after review" in row 1 of both logs.
3. Decide on Build 1's week.html script. Name a public plan source in both READMEs (spec asked for one, e.g. Hal Higdon, never prompted). Confirm no test files in build folders.
4. Separation-of-concerns map, one line per file, for both.
5. Heuristics counts with numbers for the report.
6. PDF report, 800 words max: cost/time, separation of concerns, conclusion on which is better to build, maintain, run; model details.
7. Zip from git: both apps with only needed files, run instructions, all transcripts (both builds + planning sessions). Remove DEV ONLY login prefill by zipping from git.
8. Demo video of both apps showing all features, using the two addresses above.
