import datetime as dt
from typing import Any, Dict, List, Optional

from config import (
    WEIGHTS,
    H2H_LOOKBACK_GAMES_PRIMARY,
    H2H_LOOKBACK_GAMES_FALLBACK,
    H2H_OT_RATE_PENALTY_THRESHOLD,
    PLAYOFF_RIVALRY_LOOKBACK_SEASONS,
    EVENLY_MATCHED_STANDINGS_GAP_MAX_POINTS,
    EVENLY_MATCHED_REG_WIN_PCT_DIFF_MAX,
    EVENLY_MATCHED_XG_SHARE_DIFF_MAX,
    TEAM_OT_RATE_LOOKBACK_GAMES,
    TEAM_OT_RATE_BOTH_HIGH_THRESHOLD,
    LOW_TOTAL_THRESHOLD,
    SCORE_MIN,
    SCORE_MAX,
    SKIP_IF_RIVALRY_OR_EVEN,
)
from data_fetcher import (
    fetch_head_to_head,
    fetch_playoff_series_last_n_seasons,
    fetch_team_last_games,
    compute_days_rest,
    game_implied_total_from_odds,
)


def _pct(n: int, d: int) -> float:
    return (n / d) if d else 0.0


def _compute_ot_rate_from_games(games: List[Dict[str, Any]]) -> float:
    ot_count = 0
    total = 0
    for g in games:
        ls = g.get("linescore", {})
        periods = ls.get("periods", [])
        if len(periods) > 3 or ls.get("hasShootout"):
            ot_count += 1
        total += 1
    return _pct(ot_count, total)


def _avg_goal_margin(games: List[Dict[str, Any]]) -> float:
    margins: List[int] = []
    for g in games:
        teams = g.get("teams", {})
        away = teams.get("away", {}).get("score")
        home = teams.get("home", {}).get("score")
        if away is None or home is None:
            continue
        margins.append(abs(int(away) - int(home)))
    if not margins:
        return 0.0
    return sum(margins) / len(margins)


def _regulation_win_pct(standings_entry: Optional[Dict[str, Any]]) -> float:
    if not standings_entry:
        return 0.0
    rw = standings_entry.get("regulationWins") or 0
    gp = standings_entry.get("gamesPlayed") or 0
    return _pct(rw, gp)


