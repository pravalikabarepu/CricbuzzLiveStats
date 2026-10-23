import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
from sqlalchemy import text

from db_connection import get_engine as get_database_engine
from save_matches import save_matches


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Cricbuzz LiveStats",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# 2. THEME
# =========================================================

BG = "#101713"
PANEL = "#19251D"
PANEL_ALT = "#1D2C22"
GREEN = "#39B85B"
LIGHT_GREEN = "#75DB91"
TEXT = "#E8F0EB"
MUTED = "#B6CBBD"
BORDER = "#31533A"

st.markdown(
    f"""
    <style>
   /* Table background */
    [data-testid="stDataFrame"] {{
        background-color: #102820;
        border: 1px solid #2E6B50;
        border-radius: 10px;
        overflow: hidden;
    }}

    /* Table header */
    [data-testid="stDataFrame"] [role="columnheader"] {{
        background-color: #1B4332 !important;
        color: #FFFFFF !important;
        font-weight: bold !important;
    }}

    /* Table text and cells */
    [data-testid="stDataFrame"] [role="gridcell"] {{
        background-color: #102820 !important;
        color: #FFFFFF !important;
        border-color: #2E6B50 !important;
    }}
 

/* Table hover effect */
[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {{
    background-color: #245640 !important;
}}
    .stApp {{
        background: linear-gradient(
            145deg, {BG}, #151D18, #101512
        );
        color: {TEXT};
    }}

    [data-testid="stSidebar"] {{
        background: #111A14;
        border-right: 1px solid {BORDER};
    }}

    .stApp h1, .stApp h2, .stApp h3 {{
        color: {LIGHT_GREEN} !important;
    }}

    .hero {{
        background: linear-gradient(135deg, {PANEL}, {BG});
        border: 1px solid {BORDER};
        border-left: 5px solid {GREEN};
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 24px;
    }}

    .hero h1 {{
        color: {LIGHT_GREEN} !important;
        font-size: 36px;
        margin-bottom: 8px;
    }}

    .hero p {{
        color: {MUTED};
        margin-bottom: 0;
    }}

    [data-testid="stMetric"] {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 14px;
    }}

    [data-testid="stMetricLabel"] {{
        color: {MUTED} !important;
    }}

    [data-testid="stMetricValue"] {{
        color: {LIGHT_GREEN} !important;
    }}

    .stButton > button,
    .stDownloadButton > button {{
        background: #267A3D;
        color: white !important;
        border: 1px solid {GREEN};
        border-radius: 8px;
        font-weight: 600;
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        background: {GREEN};
        color: {BG} !important;
    }}

    /* White filters with readable black text */
    input, textarea {{
        color: #000000 !important;
        caret-color: #000000 !important;
    }}

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div {{
        background: #FFFFFF !important;
        border-color: #B8C4BC !important;
    }}

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {{
        color: #000000 !important;
    }}

    div[data-baseweb="popover"],
    div[data-baseweb="popover"] *,
    ul[role="listbox"],
    ul[role="listbox"] * {{
        color: #000000 !important;
        background-color: #FFFFFF !important;
    }}

    [data-testid="stTable"] {{
        background: {PANEL} !important;
    }}

    [data-testid="stExpander"] {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    .footer {{
        color: {MUTED};
        text-align: center;
        padding: 20px;
        border-top: 1px solid {BORDER};
        margin-top: 30px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 3. DATABASE CONNECTION
# =========================================================

@st.cache_resource
def get_engine():
    return get_database_engine()


TABLE_NAMES = [
    "matches",
    "teams",
    "series",
    "venues",
    "innings_scores",
    "players",
    "batting_performance",
    "bowling_performance",
    "partnerships",
]


@st.cache_data(ttl=60, show_spinner=False)
def load_table(table_name):
    if table_name not in TABLE_NAMES:
        raise ValueError("Invalid table name")

    with get_engine().connect() as connection:
        return pd.read_sql(
            text(f"SELECT * FROM `{table_name}`"),
            connection,
        )


def refresh_data():
    load_table.clear()


def get_column(df, possible_names):
    lookup = {str(c).lower(): c for c in df.columns}

    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def show_dataframe(df):
    if df is None or df.empty:
        st.info("No records available.")
        return

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def csv_download(df, filename, label):
    if df is None or df.empty:
        st.info("No data available to download.")
        return

    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=f"download_{filename}",
    )


# =========================================================
# 4. CHART HELPER
# =========================================================

def green_bar_chart(df, x, y, title, height=450):
    if df is None or df.empty:
        st.info("No chart data available.")
        return

    if x not in df.columns or y not in df.columns:
        st.info("The required chart columns are unavailable.")
        return

    chart_df = df.copy()
    chart_df[y] = numeric(chart_df[y])
    chart_df = chart_df.dropna(subset=[y])

    if chart_df.empty:
        st.info("No numeric values are available.")
        return

    fig = px.bar(
        chart_df,
        x=x,
        y=y,
        title=title,
        color_discrete_sequence=[GREEN],
    )

    fig.update_layout(
        height=height,
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        font_color=TEXT,
        title_font_color=LIGHT_GREEN,
        xaxis=dict(
            title=None,
            tickangle=-30 if len(chart_df) > 5 else 0,
            gridcolor=BORDER,
        ),
        yaxis=dict(
            title=y,
            gridcolor=BORDER,
        ),
        showlegend=False,
    )

    fig.update_traces(
        marker_line_color=LIGHT_GREEN,
        marker_line_width=0.5,
        hovertemplate="%{x}<br>" + y + ": %{y}<extra></extra>",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# =========================================================
# 5. EXCEL EXPORT HELPER
# =========================================================

def make_excel_report(tables):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(
                writer,
                sheet_name=name[:31],
                index=False,
            )

    output.seek(0)
    return output.getvalue()


# =========================================================
# 6. LOAD DATABASE TABLES
# =========================================================

table_data = {}
table_errors = {}

with st.spinner("Loading cricket data from MySQL..."):
    for table_name in TABLE_NAMES:
        try:
            table_data[table_name] = load_table(table_name)
        except Exception as error:
            table_data[table_name] = pd.DataFrame()
            table_errors[table_name] = str(error)


matches = table_data["matches"]
teams = table_data["teams"]
series = table_data["series"]
venues = table_data["venues"]
innings = table_data["innings_scores"]
players = table_data["players"]
batting = table_data["batting_performance"]
bowling = table_data["bowling_performance"]
partnerships = table_data["partnerships"]

# Temporary cloud database diagnostic
try:
    with get_engine().connect() as connection:
        database_name = connection.exec_driver_sql(
            "SELECT DATABASE()"
        ).scalar()

        match_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM matches"
        ).scalar()

    st.success("Database connection successful!")
    st.write("Connected database:", database_name)
    st.write("Matches found in database:", match_count)

except Exception as error:
    st.error("Database connection failed!")
    st.code(f"{type(error).__name__}: {error}")


# =========================================================
# 7. SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## 🏏 Cricbuzz LiveStats")
    st.caption("Cricket Analytics Dashboard")
    st.divider()

    if st.button("🔄 Update Live Cricket Data", use_container_width=True):
        try:
            with st.spinner("Updating cricket data..."):
                save_matches()

            refresh_data()
            st.success("Cricket data updated successfully.")
            st.rerun()

        except Exception as error:
            st.error("Unable to update cricket data.")
            st.caption(str(error))

    st.divider()
    st.subheader("Database Status")

    for table_name in TABLE_NAMES:
        st.write(
            f"**{table_name}:** "
            f"{len(table_data[table_name]):,} rows"
        )


# =========================================================
# 8. MAIN HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">
        <h1>🏏 Cricbuzz LiveStats</h1>
        <p>
            Real-Time Cricket Insights · SQL-Based Analytics ·
            Player Performance
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 9. DATABASE OVERVIEW
# =========================================================

st.subheader("📊 Database Overview")

overview = [
    ("Total Matches", len(matches)),
    ("Teams", len(teams)),
    ("Players", len(players)),
    ("Innings Records", len(innings)),
    ("Batting Records", len(batting)),
    ("Bowling Records", len(bowling)),
    ("Venues", len(venues)),
    ("Partnerships", len(partnerships)),
]

for start in range(0, len(overview), 4):
    cols = st.columns(4)

    for col, (label, value) in zip(
        cols, overview[start:start + 4]
    ):
        with col:
            st.metric(label, f"{value:,}")


if table_errors:
    with st.expander("⚠️ Database loading errors"):
        for name, error in table_errors.items():
            st.warning(f"{name}: {error}")


# =========================================================
# 10. MATCH DETAILS
# =========================================================

st.divider()
st.subheader("🏏 Match Details")

filtered_matches = matches.copy()

if not matches.empty:
    format_col = get_column(
        matches, ["match_format", "format", "match_type"]
    )
    status_col = get_column(
        matches, ["status", "match_status", "state"]
    )

    team1_col = get_column(
        matches, ["team1_name", "team1", "team1name", "home_team"]
    )
    team2_col = get_column(
        matches, ["team2_name", "team2", "team2name", "away_team"]
    )

    filters = st.columns(3)

    if format_col:
        formats = sorted(
            matches[format_col].dropna().astype(str).unique()
        )

        with filters[0]:
            selected_format = st.selectbox(
                "Match Format",
                ["All Formats"] + formats,
            )

        if selected_format != "All Formats":
            filtered_matches = filtered_matches[
                filtered_matches[format_col].astype(str)
                == selected_format
            ]

    if status_col:
        statuses = sorted(
            matches[status_col].dropna().astype(str).unique()
        )

        with filters[1]:
            selected_status = st.selectbox(
                "Match Status",
                ["All Statuses"] + statuses,
            )

        if selected_status != "All Statuses":
            filtered_matches = filtered_matches[
                filtered_matches[status_col].astype(str)
                == selected_status
            ]

    if team1_col or team2_col:
        available_teams = set()

        for col_name in [team1_col, team2_col]:
            if col_name:
                available_teams.update(
                    matches[col_name].dropna().astype(str)
                )

        with filters[2]:
            selected_team = st.selectbox(
                "Team",
                ["All Teams"] + sorted(available_teams),
            )

        if selected_team != "All Teams":
            mask = pd.Series(
                False, index=filtered_matches.index
            )

            if team1_col:
                mask |= (
                    filtered_matches[team1_col].astype(str)
                    == selected_team
                )

            if team2_col:
                mask |= (
                    filtered_matches[team2_col].astype(str)
                    == selected_team
                )

            filtered_matches = filtered_matches[mask]

    st.caption(f"Showing {len(filtered_matches):,} matches")
    show_dataframe(filtered_matches)

    csv_download(
        filtered_matches,
        "cricbuzz_match_details.csv",
        "⬇️ Download Match Details",
    )
else:
    st.info("No match records are available.")


# =========================================================
# 11. INNINGS SCORES
# =========================================================

st.divider()
st.subheader("📈 Innings Scores")

filtered_innings = innings.copy()

if not innings.empty:
    innings_col = get_column(
        innings,
        ["innings_number", "innings_no", "inningsid", "innings"],
    )
    runs_col = get_column(
        innings, ["runs", "total_runs", "score", "runs_scored"]
    )
    match_col = get_column(innings, ["match_id", "matchid"])

    if innings_col:
        innings_options = sorted(
            innings[innings_col].dropna().astype(str).unique()
        )

        selected_innings = st.selectbox(
            "Filter by Innings",
            ["All Innings"] + innings_options,
        )

        if selected_innings != "All Innings":
            filtered_innings = filtered_innings[
                filtered_innings[innings_col].astype(str)
                == selected_innings
            ]

    if runs_col:
        chart_df = filtered_innings.copy()
        chart_df[runs_col] = numeric(chart_df[runs_col])

        if innings_col and match_col:
            chart_df["Chart Label"] = (
                "M"
                + chart_df[match_col].astype(str)
                + " · I"
                + chart_df[innings_col].astype(str)
            )
        elif innings_col:
            chart_df["Chart Label"] = (
                "Innings " + chart_df[innings_col].astype(str)
            )
        else:
            chart_df["Chart Label"] = [
                f"Innings {i + 1}" for i in range(len(chart_df))
            ]

        green_bar_chart(
            chart_df,
            "Chart Label",
            runs_col,
            "Runs by Innings",
            height=500,
        )

    show_dataframe(filtered_innings)

    csv_download(
        filtered_innings,
        "cricbuzz_innings_scores.csv",
        "⬇️ Download Innings Scores",
    )
else:
    st.info("No innings score data is available.")


# =========================================================
# 12. BATTING PERFORMANCE
# =========================================================

st.divider()
st.subheader("🏏 Batting Performance")

if not batting.empty:
    player_col = get_column(
        batting, ["player_name", "batsman_name", "name", "player"]
    )
    runs_col = get_column(
        batting, ["runs", "runs_scored", "batsman_runs", "total_runs"]
    )
    balls_col = get_column(
        batting, ["balls", "balls_faced", "ballsfaced"]
    )
    fours_col = get_column(batting, ["fours", "four", "fours_count"])
    sixes_col = get_column(batting, ["sixes", "six", "sixes_count"])

    filtered_batting = batting.copy()

    if player_col:
        players_list = sorted(
            batting[player_col].dropna().astype(str).unique()
        )

        selected_player = st.selectbox(
            "Filter Batting by Player",
            ["All Players"] + players_list,
        )

        if selected_player != "All Players":
            filtered_batting = filtered_batting[
                filtered_batting[player_col].astype(str)
                == selected_player
            ]

    if runs_col:
        filtered_batting[runs_col] = numeric(
            filtered_batting[runs_col]
        )

        if player_col:
            top_batsmen = (
                filtered_batting.dropna(subset=[runs_col])
                .groupby(player_col, as_index=False)[runs_col]
                .sum()
                .sort_values(runs_col, ascending=False)
                .head(10)
            )

            green_bar_chart(
                top_batsmen,
                player_col,
                runs_col,
                "Top 10 Run Scorers",
            )

        metric_cols = st.columns(4)

        with metric_cols[0]:
            st.metric(
                "Runs",
                f"{filtered_batting[runs_col].sum():,.0f}",
            )

        if balls_col:
            with metric_cols[1]:
                st.metric(
                    "Balls Faced",
                    f"{numeric(filtered_batting[balls_col]).sum():,.0f}",
                )

        if fours_col:
            with metric_cols[2]:
                st.metric(
                    "Fours",
                    f"{numeric(filtered_batting[fours_col]).sum():,.0f}",
                )

        if sixes_col:
            with metric_cols[3]:
                st.metric(
                    "Sixes",
                    f"{numeric(filtered_batting[sixes_col]).sum():,.0f}",
                )

    show_dataframe(filtered_batting)

    csv_download(
        filtered_batting,
        "cricbuzz_batting_performance.csv",
        "⬇️ Download Batting Data",
    )
else:
    st.info("No batting performance data is available.")


# =========================================================
# 13. BOWLING PERFORMANCE
# =========================================================

st.divider()
st.subheader("🎯 Bowling Performance")

if not bowling.empty:
    bowler_col = get_column(
        bowling, ["player_name", "bowler_name", "name", "player"]
    )
    wickets_col = get_column(
        bowling, ["wickets", "wickets_taken", "total_wickets"]
    )
    conceded_col = get_column(
        bowling, ["runs_conceded", "runs", "conceded"]
    )

    filtered_bowling = bowling.copy()

    if bowler_col:
        bowler_options = sorted(
            bowling[bowler_col].dropna().astype(str).unique()
        )

        selected_bowler = st.selectbox(
            "Filter Bowling by Player",
            ["All Players"] + bowler_options,
        )

        if selected_bowler != "All Players":
            filtered_bowling = filtered_bowling[
                filtered_bowling[bowler_col].astype(str)
                == selected_bowler
            ]

    if wickets_col and bowler_col:
        bowling_chart = filtered_bowling.copy()
        bowling_chart[wickets_col] = numeric(
            bowling_chart[wickets_col]
        )

        top_bowlers = (
            bowling_chart.dropna(subset=[wickets_col])
            .groupby(bowler_col, as_index=False)[wickets_col]
            .sum()
            .sort_values(wickets_col, ascending=False)
            .head(10)
        )

        green_bar_chart(
            top_bowlers,
            bowler_col,
            wickets_col,
            "Top 10 Wicket Takers",
        )

    if wickets_col:
        st.metric(
            "Total Wickets",
            f"{numeric(filtered_bowling[wickets_col]).sum():,.0f}",
        )

    if conceded_col:
        st.metric(
            "Runs Conceded",
            f"{numeric(filtered_bowling[conceded_col]).sum():,.0f}",
        )

    show_dataframe(filtered_bowling)

    csv_download(
        filtered_bowling,
        "cricbuzz_bowling_performance.csv",
        "⬇️ Download Bowling Data",
    )
else:
    st.info("No bowling performance data is available.")


# =========================================================
# 14. TEAM RUN ANALYTICS
# =========================================================

st.divider()
st.subheader("📊 Team Run Analytics")

if not innings.empty:
    team_id_col = get_column(innings, ["team_id", "batteamid"])
    runs_col = get_column(innings, ["runs", "total_runs", "score"])
    wickets_col = get_column(innings, ["wickets", "total_wickets"])

    if team_id_col and runs_col:
        team_runs = innings.copy()
        team_runs[runs_col] = numeric(team_runs[runs_col])

        if wickets_col:
            team_runs[wickets_col] = numeric(
                team_runs[wickets_col]
            )

        if not teams.empty:
            teams_id_col = get_column(teams, ["team_id", "id"])
            team_name_col = get_column(
                teams, ["team_name", "name"]
            )

            if teams_id_col and team_name_col:
                team_lookup = teams[
                    [teams_id_col, team_name_col]
                ].drop_duplicates()

                team_runs = team_runs.merge(
                    team_lookup,
                    left_on=team_id_col,
                    right_on=teams_id_col,
                    how="left",
                )

                label_col = team_name_col
            else:
                label_col = team_id_col
        else:
            label_col = team_id_col

        aggregations = {runs_col: "sum"}

        if wickets_col:
            aggregations[wickets_col] = "sum"

        summary = (
            team_runs.groupby(label_col, as_index=False)
            .agg(aggregations)
            .sort_values(runs_col, ascending=False)
        )

        green_bar_chart(
            summary,
            label_col,
            runs_col,
            "Total Runs by Team",
        )

        show_dataframe(summary)
        csv_download(
            summary,
            "cricbuzz_team_run_analytics.csv",
            "⬇️ Download Team Analytics",
        )
    else:
        st.info("Team ID or runs columns are unavailable.")
else:
    st.info("No innings data is available for team analytics.")


# =========================================================
# 15. PLAYER DIRECTORY
# =========================================================

st.divider()
st.subheader("👥 Player Directory")

if not players.empty:
    player_name_col = get_column(
        players, ["player_name", "name", "fullname"]
    )

    displayed_players = players.copy()

    if player_name_col:
        search_text = st.text_input(
            "Search Players",
            placeholder="Enter a player name...",
        )

        if search_text.strip():
            displayed_players = displayed_players[
                displayed_players[player_name_col]
                .astype(str)
                .str.contains(
                    search_text.strip(),
                    case=False,
                    na=False,
                )
            ]

    show_dataframe(displayed_players)

    csv_download(
        displayed_players,
        "cricbuzz_players.csv",
        "⬇️ Download Player Directory",
    )
else:
    st.info("No player records are available.")


# =========================================================
# 16. ADDITIONAL DATABASE TABLES
# =========================================================

st.divider()
st.subheader("🗄️ Additional Database Tables")

for title, df in [
    ("Teams", teams),
    ("Series", series),
    ("Venues", venues),
    ("Partnerships", partnerships),
]:
    with st.expander(title):
        show_dataframe(df)


# =========================================================
# 17. DATA QUALITY CHECK
# =========================================================

st.divider()
st.subheader("🔍 Data Quality Check")

quality_rows = []

for name in TABLE_NAMES:
    df = table_data[name]

    quality_rows.append({
        "Table Name": name,
        "Total Rows": len(df),
        "Total Columns": len(df.columns),
        "Missing Cells": (
            int(df.isna().sum().sum()) if not df.empty else 0
        ),
        "Status": (
            "Loaded" if name not in table_errors else "Load Error"
        ),
    })

quality_report = pd.DataFrame(quality_rows)
show_dataframe(quality_report)

csv_download(
    quality_report,
    "cricbuzz_data_quality.csv",
    "⬇️ Download Data Quality Report",
)


# =========================================================
# 18. COMPLETE EXCEL EXPORT
# =========================================================

st.divider()
st.subheader("📥 Download Complete Excel Report")

if st.button("Prepare Excel Report"):
    try:
        available_tables = {
            name: df
            for name, df in table_data.items()
            if not df.empty
        }

        if available_tables:
            excel_bytes = make_excel_report(available_tables)

            st.download_button(
                label="⬇️ Download Excel Report",
                data=excel_bytes,
                file_name="Cricbuzz_LiveStats_Report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key="download_excel_report",
            )
        else:
            st.warning("There is no data available to export.")

    except Exception as error:
        st.error("Could not prepare the Excel report.")
        st.caption(str(error))


# =========================================================
# 19. SQL ANALYTICS AND CSV EXPORT
# =========================================================

st.divider()
st.header("📊 SQL Analytics & Data Export")
st.caption(
    "Run predefined MySQL reports and export results as CSV."
)

sql_reports = {
    "Runs Scored by Match": """
        SELECT
            m.match_id AS Match_ID,
            m.match_description AS Match_Description,
            SUM(i.runs) AS Total_Runs
        FROM matches m
        JOIN innings_scores i
            ON m.match_id = i.match_id
        GROUP BY m.match_id, m.match_description
        ORDER BY Total_Runs DESC
    """,

    "Innings Score Summary": """
        SELECT
            score_id AS Score_ID,
            match_id AS Match_ID,
            team_id AS Team_ID,
            runs AS Runs,
            wickets AS Wickets
        FROM innings_scores
        ORDER BY match_id, score_id
    """,

    "Top Run Scorers": """
        SELECT
            p.player_name AS Player_Name,
            SUM(b.runs) AS Total_Runs,
            SUM(b.balls_faced) AS Total_Balls,
            SUM(b.fours) AS Total_Fours,
            SUM(b.sixes) AS Total_Sixes
        FROM batting_performance b
        JOIN players p
            ON b.player_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Total_Runs DESC
        LIMIT 10
    """,

    "Top Wicket Takers": """
        SELECT
            p.player_name AS Player_Name,
            SUM(b.wickets) AS Total_Wickets,
            SUM(b.runs_conceded) AS Runs_Conceded
        FROM bowling_performance b
        JOIN players p
            ON b.player_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Total_Wickets DESC
        LIMIT 10
    """,

    "Team Run Analytics": """
        SELECT
            t.team_name AS Team_Name,
            SUM(i.runs) AS Total_Runs,
            SUM(i.wickets) AS Total_Wickets
        FROM teams t
        JOIN innings_scores i
            ON t.team_id = i.team_id
        GROUP BY t.team_id, t.team_name
        ORDER BY Total_Runs DESC
    """,
}


selected_report = st.selectbox(
    "Select SQL Report",
    list(sql_reports.keys()),
    key="sql_analytics_report",
)


if st.button("▶ Run SQL Report", key="run_sql_analytics"):
    try:
        with get_engine().connect() as connection:
            report_df = pd.read_sql(
                text(sql_reports[selected_report]),
                connection,
            )

        # Save the result so it remains available after reruns.
        st.session_state["sql_report_df"] = report_df
        st.session_state["sql_report_name"] = selected_report

    except Exception as error:
        st.error("Unable to execute this SQL report.")
        st.code(str(error))


# IMPORTANT:
# report_df is retrieved only after a report has been executed.
# csv_data is created only when report_df exists and has rows.

if "sql_report_df" in st.session_state:
    report_df = st.session_state["sql_report_df"]
    report_name = st.session_state.get(
        "sql_report_name", "SQL Report"
    )

    st.subheader(f"📋 {report_name}")

    if not report_df.empty:
        st.success(
            f"Report generated successfully: {len(report_df)} rows"
        )

        show_dataframe(report_df)

        # CSV data is defined here, not at the top of app.py.
        csv_data = report_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="⬇️ Download Report as CSV",
            data=csv_data,
            file_name=(
                report_name.lower().replace(" ", "_") + ".csv"
            ),
            mime="text/csv",
            key="download_sql_report",
        )

        # Visualize numeric columns from the SQL report.
        numeric_columns = report_df.select_dtypes(
            include="number"
        ).columns.tolist()

        chart_metrics = [
            col for col in numeric_columns
            if not col.lower().endswith("_id")
            and col.lower() != "id"
        ]

        if chart_metrics:
            st.subheader("📈 Report Visualization")

            chart_column = st.selectbox(
                "Choose metric to visualize",
                chart_metrics,
                key="sql_report_chart_metric",
            )

            label_column = report_df.columns[0]

            chart_df = report_df[
                [label_column, chart_column]
            ].copy()

            chart_df = chart_df.dropna(
                subset=[chart_column]
            ).head(10)

            if not chart_df.empty:
                chart_df[label_column] = (
                    chart_df[label_column].astype(str)
                )

                green_bar_chart(
                    chart_df,
                    label_column,
                    chart_column,
                    f"{chart_column} by {label_column}",
                )
            else:
                st.info("No valid data available for the chart.")
        else:
            st.info(
                "No suitable numeric columns are available "
                "for visualization."
            )

    else:
        st.info("The selected report returned no rows.")

else:
    st.info("Select a SQL report and click Run SQL Report.")


# =========================================================
# 20. FOOTER
# =========================================================

st.markdown(
    f"""
    <div class="footer">
        Cricbuzz LiveStats · Real-Time Cricket Insights ·
        SQL-Based Analytics
        <br>
        Last dashboard render:
        {datetime.now().strftime("%d %b %Y, %I:%M %p")}
    </div>
    """,
    unsafe_allow_html=True,
)