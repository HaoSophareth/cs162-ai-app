"""Race training planner: a small Flask app backed by a SQLite file."""

import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import calendar_export
import estimates
import plan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "instance")
# planner.db replaced training.db when plans changed (profile + multiple plans).
# The old file is left alone; it just isn't used any more.
DB_PATH = os.path.join(DATA_DIR, "planner.db")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_VALUES = [str(i) for i in range(7)]
RUN_TYPES = {"easy": "Easy", "long": "Long run", "tempo": "Tempo", "intervals": "Intervals", "race": "Race"}
# Optional recent race times asked when creating a plan: (column, label).
# Format hint shown in each box (either format is accepted for any distance).
TIME_FORMATS = {"time_5k": "mm:ss", "time_10k": "mm:ss", "time_half": "h:mm:ss", "time_marathon": "h:mm:ss"}
RACE_TIMES = [("time_5k", "5K"), ("time_10k", "10K"), ("time_half", "Half marathon"),
              ("time_marathon", "Marathon")]

app = Flask(__name__)


def load_secret_key():
    # Kept in a file so logins survive a restart of the app.
    path = os.path.join(DATA_DIR, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


# ---------- Database ----------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    -- profile, filled in right after signup (not used by the plan)
    sex TEXT,
    age INTEGER,
    weight_kg REAL,
    height_cm REAL,
    active_plan_id INTEGER       -- the plan the calendar shows, or NULL
);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    experience TEXT NOT NULL,    -- "new" or "experienced"
    time_5k TEXT,                -- optional recent race times, "mm:ss" or "h:mm:ss"
    time_10k TEXT,
    time_half TEXT,
    time_marathon TEXT,
    weekly_km REAL NOT NULL,     -- weekly distance when the plan was made
    longest_km REAL,             -- optional longest recent run
    run_days TEXT NOT NULL,      -- weekday numbers, e.g. "0,2,5" (Monday = 0)
    long_day INTEGER NOT NULL,
    distance TEXT NOT NULL,
    start_date TEXT NOT NULL,
    race_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    user_id INTEGER NOT NULL REFERENCES users(id),  -- copied from the plan, to keep ownership checks simple
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    distance_km REAL NOT NULL,
    description TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    done INTEGER NOT NULL DEFAULT 0
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)
        # Databases made before this column existed get it added, keeping their data.
        columns = [row[1] for row in db.execute("PRAGMA table_info(plans)")]
        if "longest_km" not in columns:
            db.execute("ALTER TABLE plans ADD COLUMN longest_km REAL")


def get_user():
    return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def get_active_plan():
    return get_db().execute(
        "SELECT plans.* FROM plans JOIN users ON users.active_plan_id = plans.id"
        " WHERE users.id = ? AND plans.user_id = users.id",
        (session["user_id"],),
    ).fetchone()


# Filtering by user_id means nobody can open another user's plan or run by URL.

def get_own_plan(plan_id):
    row = get_db().execute("SELECT * FROM plans WHERE id = ? AND user_id = ?",
                           (plan_id, session["user_id"])).fetchone()
    if row is None:
        abort(404)
    return row


def get_own_run(run_id):
    run = get_db().execute("SELECT * FROM runs WHERE id = ? AND user_id = ?",
                           (run_id, session["user_id"])).fetchone()
    if run is None:
        abort(404)
    return run


def save_plan(values, plan_id=None):
    """Create a plan (plan_id=None) or update one, and (re)generate its runs.

    A new plan becomes the active one. Returns the plan id.
    """
    user_id = session["user_id"]
    db = get_db()
    columns = {
        "experience": values["experience"],
        **{key: values[key] for key, _ in RACE_TIMES},
        "weekly_km": values["weekly_km"],
        "longest_km": values["longest_km"],
        "run_days": ",".join(map(str, values["run_days"])),
        "long_day": values["long_day"],
        "distance": values["distance"],
        "start_date": values["start_date"].isoformat(),
        "race_date": values["race_date"].isoformat(),
    }
    if plan_id is None:
        cursor = db.execute(
            f"INSERT INTO plans (user_id, {', '.join(columns)}) VALUES (?{', ?' * len(columns)})",
            (user_id, *columns.values()),
        )
        plan_id = cursor.lastrowid
        db.execute("UPDATE users SET active_plan_id = ? WHERE id = ?", (plan_id, user_id))
    else:
        db.execute(
            f"UPDATE plans SET {', '.join(name + ' = ?' for name in columns)} WHERE id = ? AND user_id = ?",
            (*columns.values(), plan_id, user_id),
        )

    db.execute("DELETE FROM runs WHERE plan_id = ? AND user_id = ?", (plan_id, user_id))
    runs = plan.generate_plan(values["experience"], values["weekly_km"], values["run_days"],
                              values["long_day"], values["distance"],
                              values["start_date"], values["race_date"], values["longest_km"])
    db.executemany(
        "INSERT INTO runs (plan_id, user_id, date, type, distance_km, description) VALUES (?, ?, ?, ?, ?, ?)",
        [(plan_id, user_id, r["date"].isoformat(), r["type"], r["distance_km"], r["description"])
         for r in runs],
    )
    db.commit()  # one commit, so a plan is never half-replaced
    return plan_id


