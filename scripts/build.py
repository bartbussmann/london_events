#!/usr/bin/env python3
"""Normalise the event store and regenerate the subscribable calendar feed.

Run after any edit to data/events.json:

    python3 scripts/build.py

It will:
  - validate every event against the schema (see AGENTS.md)
  - assign stable ids to events that lack one
  - de-duplicate (same normalised title + same London date -> keep first)
  - prune events that ended more than PRUNE_AFTER_DAYS ago
  - sort by start time and rewrite data/events.json
  - regenerate calendar.ics (UTC times, importable/subscribable feed)

Exits non-zero with a readable message if any event is malformed, so agents
can fix their edits before committing. Stdlib only.
"""

import json
import re
import sys
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "data" / "events.json"
ICS_PATH = ROOT / "calendar.ics"

PRUNE_AFTER_DAYS = 2  # keep events a couple of days past their date
ALLOWED_TAGS = {
    "music", "art", "theatre", "film", "food", "market", "festival",
    "talk", "comedy", "class", "workshop", "outdoors", "tech", "community",
    "sport", "dance",
}
REQUIRED = ["title", "start", "url", "source"]


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_dt(value: str, field: str, title: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        fail(f"event {title!r}: {field} is not ISO 8601: {value!r}")
    if dt.tzinfo is None:
        fail(f"event {title!r}: {field} must include a UTC offset, e.g. +01:00")
    return dt


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "event"


def make_id(ev: dict) -> str:
    base = f"{ev['title']}|{ev['start']}"
    digest = hashlib.sha1(base.encode()).hexdigest()[:8]
    return f"{slugify(ev['title'])}-{digest}"


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def validate(ev: dict, idx: int) -> None:
    if not isinstance(ev, dict):
        fail(f"event #{idx} is not an object")
    title = ev.get("title") or f"#{idx}"
    for field in REQUIRED:
        if not ev.get(field):
            fail(f"event {title!r}: missing required field {field!r}")
    parse_dt(ev["start"], "start", title)
    if ev.get("end"):
        if parse_dt(ev["end"], "end", title) < parse_dt(ev["start"], "start", title):
            fail(f"event {title!r}: end is before start")
    if not str(ev["url"]).startswith(("http://", "https://")):
        fail(f"event {title!r}: url must be an http(s) link")
    tags = ev.get("tags") or []
    if not isinstance(tags, list):
        fail(f"event {title!r}: tags must be a list")
    if ev.get("cycle_minutes") is not None:
        if not isinstance(ev["cycle_minutes"], (int, float)) or ev["cycle_minutes"] <= 0:
            fail(f"event {title!r}: cycle_minutes must be a positive number")
    if ev.get("neighbourhood") is not None and not isinstance(ev["neighbourhood"], str):
        fail(f"event {title!r}: neighbourhood must be a string")
    unknown = set(tags) - ALLOWED_TAGS
    if unknown:
        fail(f"event {title!r}: unknown tags {sorted(unknown)} "
             f"(allowed: {sorted(ALLOWED_TAGS)})")


def ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def ics_fold(line: str) -> str:
    """Fold content lines at 74 octets per RFC 5545."""
    out, chunk = [], line
    while len(chunk.encode()) > 74:
        cut = 74
        while cut > 1 and len(chunk[:cut].encode()) > 74:
            cut -= 1
        out.append(chunk[:cut])
        chunk = " " + chunk[cut:]
    out.append(chunk)
    return "\r\n".join(out)


def ics_dt(value: str) -> str:
    dt = datetime.fromisoformat(value).astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics(events: list) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//london_events//event-agents//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:London Events",
        "X-WR-TIMEZONE:Europe/London",
    ]
    for ev in events:
        start = datetime.fromisoformat(ev["start"])
        end_raw = ev.get("end")
        end = (datetime.fromisoformat(end_raw) if end_raw
               else start + timedelta(hours=2))
        desc_parts = [ev.get("description") or ""]
        if ev.get("price"):
            desc_parts.append(f"Price: {ev['price']}")
        desc_parts.append(ev["url"])
        location = ", ".join(x for x in [ev.get("venue"), ev.get("address")] if x)
        fields = [
            "BEGIN:VEVENT",
            f"UID:{ev['id']}@london-events",
            f"DTSTAMP:{ics_dt(ev['start'])}",
            f"DTSTART:{ics_dt(ev['start'])}",
            f"DTEND:{end.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{ics_escape(ev['title'])}",
            f"DESCRIPTION:{ics_escape(chr(10).join(p for p in desc_parts if p))}",
            f"URL:{ev['url']}",
        ]
        if location:
            fields.append(f"LOCATION:{ics_escape(location)}")
        fields.append("END:VEVENT")
        lines.extend(fields)
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


def main() -> None:
    if not EVENTS_PATH.exists():
        fail(f"{EVENTS_PATH} not found")
    try:
        events = json.loads(EVENTS_PATH.read_text())
    except json.JSONDecodeError as exc:
        fail(f"data/events.json is not valid JSON: {exc}")
    if not isinstance(events, list):
        fail("data/events.json must be a JSON array")

    for i, ev in enumerate(events):
        validate(ev, i)
        if not ev.get("id"):
            ev["id"] = make_id(ev)
        if not ev.get("added"):
            ev["added"] = datetime.now(timezone.utc).date().isoformat()

    # De-duplicate: same normalised title on the same London date.
    seen, deduped, dropped = set(), [], 0
    for ev in sorted(events, key=lambda e: e.get("added", "")):
        day = datetime.fromisoformat(ev["start"]).date().isoformat()
        key = (norm_title(ev["title"]), day)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        deduped.append(ev)

    # Prune long-past events.
    cutoff = datetime.now(timezone.utc) - timedelta(days=PRUNE_AFTER_DAYS)
    kept = []
    pruned = 0
    for ev in deduped:
        end_str = ev.get("end") or ev["start"]
        if datetime.fromisoformat(end_str) < cutoff:
            pruned += 1
        else:
            kept.append(ev)

    kept.sort(key=lambda e: e["start"])
    EVENTS_PATH.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n")
    ICS_PATH.write_text(build_ics(kept))

    print(f"ok: {len(kept)} events "
          f"({dropped} duplicates removed, {pruned} past events pruned)")


if __name__ == "__main__":
    main()
