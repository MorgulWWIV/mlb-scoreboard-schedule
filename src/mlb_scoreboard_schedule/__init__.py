"""Upcoming MLB schedule plugin for MLB-LED-Scoreboard."""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

import bullpen.api as api

if TYPE_CHECKING:
    from RGBMatrixEmulator.emulation.canvas import Canvas


TEAM_IDS = {
    "LAA": 108, "AZ": 109, "BAL": 110, "BOS": 111, "CHC": 112,
    "CIN": 113, "CLE": 114, "COL": 115, "DET": 116, "HOU": 117,
    "KC": 118, "LAD": 119, "WSH": 120, "NYM": 121, "OAK": 133,
    "PIT": 134, "SD": 135, "SEA": 136, "SF": 137, "STL": 138,
    "TB": 139, "TEX": 140, "TOR": 141, "MIN": 142, "PHI": 143,
    "ATL": 144, "CWS": 145, "MIA": 146, "NYY": 147, "MIL": 158,
}
TEAM_ABBR = {team_id: abbr for abbr, team_id in TEAM_IDS.items()}

# Header and game details use the original 3x5 font.
FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("111", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("111", "100", "101", "101", "111"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "111"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("111", "101", "101", "111", "001"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("111", "100", "111", "001", "111"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "/": ("001", "001", "010", "100", "100"),
    ":": ("000", "010", "000", "010", "000"),
    "@": ("111", "101", "111", "100", "111"),
    "-": ("000", "000", "111", "000", "000"),
    ".": ("000", "000", "000", "000", "010"),
    " ": ("000", "000", "000", "000", "000"),
}


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        raw = base.plugin_config
        mode = str(raw.get("mode", "all")).lower()
        self.mode = mode if mode in ("all", "team") else "all"

        team = str(raw.get("team", "NYY")).upper()
        self.team = team if team in TEAM_IDS else "NYY"

        self.days_ahead = _bounded_int(raw.get("days_ahead", 14), 14, 1, 365)
        self.max_games = _bounded_int(raw.get("max_games", 60), 60, 1, 200)
        self.refresh_seconds = _bounded_int(raw.get("refresh_minutes", 30), 30, 5, 240) * 60
        self.scrolling_speed = max(0.03, float(base.scrolling_speed))


class Data(api.PluginData):
    def __init__(self, config: Config) -> None:
        self.config = config
        self.games: list[dict] = []
        self.last_update = 0.0
        self.last_error: str | None = None
        self.last_signature: tuple | None = None

    def update(self, force: bool = False) -> api.UpdateStatus:
        now_mono = time.monotonic()
        if not force and now_mono - self.last_update < self.config.refresh_seconds:
            return api.UpdateStatus.DEFERRED

        today = dt.datetime.now().astimezone().date()
        end_date = today + dt.timedelta(days=self.config.days_ahead)
        params = urllib.parse.urlencode({
            "sportId": 1,
            "startDate": today.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": "team",
        })
        url = f"https://statsapi.mlb.com/api/v1/schedule?{params}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "mlb-scoreboard-schedule/0.1"},
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))

            now = dt.datetime.now().astimezone()
            games: list[dict] = []
            for date_block in payload.get("dates", []):
                for game in date_block.get("games", []):
                    game_time = _parse_game_time(game.get("gameDate"))
                    if game_time is None or game_time < now:
                        continue

                    teams = game.get("teams", {})
                    away = teams.get("away", {}).get("team", {})
                    home = teams.get("home", {}).get("team", {})
                    away_id = away.get("id")
                    home_id = home.get("id")
                    if not away_id or not home_id:
                        continue

                    away_abbr = TEAM_ABBR.get(away_id, _short_name(away.get("name", "AWY")))
                    home_abbr = TEAM_ABBR.get(home_id, _short_name(home.get("name", "HOM")))

                    if self.config.mode == "team":
                        selected_id = TEAM_IDS[self.config.team]
                        if selected_id not in (away_id, home_id):
                            continue

                    games.append({
                        "date": game_time.strftime("%m/%d"),
                        "time": game_time.strftime("%I:%M %p").lstrip("0"),
                        "away": away_abbr,
                        "home": home_abbr,
                        "game_pk": game.get("gamePk"),
                        "timestamp": game_time.timestamp(),
                    })

            games.sort(key=lambda item: item["timestamp"])
            games = games[: self.config.max_games]
            self.games = games
            self.last_signature = tuple((g["game_pk"], g["timestamp"]) for g in games)
            self.last_error = None
            self.last_update = now_mono
            return api.UpdateStatus.SUCCESS

        except Exception as exc:
            self.last_error = str(exc)
            self.last_update = now_mono
            return api.UpdateStatus.FAIL


class Renderer(api.PluginRenderer["Data"]):
    HEADER_HEIGHT = 7
    ROW_HEIGHT = 14
    BOTTOM_MARGIN = 1

    def __init__(self, config: Config, layout: api.Layout, colors: api.Color) -> None:
        self.config = config
        self.layout = layout
        self.colors = colors
        self.background = colors.graphics_color("default.background")
        self.offset = 0
        self.last_signature: tuple | None = None
        self.header_rgb = (255, 170, 0)
        self.text_rgb = (235, 245, 255)
        self.matchup_rgb = (255, 0, 0)
        self.date_rgb = (0, 255, 0)

    def wait_time(self) -> float:
        # Increase the frame delay by 50% for a gentler scroll.
        return self.config.scrolling_speed * 1.5

    def reset(self) -> None:
        self.offset = 0
        self.last_signature = None

    def render(
        self,
        data: Data,
        canvas: "Canvas",
        graphics: api.renderer.graphics,
        scrolling_text_pos: int,
    ) -> None:
        if data.last_signature != self.last_signature:
            self.offset = 0
            self.last_signature = data.last_signature

        # Force unused pixels to true black (RGB 0, 0, 0).
        canvas.Fill(0, 0, 0)

        # Keep the heading fixed while only the game list scrolls.
        self._draw_text(canvas, "UPCOMING GAMES", 11, 0, self.header_rgb)

        if data.last_error and not data.games:
            self._draw_text(canvas, "DATA UNAVAILABLE", 0, 12, (255, 70, 70))
            return

        if not data.games:
            self._draw_text(canvas, "NO UPCOMING GAMES", 0, 12, self.text_rgb)
            return

        viewport_height = self.layout.height - self.HEADER_HEIGHT - self.BOTTOM_MARGIN
        content_height = len(data.games) * self.ROW_HEIGHT
        max_offset = max(0, content_height - viewport_height)
        self.offset = min(self.offset + 1, max_offset)

        for index, game in enumerate(data.games):
            y = self.HEADER_HEIGHT + index * self.ROW_HEIGHT - self.offset
            if y < self.layout.height and y + 11 > self.HEADER_HEIGHT:
                self._draw_text(canvas, f'{game["away"]} @ {game["home"]}', 0, y, self.matchup_rgb, clip_top=self.HEADER_HEIGHT)
                self._draw_text(canvas, f'{game["date"]} - {game["time"]}', 0, y + 6, self.date_rgb, clip_top=self.HEADER_HEIGHT)

    @staticmethod
    def _draw_text(canvas: "Canvas", text: str, x: int, y: int, rgb: tuple[int, int, int], clip_top: int = 0) -> None:
        red, green, blue = rgb
        cursor_x = x
        for char in text.upper():
            glyph = FONT.get(char, FONT[" "])
            for row_index, pattern in enumerate(glyph):
                py = y + row_index
                if py < clip_top or py >= canvas.height:
                    continue
                for column_index, pixel in enumerate(pattern):
                    px = cursor_x + column_index
                    if pixel == "1" and 0 <= px < canvas.width:
                        canvas.SetPixel(px, py, red, green, blue)
            cursor_x += 3
            if cursor_x >= canvas.width:
                break


def _parse_game_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone()
    except (TypeError, ValueError):
        return None


def _short_name(name: str) -> str:
    return "".join(part[0] for part in name.split() if part)[:3].upper()


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def load() -> api.PLUGIN_DEFINITION:
    return Config, Data, Renderer