# ---------- Helpers ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # The second check catches a leftover login for an account that no
        # longer exists (e.g. after switching to a fresh database).
        if "user_id" not in session or get_user() is None:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def parse_number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def run_event_text(run):
    """A run's calendar title and details, for the Google link and the plan export."""
    title = f"{RUN_TYPES[run['type']]} - {run['distance_km']:g} km"
    details = run["description"] + (f"\n\nNotes: {run['notes']}" if run["notes"] else "")
    return title, details


def google_calendar_link(run):
    day = date.fromisoformat(run["date"])
    title, details = run_event_text(run)
    params = {
        "action": "TEMPLATE",
        "text": title,
        # All-day event: the end date is exclusive, so it's the next day.
        "dates": f"{day:%Y%m%d}/{day + timedelta(days=1):%Y%m%d}",
        "details": details,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


@app.context_processor
def template_helpers():
    return {"RUN_TYPES": RUN_TYPES, "WEEKDAYS": WEEKDAYS, "DISTANCES": plan.DISTANCES,
            "RACE_TIMES": RACE_TIMES, "TIME_FORMATS": TIME_FORMATS}


@app.template_filter("nice_date")
def nice_date(value):
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return f"{value:%a, %b} {value.day}, {value.year}"


# ---------- Accounts ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        if not username or len(password) < 6:
            flash("Choose a username and a password of at least 6 characters.", "error")
        elif db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            flash("That username is taken.", "error")
        else:
            cursor = db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                                (username, generate_password_hash(password)))
            db.commit()
            session.clear()
            session["user_id"] = cursor.lastrowid
            return redirect(url_for("profile"))
    return render_template("auth.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("week"))
        flash("Wrong username or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Profile ----------

def running_history(user_id):
    """Read-only summary for the profile page, from all the user's plans and runs
    (active or not). Returns None when there is nothing to show yet."""
    db = get_db()
    plan_rows = db.execute("SELECT * FROM plans WHERE user_id = ?", (user_id,)).fetchall()

    # Compared as durations: as text, "1:00:00" would count as faster than "59:00".
    best_times = []
    for key, label in RACE_TIMES:
        seconds = [estimates.parse_time(p[key]) for p in plan_rows if p[key]]
        seconds = [s for s in seconds if s > 0]
        best_times.append({"label": label, "time": estimates.format_time(min(seconds)) if seconds else None})

    longest_entered = max((p["longest_km"] for p in plan_rows if p["longest_km"]), default=None)
    done = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(distance_km), 0) AS total, MAX(distance_km) AS longest"
        " FROM runs WHERE user_id = ? AND done", (user_id,),
    ).fetchone()

    if not (longest_entered or done["count"] or any(b["time"] for b in best_times)):
        return None
    return {"best_times": best_times, "longest_entered": longest_entered, "done": done}


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_user()
    first_time = user["sex"] is None

    if request.method == "POST":
        values = {
            "sex": request.form.get("sex"),
            "age": parse_number(request.form.get("age")),
            "weight_kg": parse_number(request.form.get("weight_kg")),
            "height_cm": parse_number(request.form.get("height_cm")),
        }
        errors = []
        if values["sex"] not in ("male", "female"):
            errors.append("Pick male or female.")
        if values["age"] is None or not 10 <= values["age"] <= 100:
            errors.append("Age must be between 10 and 100.")
        if values["weight_kg"] is None or not 25 <= values["weight_kg"] <= 250:
            errors.append("Weight must be between 25 and 250 kg.")
        if values["height_cm"] is None or not 100 <= values["height_cm"] <= 250:
            errors.append("Height must be between 100 and 250 cm.")
        if not errors:
            db = get_db()
            db.execute("UPDATE users SET sex = ?, age = ?, weight_kg = ?, height_cm = ? WHERE id = ?",
                       (values["sex"], int(values["age"]), values["weight_kg"], values["height_cm"],
                        user["id"]))
            db.commit()
            flash("Profile saved.", "success")
            return redirect(url_for("week"))
        for error in errors:
            flash(error, "error")
        return render_template("profile.html", values=request.form, first_time=first_time,
                               history=running_history(user["id"]))

    return render_template("profile.html", values=user, first_time=first_time,
                           history=running_history(user["id"]))


