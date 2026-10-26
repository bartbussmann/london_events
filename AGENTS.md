# Agent playbook — event sweep

You are an autonomous event-scout agent. Your job on each run: find genuinely
interesting upcoming San Francisco / Bay Area events and add them to this repo's calendar.

## Steps

1. **Sync**: `git pull` the latest default branch.
2. **Read your inputs**:
   - `preferences.md` — the taste profile. This is your judgment standard.
   - `sources.yaml` — where to look (ICS feeds, venue pages, listings, keywords).
   - `data/events.json` — what's already on the calendar (don't re-add).
3. **Deterministic pass**: run `python3 scripts/fetch_ics.py` to merge any
   configured ICS feeds. Feed imports arrive without `neighbourhood` /
   `cycle_minutes` — look at each new import's venue/location and fill both
   in (Mox / 1680 Mission St = "Mission", 13). Also drop any import that
   clearly isn't in the Bay Area, is online-only, is a weekday-daytime event,
   or otherwise violates the preferences — and when you drop one, add its `id`
   to `data/suppressed_ids.json` so the fetcher never re-imports it.
4. **Browse pass**: for each entry under `venues:` and `listings:` in
   sources.yaml, fetch the page and look for upcoming events (next ~6 weeks)
   that fit the preferences.
5. **Discovery pass**: run web searches for each entry under `keywords:`,
   plus 1–2 timely variations of your own (season, notable happenings).
6. **Judge before adding**. For every candidate ask:
   - Does it match the interests in preferences.md, and none of the "skip" rules?
   - Is the date/time/URL verified on a real page? Never invent or guess dates.
   - Is it already in `data/events.json` (same event, any source)?
   Add any event that's a decent fit for the preferences — the owner wants
   plenty of daily options, so when in doubt, include it. Aim for 8–15
   additions per sweep when the sources offer them. The hard rules still
   hold (verified dates only, no invented events, respect the skip list),
   but "interesting enough" is a low bar, not a high one.
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
  "start": "2026-11-12T18:30:00-08:00",      // ISO 8601 WITH offset (-07:00 PDT / -08:00 PST)
  "end": "2026-11-12T20:30:00-08:00",        // or null if unknown
  "venue": "Example Ceramics Studio",
  "address": "Folsom St, San Francisco, CA",  // or null
  "url": "https://...",                      // booking/official page, required
  "source": "keyword-search",                // e.g. "venue:barbican", "aggregator:eventbrite", "ics:<name>"
  "tags": ["class", "workshop"],             // 1–3 from the allowed list in scripts/build.py
  "price": "$25",                            // or "Free" or null
  "description": "One or two plain sentences on what it is and why it's interesting.",
  "neighbourhood": "SoMa",                   // San Francisco neighbourhood of the venue
  "cycle_minutes": 5,                        // approx. cycle time from 39 Tehama St, SoMa
  "added": ""                                // leave empty — build.py stamps today
}
```

### Neighbourhood and cycle time

Always fill `neighbourhood` and `cycle_minutes` for every event you add:

- `neighbourhood` is the commonly-used San Francisco / Bay Area name for the
  venue's area (e.g. "SoMa", "Mission", "Hayes Valley", "North Beach",
  "Oakland").
- `cycle_minutes` is the approximate cycling time from **39 Tehama St, SoMa**
  (the calendar owner's home, between 1st & 2nd St near the Salesforce
  Transit Center), assuming a relaxed ~15 km/h pace on bike-friendly routes
  (Market St, the Wiggle) and adding time for real hills. Reference points:
  Salesforce Park/Yerba Buena ≈ 3, Ferry Building/Moscone/SFMOMA ≈ 5,
  Union Square/FiDi ≈ 6, Civic Center/Tenderloin ≈ 8, Chinatown ≈ 9,
  North Beach/Exploratorium (Pier 15) ≈ 10, Dogpatch/Hayes Valley ≈ 11,
  Potrero Hill/Mission (16th St) ≈ 12, Mission (24th St)/Lower Haight ≈ 16,
  Castro/Fillmore/Japantown ≈ 17, Fort Mason/Marina ≈ 22, Haight-Ashbury/
  Noe Valley/Bernal Heights ≈ 22, Golden Gate Park (Cal Academy)/Inner
  Richmond ≈ 27, Presidio ≈ 30, Outer Sunset/Ocean Beach ≈ 45.
- **East Bay / Peninsula** venues aren't a bike ride: set `cycle_minutes` to
  null and say how to get there in the description (e.g. "BART from
  Montgomery, ~25 min to Downtown Berkeley").

## Rules

- **Never invent events.** Every event must be verified on a live page you fetched.
- **Never remove events by hand** — build.py handles expiry. Only remove an
  event if you discover it was cancelled or the data was wrong.
- Keep edits limited to `data/events.json` (and `calendar.ics` via build.py)
  unless the calendar owner asked for something else.
- If a source page is unreachable, skip it and mention that in the commit body.
- Times are America/Los_Angeles; always include the UTC offset in timestamps:
  -07:00 (PDT) until clocks go back on Sun 1 Nov 2026, -08:00 (PST) from then
  until Sun 14 Mar 2027, then -07:00 again.
- The old London calendar is archived on the `london-archive` branch — don't
  touch it.