def compute_signals_for_matchup(
    game: Dict[str, Any],
    standings: Dict[int, Dict[str, Any]],
    odds: Optional[Dict[str, Any]] = None,
    xg_share_last10: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """
    Compute matchup signals from NHL data. Returns a dictionary with fields used by scoring and UI.
    xg_share_last10: optional MoneyPuck xG share per team id (0-1). If missing, data_confidence reduced.
    """
    teams_block = game.get("teams", {})
    home = teams_block.get("home", {}).get("team", {}).get("id")
    away = teams_block.get("away", {}).get("team", {}).get("id")
    game_pk = game.get("gamePk")
    game_date_str = game.get("gameDate")
    game_date = dt.datetime.fromisoformat(game_date_str.replace("Z", "+00:00")).date() if game_date_str else dt.date.today()

    # Head to head games
    h2h = fetch_head_to_head(away, home, H2H_LOOKBACK_GAMES_PRIMARY)
    if len(h2h) < H2H_LOOKBACK_GAMES_FALLBACK:
        h2h = fetch_head_to_head(away, home, H2H_LOOKBACK_GAMES_FALLBACK)
    head2head_ot_rate = _compute_ot_rate_from_games(h2h)
    head2head_avg_goal_margin = _avg_goal_margin(h2h)
    playoff_rivalry_flag = fetch_playoff_series_last_n_seasons(away, home, PLAYOFF_RIVALRY_LOOKBACK_SEASONS)

    # Evenly matched signals
    s_away = standings.get(int(away))
    s_home = standings.get(int(home))
    standings_gap = abs((s_home or {}).get("points", 0) - (s_away or {}).get("points", 0))
    reg_win_pct_diff = abs(_regulation_win_pct(s_home) - _regulation_win_pct(s_away))
    # Special teams mismatch (percentage points difference between home PP and away PK and vice versa)
    pp_home = (s_home or {}).get("ppPct")
    pk_away = (s_away or {}).get("pkPct")
    pp_away = (s_away or {}).get("ppPct")
    pk_home = (s_home or {}).get("pkPct")
    special_teams_mismatch = None
    try:
        candidates = []
        if pp_home is not None and pk_away is not None:
            candidates.append(abs(float(pp_home) - float(pk_away)) / 100.0)
        if pp_away is not None and pk_home is not None:
            candidates.append(abs(float(pp_away) - float(pk_home)) / 100.0)
        if candidates:
            special_teams_mismatch = max(candidates)
    except Exception:
        special_teams_mismatch = None
    xg_share_diff = None
    if xg_share_last10 and int(away) in xg_share_last10 and int(home) in xg_share_last10:
        xg_share_diff = abs((xg_share_last10[int(home)] or 0) - (xg_share_last10[int(away)] or 0))

    evenly_matched = False
    if xg_share_diff is not None:
        evenly_matched = (
            standings_gap < EVENLY_MATCHED_STANDINGS_GAP_MAX_POINTS
            and reg_win_pct_diff < EVENLY_MATCHED_REG_WIN_PCT_DIFF_MAX
            and xg_share_diff < EVENLY_MATCHED_XG_SHARE_DIFF_MAX
        )
    else:
        # Fallback without xG
        evenly_matched = (
            standings_gap < EVENLY_MATCHED_STANDINGS_GAP_MAX_POINTS
            and reg_win_pct_diff < EVENLY_MATCHED_REG_WIN_PCT_DIFF_MAX
        )

    # Recent OT form
    last_away = fetch_team_last_games(away, TEAM_OT_RATE_LOOKBACK_GAMES)
    last_home = fetch_team_last_games(home, TEAM_OT_RATE_LOOKBACK_GAMES)
    team_ot_rate_away = _compute_ot_rate_from_games(last_away)
    team_ot_rate_home = _compute_ot_rate_from_games(last_home)

    # Rest and back-to-back
    days_rest_away = compute_days_rest(away, game_date)
    days_rest_home = compute_days_rest(home, game_date)
    back_to_back_away = (days_rest_away == 0) if days_rest_away is not None else False
    back_to_back_home = (days_rest_home == 0) if days_rest_home is not None else False

    # Goalie status (placeholder: API often lacks confirmations)
    # Keep unknown for now; analyzer will score accordingly
    goalie_status_home = "unknown"
    goalie_status_away = "unknown"

    # Totals
    implied_total = game_implied_total_from_odds(odds)

    # Data confidence 0-100 based on available signals
    available = 0
    total = 8  # rough count of major signals
    for flag in [h2h is not None, True, s_home is not None, s_away is not None, last_home is not None, last_away is not None, implied_total is not None, xg_share_diff is not None]:
        if flag:
            available += 1
    data_confidence = int(round(100 * _pct(available, total)))

    reason_bits: List[str] = []
    if head2head_ot_rate > H2H_OT_RATE_PENALTY_THRESHOLD:
        reason_bits.append(f"Head-to-head OT {int(round(100*head2head_ot_rate))}% last {len(h2h)}")
    if playoff_rivalry_flag:
        reason_bits.append("Recent playoffs met")
    if evenly_matched:
        reason_bits.append("Evenly matched by standings/reg wins/xG")

    return {
        "away_id": int(away),
        "home_id": int(home),
        "head2head_OT_rate": head2head_ot_rate,
        "head2head_avg_goal_margin": head2head_avg_goal_margin,
        "playoff_rivalry_flag": playoff_rivalry_flag,
        "standings_gap": standings_gap,
        "regulation_win_pct_diff": reg_win_pct_diff,
        "xg_share_diff": xg_share_diff,
        "special_teams_mismatch": special_teams_mismatch,
        "evenly_matched": evenly_matched,
        "team_OT_rate_last_15_away": team_ot_rate_away,
        "team_OT_rate_last_15_home": team_ot_rate_home,
        "days_rest_away": days_rest_away,
        "days_rest_home": days_rest_home,
        "back_to_back_away": back_to_back_away,
        "back_to_back_home": back_to_back_home,
        "goalie_status_away": goalie_status_away,
        "goalie_status_home": goalie_status_home,
        "implied_total": implied_total,
        "data_confidence": data_confidence,
        "reason": "; ".join(reason_bits),
    }


def score_matchup(signals: Dict[str, Any]) -> Dict[str, Any]:
    # Base components (fallback-only here; real GF/GA inputs could be added later)
    gf_diff = 0.0
    ga_diff = 0.0
    reg_win_diff = signals.get("regulation_win_pct_diff", 0.0)
    avg_team_ot_inv = 1.0 - ((signals.get("team_OT_rate_last_15_away", 0.0) + signals.get("team_OT_rate_last_15_home", 0.0)) / 2.0)

    score = 0.0
    score += WEIGHTS["gf_diff"] * gf_diff
    score += WEIGHTS["ga_diff"] * ga_diff
    score += WEIGHTS["reg_win_diff"] * (1.0 - reg_win_diff)  # smaller diff is better
    score += WEIGHTS["avg_team_ot_inv"] * avg_team_ot_inv

    # Penalties
    if signals.get("head2head_OT_rate", 0.0) > H2H_OT_RATE_PENALTY_THRESHOLD:
        score += WEIGHTS["head2head_penalty"]
    if signals.get("evenly_matched"):
        score += WEIGHTS["evenly_matched_penalty"]
    if signals.get("back_to_back_away") or signals.get("back_to_back_home"):
        score += WEIGHTS["back_to_back_penalty"]
    if (signals.get("implied_total") is not None) and (signals.get("implied_total") <= LOW_TOTAL_THRESHOLD):
        score += WEIGHTS["low_total_penalty"]
    # Special teams mismatch: more mismatch -> fewer stale even-strength minutes -> slightly lower OT risk
    if signals.get("special_teams_mismatch") is not None:
        score += WEIGHTS["special_teams_mismatch"] * float(signals.get("special_teams_mismatch"))

    # Both teams recent OT form high -> multiplier
    if (
        signals.get("team_OT_rate_last_15_away", 0.0) > TEAM_OT_RATE_BOTH_HIGH_THRESHOLD
        and signals.get("team_OT_rate_last_15_home", 0.0) > TEAM_OT_RATE_BOTH_HIGH_THRESHOLD
    ):
        score *= WEIGHTS["both_teams_high_ot_multiplier"]

    # Clip and convert to confidence 0-100 (simple normalization)
    clipped = max(SCORE_MIN, min(SCORE_MAX, score))
    confidence = int(round(100 * (clipped - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)))

    return {**signals, "score": score, "confidence": confidence}


def should_skip(signals: Dict[str, Any]) -> bool:
    if not SKIP_IF_RIVALRY_OR_EVEN:
        return False
    return bool(signals.get("evenly_matched") or signals.get("playoff_rivalry_flag") or (signals.get("head2head_OT_rate", 0.0) > H2H_OT_RATE_PENALTY_THRESHOLD))


