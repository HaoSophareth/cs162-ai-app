from datetime import date, timedelta
from urllib.parse import urlencode

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import func

from models import Plan, Run, db
from plan_generator import (DAYS, RECOMMENDED_WEEKS, current_paces, estimate_finish,
                            generate_plan, monday_of)

main_bp = Blueprint("main", __name__)

DISTANCES = {"5k": "5K", "10k": "10K", "15k": "15K", "half": "Half marathon", "marathon": "Marathon"}
BEST_TIME_FIELDS = {"best_5k": "5K", "best_10k": "10K", "best_half": "Half marathon", "best_full": "Marathon"}
# The number boxes each race time is typed into.
BEST_TIME_PARTS = {"best_5k": ("min", "sec"), "best_10k": ("min", "sec"),
                   "best_half": ("h", "min", "sec"), "best_full": ("h", "min", "sec")}
BEST_TIME_BOXES = [f"{field}_{part}" for field, parts in BEST_TIME_PARTS.items() for part in parts]
# Which race distance each best-time column is for (the marathon column is best_full).
BEST_TIME_DISTANCE = {"best_5k": "5k", "best_10k": "10k", "best_half": "half", "best_full": "marathon"}
# The plan form is split into three steps, in this order. Each one names the form
# fields it asks for; errors are grouped by "key", so reordering only happens here.
PLAN_STEPS = {
    1: {"key": "goal", "title": "Goal", "fields": ["race_distance", "start_date", "race_date"]},
    2: {"key": "experience", "title": "Experience", "fields": ["has_run_before", "weekly_km", "longest_run_km",
                                                               "has_race_time", "race_time_distances", *BEST_TIME_BOXES]},
    3: {"key": "schedule", "title": "Schedule", "fields": ["run_days", "long_run_day"]},
}
LAST_STEP = len(PLAN_STEPS)


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


def duration_from_parts(form, field):
    # The boxes of one race time -> seconds. Raises ValueError if they don't make a valid time.
    texts = [form.get(f"{field}_{part}", "") for part in BEST_TIME_PARTS[field]]
    texts[-1] = texts[-1] or "0"  # a blank seconds box counts as 00
    if not all(text.isdecimal() for text in texts):
        raise ValueError
    numbers = [int(text) for text in texts]
    if numbers[0] > 999 or any(number > 59 for number in numbers[1:]):
        raise ValueError
    total = 0
    for number in numbers:
        total = total * 60 + number
    if total == 0:
        raise ValueError
    return total


