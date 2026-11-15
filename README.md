# MLB Scoreboard Schedule

A compact, vertically scrolling upcoming-game schedule plugin for [MLB-LED-Scoreboard](https://github.com/MLB-LED-Scoreboard/mlb-led-scoreboard) using its native `bullpen` plugin API.

Designed for 64x32 LED matrix displays.

## Features

- Choose **All Games** or **One Team** in the plugin configuration.
- In team mode, choose any MLB team by its three-letter abbreviation.
- Compact matchup rows with local date and start time.
- Doubleheaders are listed as separate games.
- Upcoming games scroll upward once and stop at the end of the list (no endless repeat).
- Schedule data refreshes every 30 minutes by default.
- Uses the MLB Stats API; no API key is required.

## Install

From the MLB-LED-Scoreboard installation directory, install this repository into the same Python environment used by the scoreboard:

```bash
python3 -m pip install git+https://github.com/MorgulWWIV/mlb-scoreboard-schedule.git
```

Restart MLB-LED-Scoreboard after installing.

## Configure

Add the plugin under the top-level `plugins` object in `config.json`:

```json
{
  "plugins": {
    "mlb_team_schedule": {
      "mode": "all",
      "team": "NYY",
      "days_ahead": 14,
      "max_games": 60,
      "refresh_minutes": 30
    }
  }
}
```

### Options

| Setting | Values | Default | Description |
|---|---|---:|---|
| `mode` | `all`, `team` | `all` | Show all MLB games or only one team's games |
| `team` | MLB abbreviation | `NYY` | Team to show when mode is `team` |
| `days_ahead` | 1–30 | `14` | How far ahead to request the schedule |
| `max_games` | 1–200 | `60` | Maximum games displayed |
| `refresh_minutes` | 5–240 | `30` | Schedule refresh interval |

Supported team abbreviations: ATL, AZ, BAL, BOS, CHC, CWS, CIN, CLE, COL, DET, HOU, KC, LAA, LAD, MIA, MIL, MIN, NYM, NYY, OAK, PHI, PIT, SD, SEA, SF, STL, TB, TEX, TOR, WSH.

## Display behavior

The renderer uses a compact 3x5 pixel font and scrolls the game list upward one pixel at a time. It stops when the final games are visible. The date and start time are shown in the Raspberry Pi's local time zone.

## Development

The plugin registers the entry point `bullpen.mlbled.plugin` with the ID `mlb_team_schedule`.
