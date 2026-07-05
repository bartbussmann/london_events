#!/usr/bin/env python3
"""Pull events from the ICS feeds listed in sources.yaml into data/events.json.

    python3 scripts/fetch_ics.py

For each feed under the `ics:` section of sources.yaml, download the calendar,
parse its VEVENTs, and merge upcoming ones into data/events.json (skipping any
whose UID-derived id is already present). Run scripts/build.py afterwards to
validate, dedup, and regenerate calendar.ics.

Stdlib only; the sources.yaml reader supports exactly the documented format
(a list of `- name:` / `url:` / `tags:` entries per section).
"""

import json
import re
import sys
import hashlib
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT / "sources.yaml"
EVENTS_PATH = ROOT / "data" / "events.json"

HORIZON_DAYS = 60  # ignore feed events further out than this


def read_ics_sources() -> list:
    """Minimal reader for the `ics:` section of sources.yaml."""
    if not SOURCES_PATH.exists():
        return []
    sources, current, in_ics = [], None, False
    for raw in SOURCES_PATH.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_ics = line.strip() == "ics:"
            continue
        if not in_ics:
            continue
        m = re.match(r"\s*-\s+name:\s*(.+)", line)
        if m:
            current = {"name": m.group(1).strip().strip('"'), "url": None, "tags": []}
            sources.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"\s+url:\s*(\S+)", line)
        if m:
            current["url"] = m.group(1).strip('"')
            continue
        m = re.match(r"\s+tags:\s*\[(.*)\]", line)
        if m:
            current["tags"] = [t.strip().strip('"') for t in m.group(1).split(",") if t.strip()]
    return [s for s in sources if s["url"]]


def unfold(text: str) -> list:
    lines, out = text.replace("\r\n", "\n").split("\n"), []
    for line in lines:
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def ics_unescape(text: str) -> str:
    return (text.replace("\\n", "\n").replace("\\N", "\n")
                .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"))


def parse_ics_dt(prop: str, value: str) -> datetime | None:
    value = value.strip()
    try:
        if re.fullmatch(r"\d{8}", value):  # all-day date
            return datetime.strptime(value, "%Y%m%d").replace(
                hour=10, tzinfo=timezone.utc)
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc)
        # Naive or TZID-qualified local time: assume Europe/London offset is
        # embedded upstream; treat as UTC+1 in summer, +0 otherwise.
        dt = datetime.strptime(value, "%Y%m%dT%H%M%S")
        offset = 1 if 3 < dt.month < 11 else 0
        return dt.replace(tzinfo=timezone(timedelta(hours=offset)))
    except ValueError:
        return None


def parse_vevents(text: str) -> list:
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, value = line.split(":", 1)
            prop = key.split(";", 1)[0].upper()
            cur[prop] = (key, value)
    return events


def main() -> None:
    sources = read_ics_sources()
    if not sources:
        print("no ICS sources configured in sources.yaml — nothing to do")
        return

    existing = json.loads(EVENTS_PATH.read_text()) if EVENTS_PATH.exists() else []
    known_ids = {e.get("id") for e in existing}
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=HORIZON_DAYS)
    added = 0

    for src in sources:
        try:
            with urllib.request.urlopen(src["url"], timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"warn: could not fetch {src['name']} ({src['url']}): {exc}",
                  file=sys.stderr)
            continue

        for ev in parse_vevents(body):
            summary = ics_unescape(ev.get("SUMMARY", ("", ""))[1]).strip()
            dtstart = ev.get("DTSTART")
            if not summary or not dtstart:
                continue
            start = parse_ics_dt(*dtstart)
            if not start or not (now - timedelta(days=1) <= start <= horizon):
                continue
            end = parse_ics_dt(*ev["DTEND"]) if "DTEND" in ev else None
            uid = ev.get("UID", ("", f"{summary}|{start.isoformat()}"))[1]
            eid = ("ics-" + hashlib.sha1(
                f"{src['url']}|{uid}".encode()).hexdigest()[:12])
            if eid in known_ids:
                continue
            url = ev.get("URL", ("", src["url"]))[1].strip() or src["url"]
            if not url.startswith(("http://", "https://")):
                url = src["url"]
            existing.append({
                "id": eid,
                "title": summary,
                "start": start.isoformat(),
                "end": end.isoformat() if end else None,
                "venue": ics_unescape(ev.get("LOCATION", ("", ""))[1]).strip() or src["name"],
                "address": None,
                "url": url,
                "source": f"ics:{src['name']}",
                "tags": src.get("tags") or [],
                "price": None,
                "description": ics_unescape(
                    ev.get("DESCRIPTION", ("", ""))[1]).strip()[:300] or None,
                "added": now.date().isoformat(),
            })
            known_ids.add(eid)
            added += 1

    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n")
    print(f"ok: {added} new events merged from {len(sources)} feed(s); "
          f"now run scripts/build.py")


if __name__ == "__main__":
    main()
