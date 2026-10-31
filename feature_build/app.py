"""Race training planner: a small Flask app backed by a SQLite file."""

import os
import secrets
import sqlite3
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import plan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(DATA_DIR, "training.db")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_VALUES = [str(i) for i in range(7)]
RUN_TYPES = {"easy": "Easy", "long": "Long run", "tempo": "Tempo", "intervals": "Intervals", "race": "Race"}

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
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS setups (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    experience TEXT NOT NULL,
    run_days TEXT NOT NULL,      -- weekday numbers, e.g. "0,2,5" (Monday = 0)
    long_day INTEGER NOT NULL,
    distance TEXT NOT NULL,
    start_date TEXT NOT NULL,
    race_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
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


def get_setup(user_id):
    return get_db().execute("SELECT * FROM setups WHERE user_id = ?", (user_id,)).fetchone()


def get_own_run(run_id):
    # Filtering by user_id means nobody can open another user's run by URL.
    run = get_db().execute(
        "SELECT * FROM runs WHERE id = ? AND user_id = ?", (run_id, session["user_id"])
    ).fetchone()
    if run is None:
        abort(404)
    return run


def save_plan(user_id, form):
    """Store the setup answers and replace all runs with a freshly generated plan."""
    db = get_db()
    db.execute("DELETE FROM setups WHERE user_id = ?", (user_id,))
    db.execute(
        "INSERT INTO setups (user_id, experience, run_days, long_day, distance, start_date, race_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, form["experience"], ",".join(map(str, form["run_days"])), form["long_day"],
         form["distance"], form["start_date"].isoformat(), form["race_date"].isoformat()),
    )
    db.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
    runs = plan.generate_plan(form["experience"], form["run_days"], form["long_day"],
                              form["distance"], form["start_date"], form["race_date"])
    db.executemany(
        "INSERT INTO runs (user_id, date, type, distance_km, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, r["date"].isoformat(), r["type"], r["distance_km"], r["description"]) for r in runs],
    )
    db.commit()  # one commit, so the old plan is never half-replaced


