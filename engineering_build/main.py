from datetime import date, timedelta
from urllib.parse import urlencode

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Plan, Run, db
from plan_generator import DAYS, RECOMMENDED_WEEKS, generate_plan, monday_of

main_bp = Blueprint("main", __name__)

DISTANCES = {"5k": "5k", "10k": "10k", "half": "Half marathon", "marathon": "Marathon"}
BEST_TIME_FIELDS = {"best_5k": "5k", "best_10k": "10k", "best_half": "Half marathon", "best_full": "Marathon"}
WEEKS_SHOWN = 2


@main_bp.before_request
def require_profile():
    # New users fill in their profile before anything else in the app.
    if (current_user.is_authenticated and not current_user.has_profile
            and request.endpoint != "main.profile"):
        return redirect(url_for("main.profile"))


@main_bp.app_template_filter("duration")
def format_duration(seconds):
    if seconds is None:
        return ""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def parse_number(text, kind=float):
    try:
        return kind(text)
    except (TypeError, ValueError):
        return None


def parse_duration(text):
    # "25:30" (mm:ss) or "1:45:00" (h:mm:ss) -> seconds. Raises ValueError if malformed.
    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError
    numbers = [int(p) for p in parts]
    if any(n >= 60 for n in numbers[1:]):
        raise ValueError
    hours, minutes, seconds = [0] * (3 - len(numbers)) + numbers
    total = hours * 3600 + minutes * 60 + seconds
    if total == 0:
        raise ValueError
    return total


def get_active_plan():
    return Plan.query.filter_by(user_id=current_user.id, is_active=True).first()


def get_user_plan(plan_id):
    # Filtering by user_id means a changed id in the URL gives a 404, not someone else's plan.
    return Plan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()


def make_active(plan):
    # Called before a commit, so switching plans happens in one transaction.
    Plan.query.filter_by(user_id=current_user.id).update({"is_active": False})
    plan.is_active = True


def runs_between(plan, first_day, last_day):
    if plan is None:
        return []
    return Run.query.filter(
        Run.plan_id == plan.id, Run.date >= first_day, Run.date <= last_day
    ).order_by(Run.date, Run.id).all()


def total_plan_weeks(plan):
    return (monday_of(plan.race_date) - monday_of(plan.start_date)).days // 7 + 1


def plan_week_number(plan, week_start):
    # None for weeks outside the plan, so templates only show "Week N" when it means something.
    if plan is None:
        return None
    number = (week_start - monday_of(plan.start_date)).days // 7 + 1
    return number if 1 <= number <= total_plan_weeks(plan) else None


def build_week(plan, week_start):
    week_end = week_start + timedelta(days=6)
    runs = runs_between(plan, week_start, week_end)
    days = [week_start + timedelta(days=i) for i in range(7)]
    return {
        "start": week_start,
        "end": week_end,
        "number": plan_week_number(plan, week_start),
        "columns": [{"date": d, "runs": [r for r in runs if r.date == d]} for d in days],
        "planned_km": sum(r.distance_km for r in runs),
        "done_km": sum(r.distance_km for r in runs if r.done),
    }


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


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    onboarding = not current_user.has_profile

    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("sex", "age", "weight_kg", "height_cm")}
        age = parse_number(form["age"], int)
        weight = parse_number(form["weight_kg"])
        height = parse_number(form["height_cm"], int)

        errors = []
        if form["sex"] not in ("male", "female"):
            errors.append("Choose male or female.")
        if age is None or not 10 <= age <= 100:
            errors.append("Age must be a whole number between 10 and 100.")
        if weight is None or not 25 <= weight <= 300:
            errors.append("Weight must be between 25 and 300 kg.")
        if height is None or not 100 <= height <= 250:
            errors.append("Height must be a whole number between 100 and 250 cm.")

        if not errors:
            current_user.sex = form["sex"]
            current_user.age = age
            current_user.weight_kg = round(weight, 1)
            current_user.height_cm = height
            db.session.commit()
            if onboarding:
                flash("Welcome! Create a plan when you're ready.", "success")
                return redirect(url_for("main.week"))
            flash("Profile saved.", "success")
            return redirect(url_for("main.profile"))
        for error in errors:
            flash(error, "error")
    else:
        form = {
            "sex": current_user.sex or "",
            "age": current_user.age or "",
            "weight_kg": "" if current_user.weight_kg is None else f"{current_user.weight_kg:g}",
            "height_cm": current_user.height_cm or "",
        }
    return render_template("profile.html", form=form, onboarding=onboarding)


