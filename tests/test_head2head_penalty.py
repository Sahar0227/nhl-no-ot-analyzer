import datetime as dt

from analyzer import score_matchup


def make_signals(h2h_rate: float) -> dict:
    return {
        "away_id": 1,
        "home_id": 2,
        "head2head_OT_rate": h2h_rate,
        "head2head_avg_goal_margin": 1.0,
        "playoff_rivalry_flag": False,
        "standings_gap": 2,
        "regulation_win_pct_diff": 0.02,
        "xg_share_diff": 0.03,
        "evenly_matched": False,
        "team_OT_rate_last_15_away": 0.10,
        "team_OT_rate_last_15_home": 0.10,
        "days_rest_away": 1,
        "days_rest_home": 1,
        "back_to_back_away": False,
        "back_to_back_home": False,
        "goalie_status_away": "unknown",
        "goalie_status_home": "unknown",
        "implied_total": 6.0,
        "data_confidence": 100,
        "reason": "",
    }


def test_head2head_penalty_applies():
    s_low = score_matchup(make_signals(0.10))
    s_high = score_matchup(make_signals(0.30))
    assert s_high["confidence"] <= s_low["confidence"], "Higher H2H OT rate should not increase confidence"


