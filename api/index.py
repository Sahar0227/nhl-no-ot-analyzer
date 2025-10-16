import datetime as dt
from typing import Any, Dict, List

from fastapi import FastAPI, Query

from analyzer import compute_signals_for_matchup, score_matchup, should_skip
from config import MAX_TOP_GAMES
from data_fetcher import fetch_schedule, fetch_standings, fetch_teams


app = FastAPI(title="NHL No OT Analyzer API")


@app.get("/api/games")
def get_games(date: str | None = Query(default=None), max_rows: int = Query(default=MAX_TOP_GAMES), skip_flags: bool = Query(default=False)) -> Dict[str, Any]:
    target_date = dt.date.fromisoformat(date) if date else dt.date.today()
    teams_map = fetch_teams()
    standings = fetch_standings()
    schedule = fetch_schedule(target_date)

    rows: List[Dict[str, Any]] = []
    for g in schedule:
        signals = compute_signals_for_matchup(g, standings)
        if skip_flags and should_skip(signals):
            continue
        scored = score_matchup(signals)
        rows.append(scored)

    rows.sort(key=lambda r: r.get("confidence", 0), reverse=True)
    rows = rows[: int(max_rows)]

    def abbr(team_id: int) -> str:
        return teams_map.get(team_id, {}).get("abbreviation", str(team_id))

    # Lightweight response
    payload = []
    for r in rows:
        payload.append({
            "matchup": f"{abbr(r['away_id'])} @ {abbr(r['home_id'])}",
            "away_id": r["away_id"],
            "home_id": r["home_id"],
            "head2head_ot_pct": round(100 * r.get("head2head_OT_rate", 0.0)),
            "evenly_matched": r.get("evenly_matched"),
            "days_rest": [r.get("days_rest_away"), r.get("days_rest_home")],
            "goalie_status": [r.get("goalie_status_away"), r.get("goalie_status_home")],
            "confidence": r.get("confidence", 0),
            "reason": r.get("reason", ""),
            "data_confidence": r.get("data_confidence", 0),
        })

    return {"date": target_date.isoformat(), "count": len(payload), "games": payload}


