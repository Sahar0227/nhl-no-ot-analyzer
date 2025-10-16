import datetime as dt
import math
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import random

from config import (
    NHL_API_BASE,
    CACHE_TTL_TEAM_LIST_SECONDS,
)
from utils.cache import read_cache, write_cache


Session = requests.Session()
Session.headers.update({
    "User-Agent": "nhl-no-ot-analyzer/1.0 (https://github.com)"
})
# More aggressive retry for DNS/connection issues
_retry = Retry(
    total=6, 
    read=3, 
    connect=6, 
    backoff_factor=1.0, 
    status_forcelist=[429, 500, 502, 503, 504], 
    allowed_methods=["GET"]
)
Session.mount("https://", HTTPAdapter(max_retries=_retry))
Session.mount("http://", HTTPAdapter(max_retries=_retry))


def _api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Add jitter to prevent thundering herd
    time.sleep(random.uniform(0.1, 0.5))
    resp = Session.get(f"{NHL_API_BASE}{path}", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_teams(refresh: bool = False) -> Dict[int, Dict[str, Any]]:
    """
    Return mapping: teamId -> metadata. Cached and refreshed daily.
    Includes: id, shortName, teamName, name, abbreviation, venue, division, conference.
    """
    cache_key = "teams_v1"
    if not refresh:
        cached = read_cache(cache_key, CACHE_TTL_TEAM_LIST_SECONDS)
        if cached:
            return {int(k): v for k, v in cached.items()}

    try:
        data = _api_get("/teams")
        teams = {}
        for t in data.get("teams", []):
            teams[int(t["id"])]: Dict[str, Any]
            teams[t["id"]] = {
                "id": t["id"],
                "name": t.get("name"),
                "teamName": t.get("teamName"),
                "shortName": t.get("shortName", t.get("teamName")),
                "abbreviation": t.get("abbreviation"),
                "venue": t.get("venue", {}),
                "division": t.get("division", {}),
                "conference": t.get("conference", {}),
            }
        write_cache(cache_key, {str(k): v for k, v in teams.items()})
        return teams
    except Exception:
        # Graceful fallback: return cached teams if present
        cached = read_cache(cache_key, 365 * 24 * 60 * 60)  # accept stale for UI
        if cached:
            return {int(k): v for k, v in cached.items()}
        # As a last resort, return empty mapping; callers should handle
        return {}


def fetch_schedule(date: dt.date) -> List[Dict[str, Any]]:
    params = {"date": date.strftime("%Y-%m-%d")}
    data = _api_get("/schedule", params=params)
    games: List[Dict[str, Any]] = []
    for date_block in data.get("dates", []):
        for g in date_block.get("games", []):
            games.append(g)
    return games


def fetch_standings() -> Dict[int, Dict[str, Any]]:
    data = _api_get("/standings")
    standings: Dict[int, Dict[str, Any]] = {}
    for rec in data.get("records", []):
        for teamrec in rec.get("teamRecords", []):
            team = teamrec.get("team", {})
            tid = int(team.get("id"))
            standings[tid] = {
                "points": teamrec.get("points"),
                "pointsPct": teamrec.get("pointsPercentage"),
                "regulationWins": teamrec.get("regulationWins"),
                "gamesPlayed": teamrec.get("gamesPlayed"),
                "ppPct": teamrec.get("ppPct"),  # may be missing
                "pkPct": teamrec.get("pkPct"),  # may be missing
            }
    return standings


def _is_ot_game(linescore: Dict[str, Any]) -> bool:
    current_period = linescore.get("currentPeriod", 0)
    if current_period and current_period > 3:
        return True
    # Historical games: check hasShootout
    if linescore.get("hasShootout"):
        return True
    # Also inspect periods length
    periods = linescore.get("periods", [])
    return len(periods) > 3


def fetch_team_last_games(team_id: int, count: int = 15) -> List[Dict[str, Any]]:
    # NHL API supports schedule with teamId and expand=... for previous games
    params = {"teamId": team_id, "expand": "schedule.linescore", "site": "en"}
    data = _api_get("/schedule", params=params)
    games: List[Dict[str, Any]] = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    # Sort by gameDate descending and take last N
    games.sort(key=lambda g: g.get("gameDate", ""), reverse=True)
    return games[:count]


def fetch_head_to_head(team_a: int, team_b: int, max_games: int) -> List[Dict[str, Any]]:
    params = {
        "teamId": f"{team_a},{team_b}",
        "expand": "schedule.linescore",
        "site": "en",
    }
    data = _api_get("/schedule", params=params)
    # Filter to games where teams match exactly (any home/away order)
    games: List[Dict[str, Any]] = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            teams = g.get("teams", {})
            home = teams.get("home", {}).get("team", {}).get("id")
            away = teams.get("away", {}).get("team", {}).get("id")
            if {home, away} == {team_a, team_b}:
                games.append(g)
    games.sort(key=lambda g: g.get("gameDate", ""), reverse=True)
    return games[:max_games]


def fetch_playoff_series_last_n_seasons(team_a: int, team_b: int, seasons: int = 5) -> bool:
    # NHL API "tournaments/playoffs" exposes brackets by season; we can do a light scan
    try:
        current_year = dt.date.today().year
        current_season_start = current_year if dt.date.today().month >= 7 else current_year - 1
        for s in range(seasons):
            season = f"{current_season_start - s}{current_season_start - s + 1}"
            data = _api_get(f"/tournaments/playoffs?season={season}")
            for round_rec in data.get("rounds", []):
                for series in round_rec.get("series", []):
                    a = series.get("matchupTeams", [])[0].get("team", {}).get("id") if series.get("matchupTeams") else None
                    b = series.get("matchupTeams", [])[1].get("team", {}).get("id") if series.get("matchupTeams") else None
                    if a is None or b is None:
                        continue
                    if {int(a), int(b)} == {team_a, team_b}:
                        return True
    except Exception:
        return False
    return False


def get_goalie_status_for_game(game_pk: int) -> Tuple[Optional[int], Optional[int], str]:
    """
    Attempt to infer starting goalies; NHL API often lacks pregame confirmation.
    Returns (home_goalie_id, away_goalie_id, status): status is "confirmed", "probable", or "unknown".
    """
    try:
        data = _api_get(f"/game/{game_pk}/linescore")
        # Pregame may not include expected starters; default to unknown
        return None, None, "unknown"
    except Exception:
        return None, None, "unknown"


def compute_days_rest(team_id: int, reference_date: dt.date) -> Optional[int]:
    try:
        games = fetch_team_last_games(team_id, count=5)
        for g in games:
            gd = g.get("gameDate")
            if not gd:
                continue
            played_on = dt.datetime.fromisoformat(gd.replace("Z", "+00:00")).date()
            if played_on < reference_date:
                return (reference_date - played_on).days - 1
    except Exception:
        return None
    return None


def game_implied_total_from_odds(odds: Optional[Dict[str, Any]]) -> Optional[float]:
    if not odds:
        return None
    # Expect odds dict to perhaps include market_total like 5.5, 6.0, etc.
    return odds.get("total")


