# Madison Fantasy League Pro Bowl Scoreboard

A custom East/West matchup built from six ESPN fantasy rosters on each side.
The 2026 Pro Bowl lineups are loaded from the supplied team lists. The matchup
week and private fantasy ownership are not assumed. Selected player metadata
is kept in `data/matchup.json` separately from the annual fantasy roster snapshot.
When a snapshot is available, its ownership labels take precedence.
The original 2025 scoreboard is preserved at `archive-2025.html`.

## Annual roster setup

1. Add the existing ESPN account cookies as repository Actions secrets:
   `ESPN_SWID` and `ESPN_S2`. Never put cookies in HTML, JSON, commits, or logs.
2. Run **ESPN Pro Bowl data → rosters** once when ownership should be captured.
   It stores the twelve sanitized rosters in `data/rosters-2026.json`.
   It will not overwrite an existing snapshot unless `replace_snapshot` is checked.
3. Open **Annual roster setup** on the scoreboard. Assign six fantasy teams to
   each side. Players may remain TBD until the Pro Bowl selections are known.
4. Choose the matchup week and players when ready. Export the setup, then run
   **ESPN Pro Bowl data → configure**, pasting the exported file contents into
   `setup_json`. Enable score refreshes only after selections are complete.

The snapshot contains ESPN player IDs, positions, NFL team IDs, and the owning
fantasy team's name and ID. Ownership is frozen at snapshot time. Later trades
or weekly roster refreshes do not move players between Pro Bowl sides.
No fantasy owner names, member records, email addresses, or cookies are published.
Division IDs are retained as a reference; they are not assumed to define East/West.

## Separate scores and initial projections

`update_scores.py` queries only the selected IDs with `kona_playercard` and
uses weekly `appliedTotal`: source 0 for actual scoring, source 1 for projections.
It never requests `mRoster` or rewrites the roster snapshot or matchup selections.
This uses your ESPN league's scoring rules, including D/ST.

Before kickoff, ESPN weekly projections can update. At kickoff, the last stored
baseline is frozen. A baseline first obtained after kickoff is explicitly marked.
Missing stats stay missing rather than silently becoming zero for live/final games.
Network or partial-response failures preserve the last successful score file.

The browser reloads public data every minute. On GitHub Pages it reads sanitized
JSON directly from the repository so workflow data commits do not depend on a
second Pages build. Local previews read their local JSON files. The Actions workflow requests
updates approximately every five minutes on NFL game days (UTC); GitHub may delay
scheduled jobs. It makes no API requests while the matchup is disabled, and stops
polling after all games are final and the stat-correction window has passed.
Use **scores** for a manual refresh when needed. Score files contain a timestamp
so stale results are visible. This is not a second-by-second live feed.

## ESPN in-game projection findings

The current `cwendt94/espn-api` client reads `totalProjectedPointsLive` on each
scheduled **fantasy team**, but individual BoxPlayer projections come from weekly
projected stat records. A team total cannot be assigned to individual players or
combined into a new Pro Bowl lineup. Authenticated validation against this league
is still required: the saved cookies were not accessible in this session and an
unauthenticated league request returned HTTP 401.

Until a player-level live endpoint is verified or a model is chosen, the site
shows actual points and ESPN **initial** projections. It does not label weekly
projections as live forecasts or display the old uncalibrated win probabilities.

Possible home-grown live models, in increasing complexity:

- Clock baseline: actual points plus the ESPN baseline multiplied by regulation
  time remaining. Simple and transparent, but insensitive to usage/game script.
- Shrunk pace: update the remaining scoring rate from observed performance,
  shrinking toward the ESPN baseline, with position-specific parameters and caps.
- Remaining-opportunity model: estimate remaining drives/snaps and player touches,
  targets or attempts; simulate correlated player outcomes for matchup probabilities.

Any model must use actual totals with zero variance when final, retain uncertainty
in overtime, handle negative scoring and defense separately, and distinguish bye,
DNP, injury, and unavailable data. Validate on historical snapshots before claiming
probability calibration; final box scores alone do not validate in-game forecasts.

Source reviewed: https://github.com/cwendt94/espn-api/tree/master/espn_api/football

## Local use and checks

Python uses only the standard library. With cookies in environment variables:

```bash
python scripts/update_rosters.py
python scripts/configure_matchup.py pro-bowl-setup-2026.json
python scripts/update_scores.py
python -m unittest discover -s tests
python -m http.server 8000
```

Open `http://localhost:8000` to preview. The setup page exports a local file; it
cannot write the shared configuration directly. Querying rosters/scores does not
change anyone's ESPN lineup or make fantasy transactions.
