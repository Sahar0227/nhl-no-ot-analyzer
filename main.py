import datetime as dt
from typing import Any, Dict, List

from config import MAX_TOP_GAMES
from data_fetcher import fetch_schedule, fetch_standings, fetch_teams
from analyzer import compute_signals_for_matchup, score_matchup, should_skip


def format_row(teams_map: Dict[int, Dict[str, Any]], scored: Dict[str, Any]) -> List[str]:
    a = teams_map.get(scored["away_id"], {}).get("abbreviation", str(scored["away_id"]))
    h = teams_map.get(scored["home_id"], {}).get("abbreviation", str(scored["home_id"]))
    h2h_pct = f"{int(round(100*scored.get('head2head_OT_rate', 0.0)))}%"
    even_flag = "Y" if scored.get("evenly_matched") else "-"
    rest = f"{scored.get('days_rest_away','?')}/{scored.get('days_rest_home','?')}"
    gstat = f"{scored.get('goalie_status_away','?')}/{scored.get('goalie_status_home','?')}"
    conf = f"{scored.get('confidence', 0)}%"
    return [f"{a}@{h}", h2h_pct, even_flag, rest, gstat, conf, scored.get("reason", "")] 


def print_table(headers: List[str], rows: List[List[str]]) -> None:
    widths = [max(len(str(cell)) for cell in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    def fmt_row(r: List[str]) -> str:
        return " | ".join(
            str(cell).ljust(width) for cell, width in zip(r, widths)
        )
    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r))


def main() -> None:
    today = dt.date.today()
    teams_map = fetch_teams()
    standings = fetch_standings()
    schedule = fetch_schedule(today)

    results: List[Dict[str, Any]] = []
    for g in schedule:
        signals = compute_signals_for_matchup(g, standings)
        if should_skip(signals):
            continue
        scored = score_matchup(signals)
        results.append(scored)

    results.sort(key=lambda r: r.get("confidence", 0), reverse=True)
    top = results[:MAX_TOP_GAMES]

    headers = ["Matchup", "Head2Head_OT%", "EvenMatch", "DaysRest(A/B)", "GoalieStatus(A/B)", "Confidence", "Reason"]
    rows = [format_row(teams_map, r) for r in top]
    print_table(headers, rows)


if __name__ == "__main__":
    main()


