# London Events

A personal event-aggregation calendar. Autonomous agent sweeps check calendar
feeds, venue pages, and keyword web searches on a schedule, judge candidates
against [`preferences.md`](preferences.md), and commit the interesting ones to
[`data/events.json`](data/events.json). The calendar itself is a static site —
no server, no database.

## How it fits together

```
sources.yaml ─┐
preferences.md ├─▶ scheduled agent sweep ─▶ data/events.json ─▶ index.html (GitHub Pages)
web searches ─┘         (Claude Code Routine)        └─▶ calendar.ics (subscribe from Google Calendar)
```

- **`index.html`** — the calendar site (month + list view, tag filters, search).
  Fully static; reads `data/events.json`.
- **`data/events.json`** — the event store. Every addition is a commit, so the
  git history is the audit log of what was found when, and by which sweep.
- **`calendar.ics`** — generated feed; subscribe to it from Google/Apple
  Calendar so events appear on your phone.
- **`sources.yaml`** — where the agents look. Edit any time.
- **`preferences.md`** — what "interesting" means. Edit any time.
- **`AGENTS.md`** — the playbook each scheduled agent run follows.
- **`scripts/build.py`** — validates + de-duplicates + prunes past events +
  regenerates `calendar.ics`. Run after any manual edit to the event data.
- **`scripts/fetch_ics.py`** — deterministic importer for ICS feeds in
  `sources.yaml`.

## Setup (one-time)

1. **Enable GitHub Pages**: repo Settings → Pages → Source: **GitHub Actions**.
   The `pages.yml` workflow deploys the site on every push to `main`.
2. **Subscribe from Google Calendar** (optional): Other calendars → `+` →
   *From URL* → paste the raw URL of `calendar.ics` on `main`, i.e.
   `https://raw.githubusercontent.com/bartbussmann/london_events/main/calendar.ics`
   (or the GitHub Pages URL `https://<user>.github.io/london_events/calendar.ics`).
3. The agent sweep runs as a **Claude Code Routine** (scheduled session) that
   follows `AGENTS.md` and pushes to `main`. Manage it from your Claude Code
   session (`list_triggers` / pause / delete), or just ask Claude.

## Local development

```bash
python3 -m http.server 8000   # then open http://localhost:8000
python3 scripts/build.py      # after editing data/events.json
```

## Tuning

- More/different sources → edit `sources.yaml`
- Different taste → edit `preferences.md`
- Sweep frequency → adjust the Routine's schedule
- Event retention/validation rules → `scripts/build.py`