def profile_required(view):
    """Send users who skipped the profile questions back to them first."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_user()["sex"] is None:
            return redirect(url_for("profile"))
        return view(*args, **kwargs)
    return wrapped


# ---------- Plans ----------

TIME_PATTERN = re.compile(r"^(\d{1,2}:)?[0-5]?\d:[0-5]\d$")  # mm:ss or h:mm:ss


# The plan form is split into three steps. Each step is a normal form post;
# answers from the other steps travel along as hidden fields, so nothing is
# stored until the last step creates (or regenerates) the plan.
PLAN_STEPS = {1: "Goal", 2: "Experience", 3: "Schedule"}
GOAL, EXPERIENCE, SCHEDULE = 1, 2, 3


def read_plan_form(form):
    """Return (values, errors) from the submitted plan form.

    errors maps each step number to that step's error messages.
    """
    values = {
        "experience": form.get("experience"),
        "weekly_km": parse_number(form.get("weekly_km")),
        "longest_km": parse_number(form.get("longest_km")),
        "run_days": sorted({int(d) for d in form.getlist("run_days") if d in WEEKDAY_VALUES}),
        "long_day": int(form["long_day"]) if form.get("long_day", "").isdigit() else -1,
        "distance": form.get("distance"),
        "start_date": parse_date(form.get("start_date")),
        "race_date": parse_date(form.get("race_date")),
    }
    errors = {GOAL: [], EXPERIENCE: [], SCHEDULE: []}
    if values["experience"] not in plan.START_KM_LIMITS:
        errors[EXPERIENCE].append("Tell us whether you have run before.")

    # Race times are asked of people who have run before, in two parts: do you
    # have one, then which distances. Only a ticked distance after a "yes" counts,
    # so anything typed and then hidden is ignored.
    ran_before = values["experience"] == "experienced"
    values["has_times"] = form.get("has_times") if ran_before else None
    ticked = form.getlist("time_distances") if values["has_times"] == "yes" else []
    values["time_distances"] = ticked
    if ran_before and values["has_times"] not in ("yes", "no"):
        errors[EXPERIENCE].append("Tell us whether you have a recent race time.")
    if values["has_times"] == "yes" and not any(key in ticked for key, _ in RACE_TIMES):
        errors[EXPERIENCE].append("Tick the distance of your race time, or answer No.")
    for key, label in RACE_TIMES:
        text = form.get(key, "").strip()
        values[key] = text if key in ticked and text else None
        if key in ticked and not text:
            errors[EXPERIENCE].append(f"Enter your {label} time, or untick it.")
        elif values[key] and not TIME_PATTERN.match(text):
            errors[EXPERIENCE].append(f"Write your {label} time as {TIME_FORMATS[key]}.")

    if values["experience"] == "new":
        # New runners aren't asked; 0 km makes the plan start at the
        # beginner level (the lowest starting volume in plan.py).
        values["weekly_km"] = 0.0
        values["longest_km"] = None
    else:
        if values["weekly_km"] is None or not 0 <= values["weekly_km"] <= 200:
            errors[EXPERIENCE].append("Enter how many km you run per week now.")
        # Optional, but text that isn't a sensible distance shouldn't pass silently.
        longest_text = form.get("longest_km", "").strip()
        if longest_text and (values["longest_km"] is None or not 0 < values["longest_km"] <= 100):
            errors[EXPERIENCE].append("Longest recent run must be between 0 and 100 km, or left empty.")
    if len(values["run_days"]) < 3:
        errors[SCHEDULE].append("Pick at least 3 days you can run.")
    if values["long_day"] not in values["run_days"]:
        errors[SCHEDULE].append("The long-run day must be one of your running days.")
    if values["distance"] not in plan.DISTANCES:
        errors[GOAL].append("Pick a race distance.")
    if not values["start_date"] or not values["race_date"]:
        errors[GOAL].append("Enter both a start date and a race date.")
    elif values["race_date"] <= values["start_date"]:
        errors[GOAL].append("The race date must be after the start date.")
    return values, errors


def short_plan_key(values):
    """Identifies the goal the user confirmed despite the too-short warning,
    so changing the distance or dates afterwards shows the warning again."""
    return f"{values['distance']}|{values['start_date']}|{values['race_date']}"


def handle_plan_form(existing=None):
    """Shared by "create plan" and "edit plan". existing is the plan being edited."""
    def show(step, values, short_warning=None):
        # The too-short confirmation travels with the other hidden answers;
        # when the warning is on screen, continuing confirms the goal shown.
        # Editing can open past the goal step (?step=2); that saved goal was
        # already accepted, so it only warns again if the goal is changed.
        opened_past_goal = request.method == "GET" and step > GOAL
        confirm = (short_plan_key(values) if short_warning or opened_past_goal
                   else request.form.get("confirm_short", ""))
        return render_template("plan_form.html", step=step, steps=PLAN_STEPS, values=values,
                               existing=existing, short_warning=short_warning, confirm=confirm)

    if request.method == "GET":
        if existing:
            values = dict(existing)
            values["run_days"] = [int(d) for d in existing["run_days"].split(",")]
            # The race time answers aren't stored; they follow from the saved times.
            values["time_distances"] = [key for key, _ in RACE_TIMES if existing[key]]
            if existing["experience"] == "experienced":
                values["has_times"] = "yes" if values["time_distances"] else "no"
        else:
            values = {"experience": "", "weekly_km": None, "longest_km": None, "has_times": None,
                      "time_distances": [], "run_days": [1, 3, 5], "long_day": 5,
                      "distance": "5k", "start_date": date.today(),
                      "race_date": date.today() + timedelta(weeks=10)}
        # Only an existing plan has answers for the steps before the one opened.
        wanted = request.args.get("step")
        return show(int(wanted) if existing and wanted in ("1", "2", "3") else GOAL, values)

    step = int(request.form["step"]) if request.form.get("step") in ("1", "2", "3") else 1
    values, errors = read_plan_form(request.form)

    # Back never checks anything, so half-filled answers are kept as they are.
    if request.form.get("action") == "back":
        return show(max(step - 1, 1), values)

    if errors[step]:
        for error in errors[step]:
            flash(error, "error")
        return show(step, values)

    # Too-short plans are allowed, but only after the user has seen the warning.
    # It shows on the goal step, right where the dates are chosen.
    def needs_short_warning():
        return (plan.is_too_short(values["distance"], values["start_date"], values["race_date"])
                and request.form.get("confirm_short") != short_plan_key(values))

    def show_short_warning():
        weeks = plan.count_weeks(values["start_date"], values["race_date"])
        label, _, recommended = plan.DISTANCES[values["distance"]]
        return show(GOAL, values, short_warning=(weeks, label, recommended))

    if step == GOAL and needs_short_warning():
        return show_short_warning()
    if step < 3:
        return show(step + 1, values)

    # Last step: every step should be valid by now, but check in case a
    # hidden field was tampered with, and send the user to the step to fix.
    for earlier in (GOAL, EXPERIENCE):
        if errors[earlier]:
            for error in errors[earlier]:
                flash(error, "error")
            return show(earlier, values)
    if needs_short_warning():
        return show_short_warning()

    plan_id = save_plan(values, existing["id"] if existing else None)
    flash("Your plan was regenerated." if existing else "Your training plan is ready.", "success")
    return redirect(url_for("plan_summary", plan_id=plan_id))


@app.route("/plans")
@login_required
@profile_required
def plans():
    rows = get_db().execute(
        "SELECT plans.*,"
        " (SELECT COUNT(*) FROM runs WHERE runs.plan_id = plans.id) AS run_count,"
        " (SELECT COUNT(*) FROM runs WHERE runs.plan_id = plans.id AND done) AS done_count"
        " FROM plans WHERE user_id = ? ORDER BY race_date",
        (session["user_id"],),
    ).fetchall()
    weeks = {p["id"]: plan.count_weeks(date.fromisoformat(p["start_date"]), date.fromisoformat(p["race_date"]))
             for p in rows}
    return render_template("plans.html", plans=rows, weeks=weeks, active_id=get_user()["active_plan_id"])


@app.route("/plans/new", methods=["GET", "POST"])
@login_required
@profile_required
def new_plan():
    return handle_plan_form()


@app.route("/plans/<int:plan_id>")
@login_required
def plan_summary(plan_id):
    p = get_own_plan(plan_id)
    start = date.fromisoformat(p["start_date"])
    race = date.fromisoformat(p["race_date"])
    runs = get_db().execute("SELECT * FROM runs WHERE plan_id = ? AND user_id = ? ORDER BY date",
                            (plan_id, session["user_id"])).fetchall()

    # Weekly totals of training runs (the race itself left out, so race week
    # doesn't show up as the "peak").
    weekly = {}
    for run in runs:
        if run["type"] != "race":
            monday = plan.monday_of(date.fromisoformat(run["date"]))
            weekly[monday] = weekly.get(monday, 0) + run["distance_km"]
    # Week 1 is partial when the plan starts mid-week, so "starting" weekly
    # km is the first full week.
    first_full_week = plan.monday_of(start) + timedelta(weeks=0 if start.weekday() == 0 else 1)
    training = [r for r in runs if r["type"] != "race"]

    goal_km = plan.RACE_KM[p["distance"]]
    recent = [(label, plan.RACE_KM[key.removeprefix("time_")], p[key]) for key, label in RACE_TIMES]
    best = estimates.best_recent_race(recent, goal_km)

    return render_template(
        "summary.html",
        p=p,
        weeks=plan.count_weeks(start, race),
        run_days=[WEEKDAYS[int(d)] for d in p["run_days"].split(",")],
        long_day=WEEKDAYS[p["long_day"]],
        start_km=weekly.get(first_full_week, 0),
        peak_km=max(weekly.values(), default=0),
        longest_km=max((r["distance_km"] for r in training), default=0),
        total_km=sum(r["distance_km"] for r in runs),
        goal_km=goal_km,
        best=best,
        estimate=estimates.finish_estimate(best, goal_km) if best else None,
        is_active=get_user()["active_plan_id"] == plan_id,
    )


@app.route("/plans/<int:plan_id>/export")
@login_required
def export_plan(plan_id):
    p = get_own_plan(plan_id)
    runs = get_db().execute("SELECT * FROM runs WHERE plan_id = ? AND user_id = ? ORDER BY date, id",
                            (plan_id, session["user_id"])).fetchall()
    events = []
    for run in runs:
        title, details = run_event_text(run)
        events.append({"uid": f"run-{run['id']}@race-training-planner", "date": date.fromisoformat(run["date"]),
                       "title": title, "details": details})
    race = plan.DISTANCES[p["distance"]][0]
    text = calendar_export.build_calendar(f"{race} training plan", events)
    filename = f"{race.lower().replace(' ', '-')}-plan-{p['race_date']}.ics"
    return Response(text, mimetype="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.route("/plans/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
def edit_plan(plan_id):
    return handle_plan_form(get_own_plan(plan_id))


@app.route("/plans/<int:plan_id>/activate", methods=["POST"])
@login_required
def activate_plan(plan_id):
    get_own_plan(plan_id)
    db = get_db()
    db.execute("UPDATE users SET active_plan_id = ? WHERE id = ?", (plan_id, session["user_id"]))
    db.commit()
    flash("Active plan switched.", "success")
    return redirect(url_for("week"))


@app.route("/plans/<int:plan_id>/delete", methods=["POST"])
@login_required
def delete_plan(plan_id):
    get_own_plan(plan_id)
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM runs WHERE plan_id = ? AND user_id = ?", (plan_id, user_id))
    db.execute("DELETE FROM plans WHERE id = ? AND user_id = ?", (plan_id, user_id))
    if get_user()["active_plan_id"] == plan_id:
        # The active plan is gone: fall back to the most recently created one, if any.
        latest = db.execute("SELECT id FROM plans WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                            (user_id,)).fetchone()
        db.execute("UPDATE users SET active_plan_id = ? WHERE id = ?",
                   (latest["id"] if latest else None, user_id))
    db.commit()
    flash("Plan deleted.", "success")
    return redirect(url_for("plans"))


# ---------- Week view ----------

def load_runs(active, first_day, last_day):
    """Runs of the active plan between two dates (inclusive)."""
    return get_db().execute(
        "SELECT * FROM runs WHERE plan_id = ? AND user_id = ? AND date BETWEEN ? AND ? ORDER BY date, id",
        (active["id"], session["user_id"], first_day.isoformat(), last_day.isoformat()),
    ).fetchall()


def build_days(first_day, count, runs):
    """A list of {date, runs} for `count` days starting at first_day."""
    days = []
    for offset in range(count):
        day = first_day + timedelta(days=offset)
        days.append({"date": day, "runs": [r for r in runs if r["date"] == day.isoformat()]})
    return days


def plan_week_number(monday, active):
    """Week number within the active plan, or None if this week is outside it."""
    start = date.fromisoformat(active["start_date"])
    race = date.fromisoformat(active["race_date"])
    number = (monday - plan.monday_of(start)).days // 7 + 1
    return number if 1 <= number <= plan.count_weeks(start, race) else None


@app.route("/")
@login_required
@profile_required
def week():
    """The whole active plan as weeks stacked top to bottom, from the first
    week to race week. The page opens scrolled to the current week, or to the
    week of ?week=<date> (used by "back to week" links)."""
    active = get_active_plan()
    if active is None:
        # Nothing to show yet: a simple page that points to "Create plan".
        return render_template("no_plan.html")

    today = date.today()
    target = plan.monday_of(parse_date(request.args.get("week")) or today)
    first = plan.monday_of(date.fromisoformat(active["start_date"]))
    last = plan.monday_of(date.fromisoformat(active["race_date"]))
    # Include runs the user moved outside the plan's dates.
    dates = get_db().execute("SELECT MIN(date), MAX(date) FROM runs WHERE plan_id = ? AND user_id = ?",
                             (active["id"], session["user_id"])).fetchone()
    if dates[0]:
        first = min(first, plan.monday_of(date.fromisoformat(dates[0])))
        last = max(last, plan.monday_of(date.fromisoformat(dates[1])))
    # Before the plan, open on its first week; after race day, on race week.
    target = min(max(target, first), last)

    runs = load_runs(active, first, last + timedelta(days=6))
    weeks = []
    monday = first
    while monday <= last:
        days = build_days(monday, 7, [r for r in runs if monday.isoformat() <= r["date"]
                                      <= (monday + timedelta(days=6)).isoformat()])
        week_runs = [r for day in days for r in day["runs"]]
        weeks.append({
            "monday": monday,
            "sunday": monday + timedelta(days=6),
            "number": plan_week_number(monday, active),
            "days": days,
            "planned_km": sum(r["distance_km"] for r in week_runs),
            "done_km": sum(r["distance_km"] for r in week_runs if r["done"]),
        })
        monday += timedelta(weeks=1)

    return render_template("week.html", weeks=weeks, target=target, today=today,
                           this_monday=plan.monday_of(today), active=active)


# ---------- Runs ----------

@app.route("/runs/<int:run_id>")
@login_required
def run_detail(run_id):
    run = get_own_run(run_id)
    return render_template("run.html", run=run, calendar_link=google_calendar_link(run))


@app.route("/runs/<int:run_id>/edit", methods=["GET", "POST"])
@login_required
def edit_run(run_id):
    run = get_own_run(run_id)
    if request.method == "POST":
        new_date = parse_date(request.form.get("date"))
        distance = parse_number(request.form.get("distance_km"))
        if new_date is None:
            flash("Enter a valid date.", "error")
        elif distance is None or not 0 < distance <= 100:
            flash("Distance must be a number of km between 0 and 100.", "error")
        else:
            distance = round(distance, 1)
            # Rewrite the workout text so it matches the new distance.
            race_distance = get_own_plan(run["plan_id"])["distance"]
            description = plan.describe(run["type"], distance, race_distance)
            db = get_db()
            db.execute("UPDATE runs SET date = ?, distance_km = ?, description = ?, notes = ?"
                       " WHERE id = ? AND user_id = ?",
                       (new_date.isoformat(), distance, description,
                        request.form.get("notes", "").strip(), run_id, session["user_id"]))
            db.commit()
            flash("Run updated.", "success")
            return redirect(url_for("run_detail", run_id=run_id))
    return render_template("edit_run.html", run=run)


@app.route("/runs/<int:run_id>/done", methods=["POST"])
@login_required
def set_done(run_id):
    run = get_own_run(run_id)
    # The form sends the checkbox's new state; an unticked box sends nothing.
    done = 1 if request.form.get("done") else 0
    db = get_db()
    db.execute("UPDATE runs SET done = ? WHERE id = ? AND user_id = ?", (done, run_id, session["user_id"]))
    db.commit()
    # Go back to wherever the checkbox was clicked.
    next_page = request.form.get("next")
    if next_page == "week":
        return redirect(url_for("week", week=run["date"]))
    return redirect(url_for("run_detail", run_id=run_id))


init_db()
app.secret_key = load_secret_key()
# Own cookie name, so another app on this computer can't overwrite this login.
app.config["SESSION_COOKIE_NAME"] = "race_planner_session"

if __name__ == "__main__":
    app.run(debug=True)
