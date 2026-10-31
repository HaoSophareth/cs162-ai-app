"""Training plan generator: fixed rules, no AI.

generate_plan() takes the plan answers and returns a list of runs
(plain dicts). It knows nothing about the web app or the database.
"""

from datetime import timedelta

DISTANCES = {
    # key: (label, peak long run km, recommended minimum weeks)
    "5k": ("5K", 8, 8),
    "10k": ("10K", 14, 10),
    "half": ("Half marathon", 18, 12),
    "marathon": ("Marathon", 32, 16),
}

# Week 1 starts from the runner's current weekly km, kept within these limits.
# New runners get a lower ceiling: their body isn't used to running yet,
# even if they already walk-run a fair amount.
START_KM_LIMITS = {"new": (8, 15), "experienced": (12, 70)}

# Weekly volume stops growing here, so short races don't balloon.
MAX_WEEKLY_KM = {"5k": 30, "10k": 45, "half": 55, "marathon": 70}

RACE_KM = {"5k": 5, "10k": 10, "half": 21.1, "marathon": 42.2}

# Shortest runs the plan will schedule. Kept small so a brand-new runner's
# first weeks stay close to their (low) starting volume.
MIN_EASY_KM = 2
MIN_QUALITY_KM = 3.5
RACE_WEEK_EASY_KM = 3


def monday_of(day):
    return day - timedelta(days=day.weekday())


def count_weeks(start_date, race_date):
    """Number of Monday-Sunday weeks touched by the plan, race week included."""
    return (monday_of(race_date) - monday_of(start_date)).days // 7 + 1


def is_too_short(distance, start_date, race_date):
    return count_weeks(start_date, race_date) < DISTANCES[distance][2]


def round_half(km):
    """Round to the nearest 0.5 km so distances look like real runs."""
    return round(km * 2) / 2


def starting_weekly_km(experience, current_km, distance):
    """Week 1 volume: the runner's current weekly km, within sensible limits."""
    low, high = START_KM_LIMITS[experience]
    return min(max(current_km, low), high, MAX_WEEKLY_KM[distance])


def weekly_targets(total_weeks, start_km, distance):
    """Planned km for each week, plus whether that week is a cutback or taper week."""
    taper_weeks = 2 if total_weeks >= 8 else 1
    build_weeks = total_weeks - taper_weeks

    weeks = []
    peak = start_km
    for week_number in range(1, build_weeks + 1):
        if week_number % 4 == 0:
            # Cutback: drop volume to let the body recover, then resume
            # building from where we were before the cutback.
            weeks.append({"km": peak * 0.75, "kind": "cutback"})
            continue
        if week_number > 1:
            peak = min(peak * 1.10, MAX_WEEKLY_KM[distance])
        weeks.append({"km": peak, "kind": "build"})

    # Taper: the week before race week is ~70% of peak. Race week is just
    # short easy runs plus the race (see generate_plan).
    if taper_weeks == 2:
        weeks.append({"km": peak * 0.7, "kind": "taper"})
    weeks.append({"km": 0, "kind": "race"})
    return weeks


def long_run_targets(weeks, distance):
    """Long run km for each week.

    Starts at 30% of the week, then ramps steadily (at most 3 km more per
    build week) toward the distance's peak (8/14/18/32 km). With only 30% of
    a beginner-sized week, the long run would never get near those peaks, so
    late in the plan it becomes a bigger share of the week, as it does in
    common beginner plans.
    """
    peak_long = DISTANCES[distance][1]
    start_long = weeks[0]["km"] * 0.30
    build_count = sum(1 for w in weeks if w["kind"] == "build")
    step = min(3, (peak_long - start_long) / max(1, build_count - 1))

    longs = []
    ramp = start_long
    builds_seen = 0
    for week in weeks:
        if week["kind"] == "build":
            ramp = start_long + step * builds_seen
            builds_seen += 1
            long_km = max(week["km"] * 0.30, ramp)
        elif week["kind"] == "cutback":
            long_km = ramp * 0.75
        elif week["kind"] == "taper":
            long_km = ramp * 0.6
        else:  # race week: the race itself is the long run
            long_km = 0
        longs.append(min(long_km, peak_long))
    return longs


def describe(run_type, km, distance):
    if run_type == "easy":
        return f"Easy {km:g} km at a relaxed, conversational pace."
    if run_type == "long":
        return f"Long run of {km:g} km, slow and steady. Practise drinking and fuelling."
    if run_type == "tempo":
        middle = max(1, round_half(km - 2))
        return (f"1 km easy warm-up, {middle:g} km at a comfortably hard pace "
                f"(you can speak a few words, not full sentences), 1 km easy cool-down.")
    if run_type == "intervals":
        # Each 400 m fast + 400 m jog is 0.8 km, after 2 km of warm-up/cool-down.
        repeats = max(2, round((km - 2) / 0.8))
        return (f"1 km easy warm-up, then {repeats} x 400 m fast with 400 m easy jog "
                f"between, then 1 km easy cool-down.")
    if run_type == "race":
        return f"Race day! {DISTANCES[distance][0]} ({RACE_KM[distance]:g} km). Start easy, finish strong."
    return ""


def make_run(day, run_type, km, distance):
    return {
        "date": day,
        "type": run_type,
        "distance_km": km,
        "description": describe(run_type, km, distance),
    }


def generate_plan(experience, current_km, run_days, long_day, distance, start_date, race_date):
    """Return the full list of runs.

    current_km is how much the runner runs per week now.
    run_days and long_day use Python weekday numbers (Monday = 0).
    """
    total_weeks = count_weeks(start_date, race_date)
    start_km = starting_weekly_km(experience, current_km, distance)
    weeks = weekly_targets(total_weeks, start_km, distance)
    longs = long_run_targets(weeks, distance)
    first_monday = monday_of(start_date)

    runs = []
    for i, week in enumerate(weeks):
        monday = first_monday + timedelta(weeks=i)
        days = [monday + timedelta(days=d) for d in sorted(run_days)]
        # Only train between the start date and the day before the race.
        days = [d for d in days if start_date <= d < race_date]

        if week["kind"] == "race":
            # Keep race week light: short easy runs, nothing the day before.
            for day in days:
                if (race_date - day).days > 1:
                    runs.append(make_run(day, "easy", RACE_WEEK_EASY_KM, distance))
            continue

        long_date = next((d for d in days if d.weekday() == long_day), None)
        long_km = round_half(longs[i]) if long_date else 0

        # Quality run: first run day that isn't the long run or the day
        # before it, so hard efforts don't stack up.
        quality_date = None
        for d in days:
            if long_date and (d == long_date or (long_date - d).days == 1):
                continue
            quality_date = d
            break
        quality_type = "tempo" if i % 2 == 0 else "intervals"
        quality_km = max(MIN_QUALITY_KM, round_half(week["km"] * 0.2)) if quality_date else 0

        easy_days = [d for d in days if d not in (long_date, quality_date)]
        left_over = week["km"] - long_km - quality_km
        easy_km = max(MIN_EASY_KM, round_half(left_over / len(easy_days))) if easy_days else 0

        for day in days:
            if day == long_date:
                runs.append(make_run(day, "long", long_km, distance))
            elif day == quality_date:
                runs.append(make_run(day, quality_type, quality_km, distance))
            else:
                runs.append(make_run(day, "easy", easy_km, distance))

    runs.append(make_run(race_date, "race", RACE_KM[distance], distance))
    return runs
