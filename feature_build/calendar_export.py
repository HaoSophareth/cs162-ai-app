"""Writes a calendar file (.ics, RFC 5545) from a list of all-day events.

Plain functions, no web or database code and no extra libraries.
"""

from datetime import datetime, timedelta, timezone


def escape_text(text):
    """Escape the characters that have a special meaning in calendar text."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for char, escaped in (("\\", r"\\"), (";", r"\;"), (",", r"\,"), ("\n", r"\n")):
        text = text.replace(char, escaped)
    return text


def fold_line(line):
    """Split a long line: the format allows 75 bytes per line, and a line
    starting with a space continues the one before it. Never cuts a character."""
    parts = []
    current = ""
    size = 0
    for char in line:
        char_size = len(char.encode("utf-8"))
        if size + char_size > 75:
            parts.append(current)
            current = " "
            size = 1
        current += char
        size += char_size
    parts.append(current)
    return parts


def build_calendar(name, events):
    """Return the file's text. Each event is a dict with uid, date, title, details."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Race Training Planner//EN",
             "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{escape_text(name)}"]
    for event in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event['uid']}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{event['date']:%Y%m%d}",
            # All-day event: the end date is exclusive, so it's the next day.
            f"DTEND;VALUE=DATE:{event['date'] + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escape_text(event['title'])}",
            f"DESCRIPTION:{escape_text(event['details'])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "".join(part + "\r\n" for line in lines for part in fold_line(line))
