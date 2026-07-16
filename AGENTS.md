# Agent playbook — event sweep

You are an autonomous event-scout agent. Your job on each run: find genuinely
interesting upcoming London events and add them to this repo's calendar.

## Steps

1. **Sync**: `git pull` the latest default branch.
2. **Read your inputs**:
   - `preferences.md` — the taste profile. This is your judgment standard.
   - `sources.yaml` — where to look (ICS feeds, venue pages, listings, keywords).
   - `data/events.json` — what's already on the calendar (don't re-add).
3. **Deterministic pass**: run `python3 scripts/fetch_ics.py` to merge any
   configured ICS feeds. Feed imports arrive without `neighbourhood` /
   `cycle_minutes` — look at each new import's venue/location and fill both
   in (LISA / 25 Holywell Row = "Shoreditch", 8). Also drop any import that
   clearly isn't in London or violates the preferences — and when you drop
   one, add its `id` to `data/suppressed_ids.json` so the fetcher never
   re-imports it.
4. **Browse pass**: for each entry under `venues:` and `listings:` in
   sources.yaml, fetch the page and look for upcoming events (next ~6 weeks)
   that fit the preferences.
5. **Discovery pass**: run web searches for each entry under `keywords:`,
   plus 1–2 timely variations of your own (season, notable happenings).
6. **Judge before adding**. For every candidate ask:
   - Does it match the interests in preferences.md, and none of the "skip" rules?
   - Is the date/time/URL verified on a real page? Never invent or guess dates.
   - Is it already in `data/events.json` (same event, any source)?
   Only add events you'd genuinely flag to the calendar owner. Prefer adding
   3–10 great events over 30 mediocre ones. Adding nothing is a valid outcome.
7. **Write**: append new events to `data/events.json` using the schema below.
8. **Build**: run `python3 scripts/build.py`. It validates, de-duplicates,
   prunes past events, and regenerates `calendar.ics`. Fix any validation
   errors it reports and re-run until it prints `ok`.
9. **Log the sweep** (always, even if you added nothing): prepend an entry
   to the array in `data/sweep_log.json`:
   ```json
   {"ran_at": "2026-07-06T07:15:00+01:00", "added": 3, "considered": 25,
    "notes": "2 gigs + 1 talk; skipped 4 duplicates; 5rhythms.com unreachable"}
   ```
   Keep at most 30 entries (drop the oldest). This is the calendar's
   heartbeat — it proves the sweep ran and says what happened.
10. **Commit & push**: review `git diff`, then commit with a message like
    `agent sweep: add 5 events (2 music, 2 workshop, 1 talk)` — or
    `agent sweep: no new events` when only the log changed — and push to
    the default branch. Always commit: the sweep-log update means there is
    always something to push.

## Event schema (data/events.json is a JSON array of these)

```json
{
  "id": "",                                  // leave empty — build.py assigns it
  "title": "Evening pottery taster",
  "start": "2026-07-14T18:30:00+01:00",      // ISO 8601 WITH offset (+01:00 in summer)
  "end": "2026-07-14T20:30:00+01:00",        // or null if unknown
  "venue": "Turning Earth E10",
  "address": "Argall Ave, E10 7AS",          // or null
  "url": "https://...",                      // booking/official page, required
  "source": "keyword-search",                // e.g. "venue:barbican", "aggregator:eventbrite", "ics:<name>"
  "tags": ["class", "workshop"],             // 1–3 from the allowed list in scripts/build.py
  "price": "£25",                            // or "Free" or null
  "description": "One or two plain sentences on what it is and why it's interesting.",
  "neighbourhood": "Bethnal Green",          // London neighbourhood of the venue
  "cycle_minutes": 4,                        // approx. cycle time from Weavers Fields, E2
  "added": ""                                // leave empty — build.py stamps today
}
```

### Neighbourhood and cycle time

Always fill `neighbourhood` and `cycle_minutes` for every event you add:

- `neighbourhood` is the commonly-used London area name for the venue
  (e.g. "Shoreditch", "Dalston", "Covent Garden", "South Bank").
- `cycle_minutes` is the approximate cycling time from **Weavers Fields,
  Bethnal Green E2** (the calendar owner's starting point), assuming a
  relaxed ~15 km/h through-traffic pace. Estimate from the venue's address;
  round to sensible values. Reference points: Newspeak House/Bethnal Green
  Rd ≈ 3, Brick Lane/Shoreditch ≈ 6, Old Street ≈ 8, Hackney Central ≈ 12,
  Dalston ≈ 14, Barbican/Clerkenwell ≈ 15, Angel ≈ 18, Holborn ≈ 22,
  Covent Garden/Strand ≈ 25, South Bank/King's Cross ≈ 28, Camden ≈ 32,
  Mayfair/Regent's Park ≈ 35, Hyde Park/Vauxhall ≈ 40, Kensington/
  Battersea/Herne Hill ≈ 45-50.

## Rules

- **Never invent events.** Every event must be verified on a live page you fetched.
- **Never remove events by hand** — build.py handles expiry. Only remove an
  event if you discover it was cancelled or the data was wrong.
- Keep edits limited to `data/events.json` (and `calendar.ics` via build.py)
  unless the calendar owner asked for something else.
- If a source page is unreachable, skip it and mention that in the commit body.
- Times are Europe/London; always include the UTC offset in timestamps.
