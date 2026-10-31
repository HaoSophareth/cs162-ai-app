import math
from datetime import timedelta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

RACE_KM = {"5k": 5.0, "10k": 10.0, "half": 21.1, "marathon": 42.2}
PEAK_LONG_RUN_KM = {"5k": 8, "10k": 14, "half": 18, "marathon": 32}
RECOMMENDED_WEEKS = {"5k": 8, "10k": 10, "half": 12, "marathon": 18}
# The plan starts from the runner's current weekly km, but never below this floor,
# so someone starting from zero still gets real runs. The floor is lower for new runners.
MIN_START_KM = {False: 8, True: 12}

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


def weekly_volumes(has_run_before, weekly_km, race_distance, num_weeks):
    # Peak week is the one where the long run (30%) reaches its peak distance.
    peak = PEAK_LONG_RUN_KM[race_distance] / 0.3
    base = min(max(weekly_km, MIN_START_KM[has_run_before]), peak)
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


def generate_plan(has_run_before, weekly_km, run_days, long_run_day, race_distance, start_date, race_date):
    """Return a list of runs (dicts with date, run_type, distance_km, description)."""
    first_monday = monday_of(start_date)
    num_weeks = (monday_of(race_date) - first_monday).days // 7 + 1
    volumes = weekly_volumes(has_run_before, weekly_km, race_distance, num_weeks)
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


# Race estimates. best_times maps a race distance key ("5k", "10k", "half",
# "marathon") to a recent finish time in seconds.
RIEGEL_EXPONENT = 1.06
TRAINING_GAIN = 0.03  # the fast end of the estimate assumes training makes you 3% faster


def pace_per_km(seconds, km):
    return round(seconds / km)


def riegel(time1, km1, km2):
    # Riegel formula: time2 = time1 x (distance2 / distance1) ^ 1.06
    return time1 * (km2 / km1) ** RIEGEL_EXPONENT


def current_paces(best_times):
    return {distance: pace_per_km(seconds, RACE_KM[distance]) for distance, seconds in best_times.items()}


def estimate_finish(best_times, race_distance):
    """Return the estimated finish range and paces for the race, or None without times."""
    if not best_times:
        return None
    race_km = RACE_KM[race_distance]
    # Riegel is most accurate between similar distances, so use the recent time whose
    # distance is closest to the race (compared as a ratio, so 5k->10k beats 10k->marathon).
    source = min(best_times, key=lambda d: abs(math.log(RACE_KM[d] / race_km)))
    today = riegel(best_times[source], RACE_KM[source], race_km)
    trained = today * (1 - TRAINING_GAIN)
    return {
        "based_on": source,
        "slow": round(today),
        "fast": round(trained),
        "slow_pace": pace_per_km(today, race_km),
        "fast_pace": pace_per_km(trained, race_km),
        # Aim for the middle of the range on race day.
        "target_pace": pace_per_km((today + trained) / 2, race_km),
    }
