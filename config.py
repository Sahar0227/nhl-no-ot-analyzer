"""
Centralized configuration for NHL No Overtime (Regulation Win) analyzer.

Adjust thresholds and weights here; the analyzer and fetchers will import
these values at runtime. All numeric values are floats unless otherwise noted.
"""

# --- API and cache settings ---
NHL_API_BASE = "https://statsapi.web.nhl.com/api/v1"

# Directory where lightweight JSON caches live (created automatically)
CACHE_DIR = ".cache"

# Refresh periods (seconds)
CACHE_TTL_TEAM_LIST_SECONDS = 24 * 60 * 60  # refresh daily
CACHE_TTL_XG_SECONDS = 6 * 60 * 60  # MoneyPuck xG refresh window

# --- Head-to-head / rivalry settings ---
H2H_LOOKBACK_GAMES_PRIMARY = 20
H2H_LOOKBACK_GAMES_FALLBACK = 10
H2H_OT_RATE_PENALTY_THRESHOLD = 0.20  # If > 20%, apply penalty
PLAYOFF_RIVALRY_LOOKBACK_SEASONS = 5

# --- Evenly matched (parity) thresholds ---
EVENLY_MATCHED_STANDINGS_GAP_MAX_POINTS = 6
EVENLY_MATCHED_REG_WIN_PCT_DIFF_MAX = 0.05
EVENLY_MATCHED_XG_SHARE_DIFF_MAX = 0.06

# --- Recent OT form ---
TEAM_OT_RATE_LOOKBACK_GAMES = 15
TEAM_OT_RATE_BOTH_HIGH_THRESHOLD = 0.15

# --- Rest / travel ---
LONG_TRAVEL_DISTANCE_KM = 3000  # Cross-continent-ish heuristic
BACK_TO_BACK_PENALTY_ENABLED = True

# --- Goalie ---
REQUIRE_CONFIRMED_GOALIE = False  # Set True to enforce harsh penalty if unknown
GOALIE_RECENT_CHANGE_HOURS = 12

# --- Special teams & totals ---
LOW_TOTAL_THRESHOLD = 5.5

# --- Scoring Weights ---
# Positive values increase confidence; negative decrease.
WEIGHTS = {
    # Original score components
    "gf_diff": 1.0,            # goals for per game difference
    "ga_diff": 0.8,            # goals against per game difference (lower is better)
    "reg_win_diff": 1.3,       # regulation win % difference
    "avg_team_ot_inv": 0.7,    # inverse of average OT rates for teams
    "goalie_boost": 0.8,       # applies based on starter/backup/confirmation

    # New penalties / boosts
    "head2head_penalty": -0.8,     # applied when H2H OT rate above threshold
    "evenly_matched_penalty": -1.2,
    "back_to_back_penalty": -0.6,
    "low_total_penalty": -0.5,
    "special_teams_mismatch": 0.4, # bigger PP vs opp PK mismatch slightly reduces OT risk

    # Misc scaling / multipliers
    "both_teams_high_ot_multiplier": 0.85,  # multiply final score if both OT form high
}

# Final score clipping and normalization
SCORE_MIN = -5.0
SCORE_MAX = 5.0

# Exclusion behavior
SKIP_IF_RIVALRY_OR_EVEN = False

# Output formatting
MAX_TOP_GAMES = 10



