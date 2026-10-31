"""Race time maths for the plan summary: paces and finish-time estimates.

Plain functions, no web or database code. Times are handled as seconds.
"""

# A few percent faster than today: what the plan's training is assumed to add.
TRAINING_GAIN = 0.03

# Riegel's fatigue exponent: time2 = time1 * (distance2 / distance1) ** 1.06
RIEGEL_EXPONENT = 1.06


def parse_time(text):
    """'27:30' (mm:ss) or '1:58:00' (h:mm:ss) -> seconds."""
    seconds = 0
    for part in text.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def format_time(seconds):
    """Seconds -> 'h:mm:ss', or 'm:ss' when under an hour."""
    seconds = round(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_pace(seconds, km):
    """Pace per km, e.g. '5:24 /km'."""
    return format_time(seconds / km) + " /km"


def riegel(seconds, from_km, to_km):
    """Predicted time over to_km from a race of from_km run in `seconds`."""
    return seconds * (to_km / from_km) ** RIEGEL_EXPONENT


def best_recent_race(times, goal_km):
    """The strongest of the runner's recent races, or None if they gave none.

    times is a list of (label, km, 'mm:ss' text). Races of different lengths
    can't be compared directly, so "strongest" is the one that predicts the
    fastest time over the goal distance.
    """
    races = [(label, km, parse_time(text)) for label, km, text in times if text]
    if not races:
        return None
    label, km, seconds = min(races, key=lambda race: riegel(race[2], race[1], goal_km))
    return {"label": label, "km": km, "time": format_time(seconds), "pace": format_pace(seconds, km),
            "seconds": seconds}


def finish_estimate(best, goal_km):
    """Estimated finish range over goal_km, from the best recent race.

    slow: what they could run today. fast: after training makes them a few
    percent faster. The race-day target pace sits in the middle of the range.
    """
    today = riegel(best["seconds"], best["km"], goal_km)
    trained = today * (1 - TRAINING_GAIN)
    middle = (today + trained) / 2
    return {"fast": format_time(trained), "slow": format_time(today),
            "target_pace": format_pace(middle, goal_km)}
