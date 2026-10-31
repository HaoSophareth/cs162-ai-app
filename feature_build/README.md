# Race Training Planner

A small web app that builds training plans for a 5K, 10K, 15K, half marathon or
marathon, and lets you track your runs in a calendar-style week view. It shows
the whole plan, one week below the other from the first week to race week,
and opens on the current week.

After signing up you answer a few profile questions (sex, age, weight,
height; profile only, not used by plans) and land on a page that prompts you to
create a plan in three short steps: goal, experience, schedule. A summary
page follows (also reachable from the Plans page) with the plan at a glance
and, if you gave a recent race time, an estimated finish time. You can have several plans; the calendar shows the active
one, and the Plans page lets you switch, edit (regenerates) or delete them.
The Profile page shows your running history and lets you delete your account.

Runs entirely on your computer: Python + Flask, data in a local SQLite file.
No API keys, no paid services.

## Run it

Needs Python 3.10 or newer.

```bash
cd feature_build
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --port 5051
```

Then open http://127.0.0.1:5051 and sign up.

Data (accounts, plans, runs) is stored in `instance/planner.db`, which stays
there between restarts. Delete the `instance/` folder to start fresh.
(`instance/training.db`, if you have one, is from an older version and isn't used.)

## Files

- `app.py` - web routes: accounts, profile, plans, week view, runs; database access
- `plan.py` - the plan generator (pure rules, no web or database code)
- `estimates.py` - paces and finish-time estimates for the plan summary
- `templates/` - HTML pages
- `static/style.css` - styling, run-type colours and page transitions

## How the plan is built

Weeks run Monday to Sunday. Week 1 is the week containing the start date.

- **Weekly distance:** new runners aren't asked and start at the beginner level
  (8 km a week). People who have run before start from the km they run per
  week now, at least 12 km. It grows 10% a week, capped at 30/45/50/55/70 km for 5K/10K/15K/half/marathon.
- **Recent race times** don't change the plan (it has no paces). They're used
  on the summary page: the strongest recent race (the one predicting the fastest
  goal time) gives your current pace per km, and the Riegel formula
  (time2 = time1 x (distance2 / distance1)^1.06) estimates your finish. The range
  runs from that prediction (today) to 3% faster (after training); the race-day
  target pace is the middle of the range.
- **Every 4th week** is a cutback week at 75% of the previous level.
- **Taper:** the week before race week drops to about 70% (only for plans of
  8+ weeks); race week has a few short easy runs, none the day before the race.
- **Long run** on the chosen day. It starts from your longest recent run if you
  gave one (otherwise 30% of the first week) and builds evenly to a peak of
  8/14/16/18/32 km (5K/10K/15K/half/marathon), even when that's more than 30% of the week. It adds at most
  3 km a week, so a plan with too few weeks stops short of the peak. Other runs
  aren't longer than the week's long run, so with few run days a week the week's
  total can come in under its target.
- **Balanced weeks:** when the long run would be more than about half of a build
  week, that week's total is raised to twice the long run, even if it grows more
  than 10%. Cutback and taper weeks drop from that raised level. A first week cut
  short by a mid-week start can't always balance, since few runs are left in it.
- **One quality run a week**, alternating tempo and intervals, placed away
  from the long run. The other days are easy runs.
- **Race day** is its own run on the race date.
- **Too-short plans** (fewer than 8/10/10/12/16 weeks) get a warning before saving
  but are still allowed.