# ---------- Helpers ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def google_calendar_link(run):
    day = date.fromisoformat(run["date"])
    params = {
        "action": "TEMPLATE",
        "text": f"{RUN_TYPES[run['type']]} - {run['distance_km']:g} km",
        # All-day event: the end date is exclusive, so it's the next day.
        "dates": f"{day:%Y%m%d}/{day + timedelta(days=1):%Y%m%d}",
        "details": run["description"] + (f"\n\nNotes: {run['notes']}" if run["notes"] else ""),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


@app.context_processor
def template_helpers():
    return {"RUN_TYPES": RUN_TYPES, "WEEKDAYS": WEEKDAYS, "DISTANCES": plan.DISTANCES}


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
            session["username"] = username
            return redirect(url_for("setup"))
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
            session["username"] = user["username"]
            return redirect(url_for("week"))
        flash("Wrong username or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Setup ----------

def read_setup_form(form):
    """Return (values, errors) from the submitted setup form."""
    values = {
        "experience": form.get("experience"),
        "run_days": sorted({int(d) for d in form.getlist("run_days") if d in WEEKDAY_VALUES}),
        "long_day": int(form.get("long_day", -1)) if form.get("long_day", "").isdigit() else -1,
        "distance": form.get("distance"),
        "start_date": parse_date(form.get("start_date")),
        "race_date": parse_date(form.get("race_date")),
    }
    errors = []
    if values["experience"] not in plan.START_WEEKLY_KM:
        errors.append("Pick your running experience.")
    if len(values["run_days"]) < 3:
        errors.append("Pick at least 3 days you can run.")
    if values["long_day"] not in values["run_days"]:
        errors.append("The long-run day must be one of your running days.")
    if values["distance"] not in plan.DISTANCES:
        errors.append("Pick a race distance.")
    if not values["start_date"] or not values["race_date"]:
        errors.append("Enter both a start date and a race date.")
    elif values["race_date"] <= values["start_date"]:
        errors.append("The race date must be after the start date.")
    return values, errors


@app.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    user_id = session["user_id"]
    existing = get_setup(user_id)

    if request.method == "POST":
        values, errors = read_setup_form(request.form)
        if not errors:
            short = plan.is_too_short(values["distance"], values["start_date"], values["race_date"])
            # Too-short plans are allowed, but only after the user has seen the warning.
            if short and not request.form.get("confirm_short"):
                weeks = plan.count_weeks(values["start_date"], values["race_date"])
                label, _, recommended = plan.DISTANCES[values["distance"]]
                return render_template("setup.html", values=values, existing=existing,
                                       short_warning=(weeks, label, recommended))
            save_plan(user_id, values)
            flash("Your training plan is ready." if not existing else "Your plan was regenerated.", "success")
            return redirect(url_for("week"))
        for error in errors:
            flash(error, "error")
        return render_template("setup.html", values=values, existing=existing)

    if existing:
        values = dict(existing)
        values["run_days"] = [int(d) for d in existing["run_days"].split(",")]
    else:
        values = {"experience": "new", "run_days": [1, 3, 5], "long_day": 5, "distance": "5k",
                  "start_date": date.today(), "race_date": date.today() + timedelta(weeks=10)}
    return render_template("setup.html", values=values, existing=existing)


# ---------- Calendar views (week and month) ----------

def load_runs(first_day, last_day):
    """The user's runs between two dates (inclusive)."""
    return get_db().execute(
        "SELECT * FROM runs WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date, id",
        (session["user_id"], first_day.isoformat(), last_day.isoformat()),
    ).fetchall()


def build_days(first_day, count, runs):
    """A list of {date, runs} for `count` days starting at first_day."""
    days = []
    for offset in range(count):
        day = first_day + timedelta(days=offset)
        days.append({"date": day, "runs": [r for r in runs if r["date"] == day.isoformat()]})
    return days


def plan_week_number(monday, setup_row):
    """Week number within the plan, or None if this week is outside it."""
    start = date.fromisoformat(setup_row["start_date"])
    race = date.fromisoformat(setup_row["race_date"])
    number = (monday - plan.monday_of(start)).days // 7 + 1
    return number if 1 <= number <= plan.count_weeks(start, race) else None


def default_day(setup_row):
    # Before the plan starts, open on its first week instead of an empty one.
    start = date.fromisoformat(setup_row["start_date"])
    return max(date.today(), start)


@app.route("/")
@login_required
def week():
    setup_row = get_setup(session["user_id"])
    if setup_row is None:
        return redirect(url_for("setup"))

    monday = plan.monday_of(parse_date(request.args.get("week")) or default_day(setup_row))
    sunday = monday + timedelta(days=6)
    runs = load_runs(monday, sunday)

    return render_template(
        "week.html",
        days=build_days(monday, 7, runs),
        today=date.today(),
        monday=monday,
        sunday=sunday,
        week_number=plan_week_number(monday, setup_row),
        planned_km=sum(r["distance_km"] for r in runs),
        done_km=sum(r["distance_km"] for r in runs if r["done"]),
        prev_week=monday - timedelta(weeks=1),
        next_week=monday + timedelta(weeks=1),
        setup=setup_row,
    )


@app.route("/month")
@login_required
def month():
    setup_row = get_setup(session["user_id"])
    if setup_row is None:
        return redirect(url_for("setup"))

    # ?month=2026-11 -> first day of that month
    first = parse_date((request.args.get("month") or "") + "-01") or default_day(setup_row).replace(day=1)
    next_first = (first + timedelta(days=32)).replace(day=1)
    last = next_first - timedelta(days=1)

    # The grid covers whole Monday-Sunday weeks, so it starts and ends with
    # a few days from the neighbouring months.
    grid_start = plan.monday_of(first)
    grid_end = plan.monday_of(last) + timedelta(days=6)
    runs = load_runs(grid_start, grid_end)
    days = build_days(grid_start, (grid_end - grid_start).days + 1, runs)
    weeks = [{"monday": days[i]["date"],
              "number": plan_week_number(days[i]["date"], setup_row),
              "days": days[i:i + 7]}
             for i in range(0, len(days), 7)]

    month_runs = [r for r in runs if first.isoformat() <= r["date"] <= last.isoformat()]
    return render_template(
        "month.html",
        weeks=weeks,
        first=first,
        today=date.today(),
        planned_km=sum(r["distance_km"] for r in month_runs),
        done_km=sum(r["distance_km"] for r in month_runs if r["done"]),
        prev_month=(first - timedelta(days=1)).strftime("%Y-%m"),
        next_month=next_first.strftime("%Y-%m"),
        setup=setup_row,
    )


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
        try:
            distance = round(float(request.form.get("distance_km", "")), 1)
        except ValueError:
            distance = None
        if new_date is None:
            flash("Enter a valid date.", "error")
        elif distance is None or not 0 < distance <= 100:
            flash("Distance must be a number of km between 0 and 100.", "error")
        else:
            # Rewrite the workout text so it matches the new distance.
            description = plan.describe(run["type"], distance, get_setup(session["user_id"])["distance"])
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
    if next_page == "month":
        # Stay on the month being viewed, even if the run is a greyed-out
        # day from the neighbouring month.
        return redirect(url_for("month", month=request.form.get("month") or run["date"][:7]))
    return redirect(url_for("run_detail", run_id=run_id))


init_db()
app.secret_key = load_secret_key()

if __name__ == "__main__":
    app.run(debug=True)
