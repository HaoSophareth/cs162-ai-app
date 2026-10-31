# Race Training Planner

A small web app that builds training plans for a 5K, 10K, half marathon or
marathon, and lets you track your runs in a calendar-style week or month view. Swipe
sideways (trackpad or touch) or press ← / → to move to the previous or next
week or month.

After signing up you answer a few profile questions (sex, age, weight,
height; profile only, not used by plans) and land on an empty calendar. Create
a plan from there. You can have several plans; the calendar shows the active
one, and the Plans page lets you switch, edit (regenerates) or delete them.

Runs entirely on your computer: Python + Flask, data in a local SQLite file.
No API keys, no paid services.

## Run it

Needs Python 3.10 or newer.

```bash
cd feature_build
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 and sign up.

Data (accounts, plans, runs) is stored in `instance/planner.db`, which stays
there between restarts. Delete the `instance/` folder to start fresh.
(`instance/training.db`, if you have one, is from an older version and isn't used.)

## Files

- `app.py` - web routes: accounts, profile, plans, week/month views, runs; database access
- `plan.py` - the plan generator (pure rules, no web or database code)
- `templates/` - HTML pages
- `static/style.css` - styling, run-type colours and page transitions
- `static/calendar.js` - swipe / arrow-key navigation between weeks and months

## How the plan is built

Weeks run Monday to Sunday. Week 1 is the week containing the start date.

- **Weekly distance** starts from the km you run per week now, kept between
  8 and 15 km for new runners and at least 12 km for people who have run
  before. It grows 10% a week, capped at 30/45/55/70 km for 5K/10K/half/marathon.
- **Recent race times** are saved with the plan for reference; they don't
  change the plan (it has no paces).
- **Every 4th week** is a cutback week at 75% of the previous level.
- **Taper:** the week before race week drops to about 70% (only for plans of
  8+ weeks); race week has a few short easy runs, none the day before the race.
- **Long run** on the chosen day. It starts at 30% of the week and builds
  steadily (at most 3 km more per week) to a peak of 8/14/18/32 km. On
  beginner-sized weekly totals 30% alone would never reach those peaks, so
  late in a plan the long run becomes a bigger share of the week, as in common
  beginner plans.
- **One quality run a week**, alternating tempo and intervals, placed away
  from the long run. The other days are easy runs.
- **Race day** is its own run on the race date.
- **Too-short plans** (fewer than 8/10/12/16 weeks) get a warning before saving
  but are still allowed.
