from datetime import timedelta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

RACE_KM = {"5k": 5.0, "10k": 10.0, "half": 21.1, "marathon": 42.2}
PEAK_LONG_RUN_KM = {"5k": 8, "10k": 14, "half": 18, "marathon": 32}
RECOMMENDED_WEEKS = {"5k": 8, "10k": 10, "half": 12, "marathon": 18}
# Longer races start from a higher base so the long run can get near its peak in time.
START_WEEKLY_KM = {
    "new": {"5k": 10, "10k": 15, "half": 20, "marathon": 25},
    "experienced": {"5k": 15, "10k": 22, "half": 30, "marathon": 40},
}

DESCRIPTIONS = {
    "easy": "Easy run at a relaxed pace where you could hold a conversation.",
    "long": "Long run at an easy, steady pace. The goal is time on your feet, not speed.",
    "tempo": "Warm up 2 km easy, run the middle part at a comfortably hard pace, then cool down 1-2 km easy.",
    "intervals": "Warm up 2 km easy, then 400-800 m fast repeats with 2 minutes of easy jogging between, then cool down easy.",
    "race": "Race day! Start a little slower than you want to, settle in, and enjoy it.",
}


def round_km(km):
    # Half-km steps are easy to read, and no run is shorter than 2 km.
    return max(2.0, round(km * 2) / 2)


def monday_of(day):
    return day - timedelta(days=day.weekday())


def weekly_volumes(experience, race_distance, num_weeks):
    # Peak week is the one where the long run (30%) reaches its peak distance.
    peak = PEAK_LONG_RUN_KM[race_distance] / 0.3
    base = min(START_WEEKLY_KM[experience][race_distance], peak)
    taper = [0.7, 0.4] if num_weeks >= 6 else [0.4]
    build_weeks = max(num_weeks - len(taper), 0)

    volumes = []
    for week in range(1, build_weeks + 1):
        if week % 4 == 0:
            # Cutback week: lighter, and the next week grows from the level before it.
            volumes.append(base * 0.75)
        else:
            if week > 1:
                base = min(base * 1.1, peak)
            volumes.append(base)
    for factor in taper:
        volumes.append(base * factor)
    return volumes


def generate_plan(experience, run_days, long_run_day, race_distance, start_date, race_date):
    """Return a list of runs (dicts with date, run_type, distance_km, description)."""
    first_monday = monday_of(start_date)
    num_weeks = (monday_of(race_date) - first_monday).days // 7 + 1
    volumes = weekly_volumes(experience, race_distance, num_weeks)
    # With only 3 days, 30% would make the long run shorter than the other runs.
    long_share = 0.4 if len(run_days) == 3 else 0.3

    runs = []
    for week_index, volume in enumerate(volumes):
        week_start = first_monday + timedelta(weeks=week_index)
        is_race_week = week_index == num_weeks - 1
        quality_type = "tempo" if week_index % 2 == 0 else "intervals"

        days = [week_start + timedelta(days=DAYS.index(d)) for d in DAYS if d in run_days]
        days = [d for d in days if start_date <= d < race_date]
        if not days:
            continue

        # Race week has no long run or hard workout, just a few easy runs before the race.
        long_day = None
        if not is_race_week:
            long_day = next((d for d in days if DAYS[d.weekday()] == long_run_day), None)
        long_km = min(volume * long_share, PEAK_LONG_RUN_KM[race_distance]) if long_day else 0
        other_days = [d for d in days if d != long_day]
        # Split by the full week's day count so a partial first week is just shorter.
        other_km = (volume - long_km) / (len(run_days) - 1)

        for day in days:
            if day == long_day:
                run_type, km = "long", long_km
            elif not is_race_week and day == other_days[0]:
                run_type, km = quality_type, other_km
            else:
                run_type, km = "easy", other_km
            runs.append({
                "date": day,
                "run_type": run_type,
                "distance_km": round_km(km),
                "description": DESCRIPTIONS[run_type],
            })

    runs.append({
        "date": race_date,
        "run_type": "race",
        "distance_km": RACE_KM[race_distance],
        "description": DESCRIPTIONS["race"],
    })
    return runs