def read_plan_form():
    fields = ["has_run_before", "weekly_km", "long_run_day", "race_distance",
              "start_date", "race_date", *BEST_TIME_FIELDS]
    form = {k: request.form.get(k, "").strip() for k in fields}
    form["run_days"] = request.form.getlist("run_days")
    return form


def parse_plan_form(form):
    # Returns (values ready to set on a Plan, list of error messages).
    errors = []
    has_run_before = form["has_run_before"] == "yes"
    weekly_km = parse_number(form["weekly_km"])
    run_days = [d for d in DAYS if d in form["run_days"]]
    start_date = parse_date(form["start_date"])
    race_date = parse_date(form["race_date"])

    if form["has_run_before"] not in ("yes", "no"):
        errors.append("Say whether you have run before.")
    if weekly_km is None or not 0 <= weekly_km <= 300:
        errors.append("Current weekly distance must be a number of km between 0 and 300.")
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

    # Times only count for people who have run before; otherwise they're ignored.
    best_times = {}
    for field, label in BEST_TIME_FIELDS.items():
        best_times[field] = None
        if has_run_before and form[field]:
            try:
                best_times[field] = parse_duration(form[field])
            except ValueError:
                errors.append(f"{label} time should look like 25:30 or 1:45:00.")

    values = {
        "has_run_before": has_run_before,
        "weekly_km": round(weekly_km, 1) if weekly_km is not None else None,
        "run_days": ",".join(run_days),
        "long_run_day": form["long_run_day"],
        "race_distance": form["race_distance"],
        "start_date": start_date,
        "race_date": race_date,
        **best_times,
    }
    return values, errors


def form_from_plan(plan):
    form = {
        "has_run_before": "yes" if plan.has_run_before else "no",
        "weekly_km": f"{plan.weekly_km:g}",
        "run_days": plan.run_days.split(","),
        "long_run_day": plan.long_run_day,
        "race_distance": plan.race_distance,
        "start_date": plan.start_date.isoformat(),
        "race_date": plan.race_date.isoformat(),
    }
    for field in BEST_TIME_FIELDS:
        form[field] = format_duration(getattr(plan, field))
    return form


def render_plan_form(form, plan):
    return render_template("setup.html", form=form, plan=plan, days=DAYS, distances=DISTANCES,
                           recommended=RECOMMENDED_WEEKS, best_time_fields=BEST_TIME_FIELDS)


def save_plan(plan, values):
    for key, value in values.items():
        setattr(plan, key, value)
    new_runs = generate_plan(plan.has_run_before, plan.weekly_km, plan.run_days.split(","),
                             plan.long_run_day, plan.race_distance, plan.start_date, plan.race_date)
    # Replacing the list deletes the old runs (delete-orphan), and the single
    # commit means we never end up with a plan that has half its runs.
    plan.runs = [Run(**run) for run in new_runs]
    db.session.commit()

    weeks = (plan.race_date - plan.start_date).days // 7
    needed = RECOMMENDED_WEEKS[plan.race_distance]
    if weeks < needed:
        flash(f"Heads up: you have {weeks} weeks until the race, but at least {needed} "
              f"weeks are recommended for a {DISTANCES[plan.race_distance]}. "
              "Your plan was still created.", "warning")


@main_bp.route("/plans")
@login_required
def plans():
    user_plans = Plan.query.filter_by(user_id=current_user.id).order_by(
        Plan.is_active.desc(), Plan.race_date.desc()).all()
    return render_template("plans.html", plans=user_plans, distances=DISTANCES,
                           best_time_fields=BEST_TIME_FIELDS)


