import datetime as dt
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    from analyzer import compute_signals_for_matchup, score_matchup, should_skip
    from config import MAX_TOP_GAMES
    from data_fetcher import fetch_schedule, fetch_standings, fetch_teams
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()


st.set_page_config(page_title="NHL No OT Analyzer", layout="wide")
st.title("NHL No Overtime (Regulation Win) Analyzer")

col1, col2, col3 = st.columns(3)
with col1:
    target_date = st.date_input("Date", value=dt.date.today())
with col2:
    max_rows = st.number_input("Max games shown", min_value=1, max_value=50, value=MAX_TOP_GAMES)
with col3:
    skip_flags = st.checkbox("Skip rivalry/evenly-matched games (view picks only)", value=False)

error_box = st.empty()
retry_button = st.empty()

# Check if this is a retry
if 'retry_count' not in st.session_state:
    st.session_state.retry_count = 0

def fetch_data():
    try:
        teams_map = fetch_teams()
        standings = fetch_standings()
        schedule = fetch_schedule(target_date)
        return teams_map, standings, schedule, None
    except Exception as e:
        return None, None, None, str(e)

with st.spinner("Fetching live NHL data..."):
    teams_map, standings, schedule, error = fetch_data()

if error:
    error_box.error(f"⚠️ **NHL API temporarily unavailable** (attempt {st.session_state.retry_count + 1})\n\nError: {error}\n\nThis is usually a temporary DNS issue. Click retry below.")
    
    if retry_button.button("🔄 Retry Now", type="primary"):
        st.session_state.retry_count += 1
        st.rerun()
    
    st.info("💡 **Tip**: NHL API issues are usually resolved within 1-2 minutes. Keep trying!")
    st.stop()

rows: List[Dict[str, Any]] = []
for g in schedule:
    signals = compute_signals_for_matchup(g, standings)
    if skip_flags and should_skip(signals):
        continue
    scored = score_matchup(signals)
    rows.append(scored)

if not rows:
    st.info("No games found or all filtered out by current settings.")
else:
    # Map to display rows
    def team_abbr(tid: int) -> str:
        return teams_map.get(tid, {}).get("abbreviation", str(tid))

    display = []
    for r in rows:
        display.append({
            "Matchup": f"{team_abbr(r['away_id'])} @ {team_abbr(r['home_id'])}",
            "Head2Head_OT%": f"{int(round(100*r.get('head2head_OT_rate',0))) }%",
            "EvenMatch": r.get("evenly_matched"),
            "DaysRest(A/B)": f"{r.get('days_rest_away','?')}/{r.get('days_rest_home','?')}",
            "GoalieStatus(A/B)": f"{r.get('goalie_status_away','?')}/{r.get('goalie_status_home','?')}",
            "Confidence": r.get("confidence", 0),
            "Reason": r.get("reason", ""),
            "DataConfidence": r.get("data_confidence", 0),
        })

    df = pd.DataFrame(display)
    df = df.sort_values("Confidence", ascending=False).head(int(max_rows))
    st.dataframe(df, use_container_width=True)


