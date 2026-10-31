from datetime import date, timedelta
from urllib.parse import urlencode

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Plan, Run, db
from plan_generator import DAYS, RECOMMENDED_WEEKS, generate_plan, monday_of

main_bp = Blueprint("main", __name__)

DISTANCES = {"5k": "5k", "10k": "10k", "half": "Half marathon", "marathon": "Marathon"}


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def get_user_run(run_id):
    # Joining on Plan and filtering by the current user stops people from opening
    # someone else's run by changing the id in the URL.
    return Run.query.join(Plan).filter(
        Run.id == run_id, Plan.user_id == current_user.id
    ).first_or_404()


def google_calendar_url(run):
    # An all-day event: Google expects the end date to be the day after.
    params = {
        "action": "TEMPLATE",
        "text": f"{run.run_type.capitalize()} run - {run.distance_km:g} km",
        "dates": f"{run.date:%Y%m%d}/{run.date + timedelta(days=1):%Y%m%d}",
        "details": run.description + ("\n\n" + run.notes if run.notes else ""),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


@main_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    plan = Plan.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        form = {
            "experience": request.form.get("experience"),
            "run_days": request.form.getlist("run_days"),
            "long_run_day": request.form.get("long_run_day"),
            "race_distance": request.form.get("race_distance"),
            "start_date": request.form.get("start_date", ""),
            "race_date": request.form.get("race_date", ""),
        }
        start_date = parse_date(form["start_date"])
        race_date = parse_date(form["race_date"])
        run_days = [d for d in DAYS if d in form["run_days"]]

        errors = []
        if form["experience"] not in ("new", "experienced"):
            errors.append("Choose your experience.")
        if len(run_days) < 3:
            errors.append("Pick at least 3 days you can run.")
        if form["long_run_day"] not in run_days:
            errors.append("The long-run day must be one of your running days.")
        if form["race_distance"] not in DISTANCES:
            errors.append("Choose a race distance.")
        if not start_date or not race_date:
            errors.append("Enter both a start date and a race date.")
        elif race_date <= start_date:
            errors.append("The race date must be after the start date.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("setup.html", form=form, plan=plan, days=DAYS,
                                   distances=DISTANCES, recommended=RECOMMENDED_WEEKS)

        if plan is None:
            plan = Plan(user_id=current_user.id)
            db.session.add(plan)
        plan.experience = form["experience"]
        plan.run_days = ",".join(run_days)
        plan.long_run_day = form["long_run_day"]
        plan.race_distance = form["race_distance"]
        plan.start_date = start_date
        plan.race_date = race_date

        new_runs = generate_plan(plan.experience, run_days, plan.long_run_day,
                                 plan.race_distance, start_date, race_date)
        # Replacing the list deletes the old runs (delete-orphan), and the single
        # commit means we never end up with a plan that has half its runs.
        plan.runs = [Run(**run) for run in new_runs]
        db.session.commit()

        weeks = (race_date - start_date).days // 7
        needed = RECOMMENDED_WEEKS[plan.race_distance]
        if weeks < needed:
            flash(f"Heads up: you have {weeks} weeks until the race, but at least {needed} "
                  f"weeks are recommended for a {DISTANCES[plan.race_distance]}. "
                  "Your plan was still created.", "warning")
        flash("Your training plan is ready.", "success")
        return redirect(url_for("main.week", start=monday_of(start_date).isoformat()))

    if plan:
        form = {
            "experience": plan.experience,
            "run_days": plan.run_days.split(","),
            "long_run_day": plan.long_run_day,
            "race_distance": plan.race_distance,
            "start_date": plan.start_date.isoformat(),
            "race_date": plan.race_date.isoformat(),
        }
    else:
        form = {"experience": "new", "run_days": [], "long_run_day": "Sun",
                "race_distance": "5k", "start_date": date.today().isoformat(), "race_date": ""}
    return render_template("setup.html", form=form, plan=plan, days=DAYS,
                           distances=DISTANCES, recommended=RECOMMENDED_WEEKS)


@main_bp.route("/")
@login_required
def week():
    plan = Plan.query.filter_by(user_id=current_user.id).first()
    if plan is None:
        return redirect(url_for("main.setup"))

    today = date.today()
    week_start = monday_of(parse_date(request.args.get("start")) or today)
    week_end = week_start + timedelta(days=6)

    runs = Run.query.filter(
        Run.plan_id == plan.id, Run.date >= week_start, Run.date <= week_end
    ).order_by(Run.date, Run.id).all()

    columns = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        columns.append({"date": day, "runs": [r for r in runs if r.date == day]})

    # Only show "Week N" for weeks that are actually part of the plan.
    week_number = (week_start - monday_of(plan.start_date)).days // 7 + 1
    total_weeks = (monday_of(plan.race_date) - monday_of(plan.start_date)).days // 7 + 1
    if not 1 <= week_number <= total_weeks:
        week_number = None

    return render_template(
        "week.html",
        plan=plan,
        columns=columns,
        today=today,
        week_start=week_start,
        week_end=week_end,
        week_number=week_number,
        total_weeks=total_weeks,
        planned_km=sum(r.distance_km for r in runs),
        done_km=sum(r.distance_km for r in runs if r.done),
        prev_start=(week_start - timedelta(days=7)).isoformat(),
        next_start=(week_start + timedelta(days=7)).isoformat(),
        distances=DISTANCES,
    )


@main_bp.route("/run/<int:run_id>")
@login_required
def run_detail(run_id):
    run = get_user_run(run_id)
    return render_template("run.html", run=run, gcal_url=google_calendar_url(run),
                           week_start=monday_of(run.date).isoformat())


@main_bp.route("/run/<int:run_id>/edit", methods=["GET", "POST"])
@login_required
def edit_run(run_id):
    run = get_user_run(run_id)

    if request.method == "POST":
        new_date = parse_date(request.form.get("date"))
        try:
            distance = float(request.form.get("distance_km", ""))
        except ValueError:
            distance = None

        if not new_date:
            flash("Enter a valid date.", "error")
        elif distance is None or distance <= 0:
            flash("Distance must be a number above 0.", "error")
        else:
            run.date = new_date
            run.distance_km = round(distance, 1)
            run.notes = request.form.get("notes", "").strip()
            db.session.commit()
            flash("Run updated.", "success")
            return redirect(url_for("main.run_detail", run_id=run.id))

    return render_template("edit_run.html", run=run)


@main_bp.route("/run/<int:run_id>/toggle", methods=["POST"])
@login_required
def toggle_done(run_id):
    run = get_user_run(run_id)
    run.done = not run.done
    db.session.commit()
    return redirect(url_for("main.run_detail", run_id=run.id))