@main_bp.route("/plans/new", methods=["GET", "POST"])
@login_required
def new_plan():
    if request.method == "POST":
        form = read_plan_form()
        values, errors = parse_plan_form(form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_plan_form(form, None)

        # Built with its values up front: make_active's UPDATE flushes this plan to the
        # database first, and that insert would fail with required columns still empty.
        plan = Plan(user_id=current_user.id, **values)
        db.session.add(plan)
        # A newly created plan is the one the user wants to follow, so it becomes active.
        make_active(plan)
        save_plan(plan, values)
        flash("Your training plan is ready.", "success")
        return redirect(url_for("main.week", start=monday_of(plan.start_date).isoformat()))

    form = {"has_run_before": "", "weekly_km": "", "run_days": [], "long_run_day": "Sun",
            "race_distance": "5k", "start_date": date.today().isoformat(), "race_date": "",
            **{field: "" for field in BEST_TIME_FIELDS}}
    return render_plan_form(form, None)


@main_bp.route("/plans/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
def edit_plan(plan_id):
    plan = get_user_plan(plan_id)

    if request.method == "POST":
        form = read_plan_form()
        values, errors = parse_plan_form(form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_plan_form(form, plan)

        save_plan(plan, values)
        flash("Plan updated and regenerated.", "success")
        if plan.is_active:
            return redirect(url_for("main.week", start=monday_of(plan.start_date).isoformat()))
        return redirect(url_for("main.plans"))

    return render_plan_form(form_from_plan(plan), plan)


@main_bp.route("/plans/<int:plan_id>/activate", methods=["POST"])
@login_required
def activate_plan(plan_id):
    plan = get_user_plan(plan_id)
    make_active(plan)
    db.session.commit()
    flash(f"{DISTANCES[plan.race_distance]} plan is now active.", "success")
    return redirect(url_for("main.week", start=monday_of(plan.start_date).isoformat()))


@main_bp.route("/plans/<int:plan_id>/delete", methods=["POST"])
@login_required
def delete_plan(plan_id):
    plan = get_user_plan(plan_id)
    was_active = plan.is_active
    db.session.delete(plan)
    # Keep a plan active if there is one left, so the calendar doesn't go empty.
    if was_active:
        replacement = Plan.query.filter(Plan.user_id == current_user.id, Plan.id != plan.id) \
            .order_by(Plan.race_date.desc()).first()
        if replacement:
            replacement.is_active = True
    db.session.commit()
    flash("Plan deleted.", "success")
    return redirect(url_for("main.plans"))


@main_bp.route("/")
@login_required
def week():
    plan = get_active_plan()
    week_start = monday_of(parse_date(request.args.get("start")) or date.today())
    # Two weeks side by side in a horizontal scroller: the chosen week, then the next one.
    weeks = [build_week(plan, week_start + timedelta(weeks=i)) for i in range(WEEKS_SHOWN)]

    return render_template(
        "week.html",
        plan=plan,
        weeks=weeks,
        today=date.today(),
        total_weeks=total_plan_weeks(plan) if plan else None,
        month=week_start.strftime("%Y-%m"),
        prev_start=(week_start - timedelta(days=7)).isoformat(),
        next_start=(week_start + timedelta(days=7)).isoformat(),
        distances=DISTANCES,
    )


@main_bp.route("/month")
@login_required
def month():
    plan = get_active_plan()
    today = date.today()
    first = parse_date((request.args.get("month") or "") + "-01") or today.replace(day=1)
    next_first = (first + timedelta(days=32)).replace(day=1)
    last = next_first - timedelta(days=1)

    # The grid starts on the Monday before the 1st and ends on the Sunday after
    # the last day, so every row is a full week like in Google Calendar.
    grid_start = monday_of(first)
    grid_end = monday_of(last) + timedelta(days=6)
    runs = runs_between(plan, grid_start, grid_end)

    rows = []
    week_start = grid_start
    while week_start <= grid_end:
        days = [week_start + timedelta(days=i) for i in range(7)]
        rows.append({
            "week_start": week_start,
            "week_number": plan_week_number(plan, week_start),
            "days": [{"date": d, "runs": [r for r in runs if r.date == d]} for d in days],
        })
        week_start += timedelta(days=7)

    # Totals only count runs inside this month, not the grey days from next to it.
    month_runs = [r for r in runs if first <= r.date <= last]
    return render_template(
        "month.html",
        plan=plan,
        rows=rows,
        first=first,
        today=today,
        planned_km=sum(r.distance_km for r in month_runs),
        done_km=sum(r.distance_km for r in month_runs if r.done),
        prev_month=(first - timedelta(days=1)).strftime("%Y-%m"),
        next_month=next_first.strftime("%Y-%m"),
        week_link=monday_of(first).isoformat(),
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
    # Go back to the page the checkbox was on. Only local paths are allowed, so the
    # form can't be used to send someone to another site.
    back = request.form.get("next", "")
    if not back.startswith("/") or back.startswith(("//", "/\\")):
        back = url_for("main.run_detail", run_id=run.id)
    return redirect(back)