def parts_from_duration(field, seconds):
    # Saved seconds -> the text for each box. The first box isn't limited to 59, so a 5K
    # over an hour shows as 65 : 10, and a half under an hour as 0 : 58 : 00.
    parts = BEST_TIME_PARTS[field]
    if seconds is None:
        return {f"{field}_{part}": "" for part in parts}
    minutes, secs = divmod(seconds, 60)
    numbers = [minutes, secs] if len(parts) == 2 else [minutes // 60, minutes % 60, secs]
    texts = [str(numbers[0])] + [f"{number:02}" for number in numbers[1:]]
    return {f"{field}_{part}": text for part, text in zip(parts, texts)}


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


def week_anchor(day):
    return f"week-{monday_of(day).isoformat()}"


def week_view_url(anchor="current"):
    # The week view is one long page; the #anchor scrolls it to the right week.
    # "current" is the week the page itself picks to land on (normally this week).
    return url_for("main.week", _anchor=anchor)


def build_week(plan, week_start, plan_runs):
    week_end = week_start + timedelta(days=6)
    runs = [r for r in plan_runs if week_start <= r.date <= week_end]
    days = [week_start + timedelta(days=i) for i in range(7)]
    return {
        "start": week_start,
        "end": week_end,
        "anchor": week_anchor(week_start),
        "number": plan_week_number(plan, week_start),
        "columns": [{"date": d, "runs": [r for r in runs if r.date == d]} for d in days],
        "planned_km": sum(r.distance_km for r in runs),
        "done_km": sum(r.distance_km for r in runs if r.done),
        "has_runs": bool(runs),
        "all_done": bool(runs) and all(r.done for r in runs),
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


def running_history():
    # Covers all of the user's plans, active or not. Nothing is stored; it's worked out each time.
    plan_row = db.session.query(
        *[func.min(getattr(Plan, field)) for field in BEST_TIME_FIELDS],
        func.max(Plan.longest_run_km),
    ).filter(Plan.user_id == current_user.id).one()
    done_count, done_km, longest_done_km = db.session.query(
        func.count(Run.id), func.sum(Run.distance_km), func.max(Run.distance_km),
    ).join(Plan).filter(Plan.user_id == current_user.id, Run.done.is_(True)).one()

    best_times = {label: seconds for label, seconds in zip(BEST_TIME_FIELDS.values(), plan_row)}
    longest_recent_km = plan_row[-1]
    return {
        "best_times": best_times,
        "longest_recent_km": longest_recent_km,
        "done_count": done_count,
        "done_km": done_km or 0,
        "longest_done_km": longest_done_km,
        "is_empty": not any(best_times.values()) and longest_recent_km is None and done_count == 0,
    }


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
                return redirect(week_view_url())
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
    return render_template("profile.html", form=form, onboarding=onboarding, history=running_history())


@main_bp.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    if request.form.get("confirm_username", "").strip() != current_user.username:
        flash("That username doesn't match, so nothing was deleted.", "error")
        return redirect(url_for("main.profile"))

    # Always the logged-in user. Their plans and runs go with them through the
    # cascades in models.py, all in this one commit.
    db.session.delete(current_user._get_current_object())
    db.session.commit()
    logout_user()
    session.pop("plan_form", None)
    flash("Your account has been deleted.", "success")
    return redirect(url_for("auth.login"))


def read_step_form(step):
    answers = {}
    for field in PLAN_STEPS[step]["fields"]:
        if field in ("run_days", "race_time_distances"):
            answers[field] = request.form.getlist(field)
        else:
            answers[field] = request.form.get(field, "").strip()
    return answers


def parse_plan_form(form, saved_start=None):
    # Returns (values ready to set on a Plan, {step key: [error messages]}).
    errors = {info["key"]: [] for info in PLAN_STEPS.values()}
    has_run_before = form["has_run_before"] == "yes"
    # New runners aren't asked for a weekly distance: 0 makes the plan start at the
    # beginner floor in plan_generator. Anything typed before switching to "No" is ignored.
    weekly_km = parse_number(form["weekly_km"]) if has_run_before else 0
    # Optional, and only asked of people who have run before.
    longest_text = form["longest_run_km"] if has_run_before else ""
    longest_run_km = parse_number(longest_text) if longest_text else None
    run_days = [d for d in DAYS if d in form["run_days"]]
    # An empty start date box shows "Today" and means today.
    start_date = date.today() if form["start_date"] == "" else parse_date(form["start_date"])
    race_date = parse_date(form["race_date"])

    if form["has_run_before"] not in ("yes", "no"):
        errors["experience"].append("Say whether you have run before.")
    if has_run_before and (weekly_km is None or not 0 <= weekly_km <= 300):
        errors["experience"].append("Current weekly distance must be a number of km between 0 and 300.")
    if longest_text and (longest_run_km is None or not 0 < longest_run_km <= 100):
        errors["experience"].append("Longest recent run must be a number of km above 0 and up to 100.")
    if len(run_days) < 3:
        errors["schedule"].append("Pick at least 3 days you can run.")
    if form["long_run_day"] not in run_days:
        errors["schedule"].append("The long-run day must be one of your running days.")
    if form["race_distance"] not in DISTANCES:
        errors["goal"].append("Choose a race distance.")
    if not start_date or not race_date:
        errors["goal"].append("Enter both a start date and a race date.")
    elif race_date <= start_date:
        errors["goal"].append("The race date must be after the start date.")
    # A plan already under way can keep its start date, even once that date has passed.
    if start_date and start_date < date.today() and start_date != saved_start:
        errors["goal"].append("The training start date can't be in the past.")

    # A time only counts if its box was showing: run before, "Yes" to having a race
    # time, and that distance ticked. Anything typed and then hidden is ignored.
    has_race_time = has_run_before and form.get("has_race_time") == "yes"
    ticked = form.get("race_time_distances", []) if has_race_time else []
    if has_run_before and form.get("has_race_time") not in ("yes", "no"):
        errors["experience"].append("Say whether you have a recent race time.")
    if has_race_time and not any(field in ticked for field in BEST_TIME_FIELDS):
        errors["experience"].append("Tick the distance of your recent race, or choose No.")
    best_times = {}
    for field, label in BEST_TIME_FIELDS.items():
        best_times[field] = None
        if field in ticked:
            try:
                best_times[field] = duration_from_parts(form, field)
            except ValueError:
                layout = " : ".join(BEST_TIME_PARTS[field])
                limits = "seconds" if len(BEST_TIME_PARTS[field]) == 2 else "minutes and seconds"
                errors["experience"].append(f"Enter your {label} time as {layout}, with {limits} from 0 to 59.")

    values = {
        "has_run_before": has_run_before,
        "weekly_km": round(weekly_km, 1) if weekly_km is not None else None,
        "longest_run_km": round(longest_run_km, 1) if longest_run_km is not None else None,
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
        "weekly_km": f"{plan.weekly_km:g}" if plan.has_run_before else "",
        "longest_run_km": "" if plan.longest_run_km is None else f"{plan.longest_run_km:g}",
        "run_days": plan.run_days.split(","),
        "long_run_day": plan.long_run_day,
        "race_distance": plan.race_distance,
        "start_date": plan.start_date.isoformat(),
        "race_date": plan.race_date.isoformat(),
    }
    for field in BEST_TIME_FIELDS:
        form.update(parts_from_duration(field, getattr(plan, field)))
    form["race_time_distances"] = [field for field in BEST_TIME_FIELDS if getattr(plan, field)]
    if plan.has_run_before:
        form["has_race_time"] = "yes" if form["race_time_distances"] else "no"
    else:
        form["has_race_time"] = ""
    return form


def save_plan(plan, values):
    for key, value in values.items():
        setattr(plan, key, value)
    new_runs = generate_plan(plan.has_run_before, plan.weekly_km, plan.longest_run_km, plan.run_days.split(","),
                             plan.long_run_day, plan.race_distance, plan.start_date, plan.race_date)
    # Replacing the list deletes the old runs (delete-orphan), and the single
    # commit means we never end up with a plan that has half its runs.
    plan.runs = [Run(**run) for run in new_runs]
    db.session.commit()

    weeks = total_plan_weeks(plan)
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


# Creating and editing a plan share the same three steps. The answers live in the
# Flask session between steps, and nothing touches the database until the last one.
@main_bp.route("/plans/new")
@login_required
def new_plan():
    answers = {"has_run_before": "", "weekly_km": "", "longest_run_km": "", "has_race_time": "", "race_time_distances": [],
               "run_days": [], "long_run_day": "Sun",
               "race_distance": "5k", "start_date": "", "race_date": "",
               **{box: "" for box in BEST_TIME_BOXES}}
    session["plan_form"] = {"plan_id": None, "answers": answers}
    return redirect(url_for("main.plan_step", step=1))


@main_bp.route("/plans/<int:plan_id>/edit")
@login_required
def edit_plan(plan_id):
    plan = get_user_plan(plan_id)
    session["plan_form"] = {"plan_id": plan.id, "answers": form_from_plan(plan)}
    return redirect(url_for("main.plan_step", step=1))


@main_bp.route("/plans/step/<int:step>", methods=["GET", "POST"])
@login_required
def plan_step(step):
    wizard = session.get("plan_form")
    if wizard is None or step not in PLAN_STEPS:
        return redirect(url_for("main.plans"))
    # Checked on every step, so a plan id left in the session can only ever be the user's own.
    plan = get_user_plan(wizard["plan_id"]) if wizard["plan_id"] else None
    answers = wizard["answers"]

    if request.method == "POST":
        answers.update(read_step_form(step))
        session.modified = True  # Flask doesn't notice changes inside nested dicts on its own.

        if request.form.get("action") == "back":
            if step == 1:
                session.pop("plan_form")
                return redirect(url_for("main.plans"))
            return redirect(url_for("main.plan_step", step=step - 1))

        values, errors = parse_plan_form(answers, plan.start_date if plan else None)
        step_errors = errors[PLAN_STEPS[step]["key"]]
        if step_errors:
            for error in step_errors:
                flash(error, "error")
        elif step < LAST_STEP:
            return redirect(url_for("main.plan_step", step=step + 1))
        else:
            # Earlier steps are checked again because their URLs can be skipped.
            for earlier in range(1, LAST_STEP):
                earlier_errors = errors[PLAN_STEPS[earlier]["key"]]
                if earlier_errors:
                    for error in earlier_errors:
                        flash(error, "error")
                    return redirect(url_for("main.plan_step", step=earlier))
            return finish_plan(plan, values)

    # The browser must still accept a saved start date that has passed; the server
    # rejects any other past date.
    min_start = min(date.today(), plan.start_date) if plan else date.today()
    return render_template("setup.html", min_start=min_start.isoformat(), today=date.today().isoformat(), step=step, steps=PLAN_STEPS, last_step=LAST_STEP,
                           form=answers, plan=plan, days=DAYS, distances=DISTANCES,
                           recommended=RECOMMENDED_WEEKS, best_time_fields=BEST_TIME_FIELDS,
                           best_time_parts=BEST_TIME_PARTS)


def finish_plan(plan, values):
    session.pop("plan_form")
    if plan is None:
        # Built with its values up front: make_active's UPDATE flushes this plan to the
        # database first, and that insert would fail with required columns still empty.
        plan = Plan(user_id=current_user.id, **values)
        db.session.add(plan)
        # A newly created plan is the one the user wants to follow, so it becomes active.
        make_active(plan)
        save_plan(plan, values)
        flash("Your training plan is ready.", "success")
    else:
        save_plan(plan, values)
        flash("Plan updated and regenerated.", "success")
    return redirect(url_for("main.plan_summary", plan_id=plan.id))


@main_bp.route("/plans/<int:plan_id>/summary")
@login_required
def plan_summary(plan_id):
    plan = get_user_plan(plan_id)

    # Numbers come from the saved runs, so they stay right after runs are edited or moved.
    weekly_km = {}
    for run in plan.runs:
        week = monday_of(run.date)
        weekly_km[week] = weekly_km.get(week, 0) + run.distance_km
    training_runs = [r.distance_km for r in plan.runs if r.run_type != "race"]
    stats = {
        "start_km": weekly_km[min(weekly_km)] if weekly_km else 0,
        "peak_km": max(weekly_km.values(), default=0),
        "longest_run_km": max(training_runs, default=0),
        "total_km": sum(r.distance_km for r in plan.runs),
    }

    best_times = {BEST_TIME_DISTANCE[field]: getattr(plan, field)
                  for field in BEST_TIME_FIELDS if getattr(plan, field)}
    return render_template(
        "summary.html",
        plan=plan,
        stats=stats,
        total_weeks=total_plan_weeks(plan),
        best_times=best_times,
        paces=current_paces(best_times),
        estimate=estimate_finish(best_times, plan.race_distance),
        distances=DISTANCES,
    )


@main_bp.route("/plans/<int:plan_id>/activate", methods=["POST"])
@login_required
def activate_plan(plan_id):
    plan = get_user_plan(plan_id)
    make_active(plan)
    db.session.commit()
    flash(f"{DISTANCES[plan.race_distance]} plan is now active.", "success")
    return redirect(week_view_url())


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
    if plan is None:
        # No calendar to show yet, just a prompt to create the first plan.
        return render_template("week.html", plan=None)

    today = date.today()
    this_monday = monday_of(today)
    runs = runs_between(plan, date.min, date.max)
    # From the plan's first week to race week, stretched if a run was moved outside it.
    first = monday_of(min([plan.start_date] + [r.date for r in runs]))
    last = monday_of(max([plan.race_date] + [r.date for r in runs]))

    weeks = []
    week_start = first
    while week_start <= last:
        weeks.append(build_week(plan, week_start, runs))
        week_start += timedelta(days=7)

    # Land on this week; before the plan starts that's week 1, after the race it's race week.
    landing = min(max(this_monday, first), last)

    return render_template(
        "week.html",
        plan=plan,
        weeks=weeks,
        landing=landing,
        this_monday=this_monday,
        today=today,
        total_weeks=total_plan_weeks(plan),
        distances=DISTANCES,
    )


@main_bp.route("/week/<start>", methods=["GET", "POST"])
@login_required
def week_frame(start):
    plan = get_active_plan()
    week_start = parse_date(start)
    if plan is None or week_start is None:
        abort(404)
    week_start = monday_of(week_start)
    week_end = week_start + timedelta(days=6)
    if request.method == "POST":
        if "mark_week" in request.form:
            # Sets the state the checkbox asked for, not a flip, so a page left open
            # can't do the opposite of what it showed. Only the active plan's runs.
            done = request.form["mark_week"] == "done"
            for run in runs_between(plan, week_start, week_end):
                run.done = done
        else:
            run = get_user_run(request.form.get("run_id", type=int))
            run.done = not run.done
        db.session.commit()
        return redirect(url_for("main.week_frame", start=start))

    return render_template(
        "week_frame.html",
        week=build_week(plan, week_start, runs_between(plan, week_start, week_end)),
        today=date.today(),
        this_monday=monday_of(date.today()),
        total_weeks=total_plan_weeks(plan),
    )


@main_bp.route("/run/<int:run_id>")
@login_required
def run_detail(run_id):
    run = get_user_run(run_id)
    return render_template("run.html", run=run, gcal_url=google_calendar_url(run),
                           week_link=week_view_url(week_anchor(run.date)))


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
