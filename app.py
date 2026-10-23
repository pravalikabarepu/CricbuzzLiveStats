import hmac
import logging
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from db_connection import get_engine as get_database_engine
from save_matches import save_matches

logger = logging.getLogger("cricbuzz_livestats")

# =========================================================
# 1. PAGE CONFIG + LIGHT CSS
# (table/input colours now come from .streamlit/config.toml)
# =========================================================

st.set_page_config(
    page_title="Cricbuzz LiveStats",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG, PANEL = "#101713", "#19251D"
GREEN, LIGHT_GREEN = "#39B85B", "#75DB91"
TEXT, MUTED, BORDER = "#E8F0EB", "#B6CBBD", "#31533A"

# Plain string (not an f-string) so CSS braces need no escaping.
CSS = """
<style>
.hero {
    background: linear-gradient(135deg, #19251D, #101713);
    border: 1px solid #31533A;
    border-left: 5px solid #39B85B;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 24px;
}
.hero h1 { color: #75DB91 !important; font-size: 36px; margin-bottom: 8px; }
.hero p  { color: #B6CBBD; margin-bottom: 0; }
[data-testid="stMetric"] {
    background: #19251D;
    border: 1px solid #31533A;
    border-radius: 12px;
    padding: 14px;
}
.footer {
    color: #B6CBBD; text-align: center; padding: 20px;
    border-top: 1px solid #31533A; margin-top: 30px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =========================================================
# 2. DATABASE
# =========================================================

TABLE_NAMES = [
    "matches", "teams", "series", "venues", "innings_scores",
    "players", "batting_performance", "bowling_performance", "partnerships",
]


@st.cache_resource
def get_engine():
    return get_database_engine()


@st.cache_data(ttl=60, show_spinner=False)
def load_table(table_name: str) -> pd.DataFrame:
    if table_name not in TABLE_NAMES:
        raise ValueError("Invalid table name")
    with get_engine().connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM `{table_name}`"), conn)


# =========================================================
# 3. HELPERS
# =========================================================

def get_column(df, names):
    lookup = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lookup:
            return lookup[n.lower()]
    return None


def numeric(s):
    return pd.to_numeric(s, errors="coerce")


def add_player_names(df, players_df):
    """Add a player_name column by joining on player_id, if it is missing."""
    if df.empty or players_df.empty:
        return df
    if get_column(df, ["player_name", "batsman_name", "bowler_name", "name", "player"]):
        return df

    df_id = get_column(df, ["player_id"])
    pl_id = get_column(players_df, ["player_id", "id"])
    pl_name = get_column(players_df, ["player_name", "name", "fullname"])
    if not (df_id and pl_id and pl_name):
        return df

    lookup = players_df[[pl_id, pl_name]].drop_duplicates(subset=pl_id).copy()
    lookup["_key"] = lookup[pl_id].astype(str)
    lookup = lookup[["_key", pl_name]].rename(columns={pl_name: "player_name"})

    out = df.copy()
    out["_key"] = out[df_id].astype(str)
    out = out.merge(lookup, on="_key", how="left").drop(columns="_key")
    # If a player id has no name in the players table, show the id instead.
    out["player_name"] = out["player_name"].fillna("Player " + out[df_id].astype(str))
    return out


def show_df(df):
    if df is None or df.empty:
        st.info("No records available.")
        return
    st.dataframe(df, width="stretch", hide_index=True)


def csv_button(df, filename, label):
    if df is None or df.empty:
        return
    st.download_button(
        label,
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=f"dl_{filename}",
    )


def select_filter(df, col, label, all_label, container=st):
    """Selectbox filter on one column; returns the filtered df."""
    if not col:
        return df
    options = sorted(df[col].dropna().astype(str).unique())
    choice = container.selectbox(label, [all_label] + options, key=f"f_{label}")
    if choice != all_label:
        df = df[df[col].astype(str) == choice]
    return df


def bar_chart(df, x, y, title, height=450):
    if df is None or df.empty or x not in df.columns or y not in df.columns:
        st.info("No chart data available.")
        return
    d = df.copy()
    d[y] = numeric(d[y])
    d = d.dropna(subset=[y])
    if d.empty:
        st.info("No numeric values are available.")
        return
    fig = px.bar(d, x=x, y=y, title=title, color_discrete_sequence=[GREEN])
    fig.update_layout(
        height=height, paper_bgcolor=BG, plot_bgcolor=PANEL,
        font_color=TEXT, title_font_color=LIGHT_GREEN, showlegend=False,
        xaxis=dict(title=None, tickangle=-30 if len(d) > 5 else 0, gridcolor=BORDER),
        yaxis=dict(title=y, gridcolor=BORDER),
    )
    fig.update_traces(marker_line_color=LIGHT_GREEN, marker_line_width=0.5)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def make_excel(tables: dict) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return out.getvalue()


def is_admin() -> bool:
    return st.session_state.get("is_admin", False)


# =========================================================
# 4. LOAD DATA
# =========================================================

table_data, table_errors = {}, {}

with st.spinner("Loading cricket data..."):
    for name in TABLE_NAMES:
        try:
            table_data[name] = load_table(name)
        except Exception:
            logger.exception("Failed to load table %s", name)
            table_data[name] = pd.DataFrame()
            table_errors[name] = "Could not load this table."

matches = table_data["matches"]
teams = table_data["teams"]
series = table_data["series"]
venues = table_data["venues"]
innings = table_data["innings_scores"]
players = table_data["players"]
batting = table_data["batting_performance"]
bowling = table_data["bowling_performance"]
partnerships = table_data["partnerships"]

# Batting/bowling tables usually store only player_id, so add the names
# from the players table. This is what makes the player charts appear.
batting = add_player_names(batting, players)
bowling = add_player_names(bowling, players)

# =========================================================
# 5. SIDEBAR (admin-only refresh)
# =========================================================

with st.sidebar:
    st.markdown("## 🏏 Cricbuzz LiveStats")
    st.caption("Cricket Analytics Dashboard")
    st.divider()

    try:
        admin_secret = st.secrets.get("ADMIN_PASSWORD", "")
    except Exception:
        admin_secret = ""

    if admin_secret:
        if not is_admin():
            with st.expander("🔒 Admin"):
                pw = st.text_input("Password", type="password", key="admin_pw")
                if st.button("Log in"):
                    if hmac.compare_digest(pw, str(admin_secret)):
                        st.session_state["is_admin"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            if st.button("🔄 Update Live Cricket Data", width="stretch"):
                try:
                    with st.spinner("Updating cricket data..."):
                        save_matches()
                    load_table.clear()
                    st.success("Cricket data updated.")
                    st.rerun()
                except Exception:
                    logger.exception("save_matches failed")
                    st.error("Update failed. Check the server logs.")
            if st.button("Log out"):
                st.session_state["is_admin"] = False
                st.rerun()

    st.divider()
    st.subheader("Database Status")
    for name in TABLE_NAMES:
        st.write(f"**{name}:** {len(table_data[name]):,} rows")

# =========================================================
# 6. HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">
        <h1>🏏 Cricbuzz LiveStats</h1>
        <p>Real-Time Cricket Insights · SQL-Based Analytics · Player Performance</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if table_errors:
    st.warning(
        "Some tables could not be loaded: " + ", ".join(table_errors) + "."
    )

tabs = st.tabs([
    "📊 Overview", "🏏 Matches", "📈 Innings", "🏏 Batting", "🎯 Bowling",
    "👥 Teams & Players", "🧮 SQL Reports", "📥 Export & Quality",
])

# =========================================================
# 7. OVERVIEW
# =========================================================

with tabs[0]:
    overview = [
        ("Total Matches", len(matches)), ("Teams", len(teams)),
        ("Players", len(players)), ("Innings Records", len(innings)),
        ("Batting Records", len(batting)), ("Bowling Records", len(bowling)),
        ("Venues", len(venues)), ("Partnerships", len(partnerships)),
    ]
    for start in range(0, len(overview), 4):
        for col, (label, value) in zip(st.columns(4), overview[start:start + 4]):
            col.metric(label, f"{value:,}")

    counts = pd.DataFrame({
        "Table": TABLE_NAMES,
        "Rows": [len(table_data[n]) for n in TABLE_NAMES],
    })
    bar_chart(counts, "Table", "Rows", "Records per Table", 400)

# =========================================================
# 8. MATCHES
# =========================================================

with tabs[1]:
    if matches.empty:
        st.info("No match records are available.")
    else:
        fmt_col = get_column(matches, ["match_format", "format", "match_type"])
        status_col = get_column(matches, ["status", "match_status", "state"])
        t1_col = get_column(matches, ["team1_name", "team1", "team1name", "home_team"])
        t2_col = get_column(matches, ["team2_name", "team2", "team2name", "away_team"])

        f = matches.copy()
        c1, c2, c3 = st.columns(3)
        f = select_filter(f, fmt_col, "Match Format", "All Formats", c1)
        f = select_filter(f, status_col, "Match Status", "All Statuses", c2)

        team_cols = [c for c in (t1_col, t2_col) if c]
        if team_cols:
            all_teams = sorted(
                set().union(*[set(matches[c].dropna().astype(str)) for c in team_cols])
            )
            chosen = c3.selectbox("Team", ["All Teams"] + all_teams, key="f_team")
            if chosen != "All Teams":
                mask = pd.Series(False, index=f.index)
                for c in team_cols:
                    mask |= f[c].astype(str) == chosen
                f = f[mask]

        st.caption(f"Showing {len(f):,} matches")

        if fmt_col and not f.empty:
            by_format = f[fmt_col].astype(str).value_counts().reset_index()
            by_format.columns = [fmt_col, "Matches"]
            bar_chart(by_format, fmt_col, "Matches", "Matches by Format", 400)

        show_df(f)
        csv_button(f, "cricbuzz_match_details.csv", "⬇️ Download Match Details")

# =========================================================
# 9. INNINGS
# =========================================================

with tabs[2]:
    if innings.empty:
        st.info("No innings score data is available.")
    else:
        inn_col = get_column(innings, ["innings_number", "innings_no", "inningsid", "innings"])
        runs_col = get_column(innings, ["runs", "total_runs", "score", "runs_scored"])
        match_col = get_column(innings, ["match_id", "matchid"])

        f = select_filter(innings.copy(), inn_col, "Innings", "All Innings")

        if runs_col:
            d = f.copy()
            d[runs_col] = numeric(d[runs_col])
            if inn_col and match_col:
                d["Chart Label"] = "M" + d[match_col].astype(str) + " · I" + d[inn_col].astype(str)
            elif inn_col:
                d["Chart Label"] = "Innings " + d[inn_col].astype(str)
            else:
                d["Chart Label"] = [f"Innings {i + 1}" for i in range(len(d))]
            bar_chart(d, "Chart Label", runs_col, "Runs by Innings", 500)

        show_df(f)
        csv_button(f, "cricbuzz_innings_scores.csv", "⬇️ Download Innings Scores")

# =========================================================
# 10. BATTING
# =========================================================

with tabs[3]:
    if batting.empty:
        st.info("No batting performance data is available.")
    else:
        p_col = (
            get_column(batting, ["player_name", "batsman_name", "name", "player"])
            or get_column(batting, ["player_id"])
        )
        runs_col = get_column(batting, ["runs", "runs_scored", "batsman_runs", "total_runs"])
        balls_col = get_column(batting, ["balls", "balls_faced", "ballsfaced"])
        fours_col = get_column(batting, ["fours", "four", "fours_count"])
        sixes_col = get_column(batting, ["sixes", "six", "sixes_count"])

        f = select_filter(batting.copy(), p_col, "Batting Player", "All Players").copy()

        if runs_col:
            f[runs_col] = numeric(f[runs_col])
            if p_col:
                top = (
                    f.dropna(subset=[runs_col]).groupby(p_col, as_index=False)[runs_col]
                    .sum().sort_values(runs_col, ascending=False).head(10)
                )
                top[p_col] = top[p_col].astype(str)
                bar_chart(top, p_col, runs_col, "Top 10 Run Scorers")

            cols = st.columns(4)
            cols[0].metric("Runs", f"{f[runs_col].sum():,.0f}")
            for c, col_name, label in (
                (cols[1], balls_col, "Balls Faced"),
                (cols[2], fours_col, "Fours"),
                (cols[3], sixes_col, "Sixes"),
            ):
                if col_name:
                    c.metric(label, f"{numeric(f[col_name]).sum():,.0f}")

        show_df(f)
        csv_button(f, "cricbuzz_batting_performance.csv", "⬇️ Download Batting Data")

# =========================================================
# 11. BOWLING
# =========================================================

with tabs[4]:
    if bowling.empty:
        st.info("No bowling performance data is available.")
    else:
        b_col = (
            get_column(bowling, ["player_name", "bowler_name", "name", "player"])
            or get_column(bowling, ["player_id"])
        )
        w_col = get_column(bowling, ["wickets", "wickets_taken", "total_wickets"])
        rc_col = get_column(bowling, ["runs_conceded", "runs", "conceded"])

        f = select_filter(bowling.copy(), b_col, "Bowling Player", "All Players").copy()

        if w_col:
            f[w_col] = numeric(f[w_col])
            if b_col:
                top = (
                    f.dropna(subset=[w_col]).groupby(b_col, as_index=False)[w_col]
                    .sum().sort_values(w_col, ascending=False).head(10)
                )
                top[b_col] = top[b_col].astype(str)
                bar_chart(top, b_col, w_col, "Top 10 Wicket Takers")

        m1, m2 = st.columns(2)
        if w_col:
            m1.metric("Total Wickets", f"{f[w_col].sum():,.0f}")
        if rc_col:
            m2.metric("Runs Conceded", f"{numeric(f[rc_col]).sum():,.0f}")

        show_df(f)
        csv_button(f, "cricbuzz_bowling_performance.csv", "⬇️ Download Bowling Data")

# =========================================================
# 12. TEAMS & PLAYERS
# =========================================================

with tabs[5]:
    st.subheader("📊 Team Run Analytics")
    st.caption("Totals include every stored innings, including matches still in progress.")

    team_id_col = get_column(innings, ["team_id", "batteamid"]) if not innings.empty else None
    runs_col = get_column(innings, ["runs", "total_runs", "score"]) if not innings.empty else None
    wk_col = get_column(innings, ["wickets", "total_wickets"]) if not innings.empty else None

    if team_id_col and runs_col:
        tr = innings.copy()
        tr[runs_col] = numeric(tr[runs_col])
        if wk_col:
            tr[wk_col] = numeric(tr[wk_col])

        label_col = team_id_col
        if not teams.empty:
            t_id = get_column(teams, ["team_id", "id"])
            t_name = get_column(teams, ["team_name", "name"])
            if t_id and t_name:
                lookup = (
                    teams[[t_id, t_name]]
                    .drop_duplicates(subset=t_id)
                    .rename(columns={t_name: "Team"})
                )
                tr = tr.merge(lookup, left_on=team_id_col, right_on=t_id, how="left")
                # Show the id when a team has no name in the teams table.
                tr["Team"] = tr["Team"].fillna("Team " + tr[team_id_col].astype(str))
                label_col = "Team"

        agg = {runs_col: "sum"}
        if wk_col:
            agg[wk_col] = "sum"
        summary = tr.groupby(label_col, as_index=False).agg(agg).sort_values(
            runs_col, ascending=False
        )
        summary[label_col] = summary[label_col].astype(str)
        bar_chart(summary, label_col, runs_col, "Total Runs by Team")
        show_df(summary)
        csv_button(summary, "cricbuzz_team_run_analytics.csv", "⬇️ Download Team Analytics")
    else:
        st.info("Team ID or runs columns are unavailable.")

    st.divider()
    st.subheader("👥 Player Directory")
    if players.empty:
        st.info("No player records are available.")
    else:
        name_col = get_column(players, ["player_name", "name", "fullname"])
        shown = players.copy()
        if name_col:
            q = st.text_input("Search Players", placeholder="Enter a player name...")
            if q.strip():
                shown = shown[
                    shown[name_col].astype(str).str.contains(q.strip(), case=False, na=False, regex=False)
                ]
        show_df(shown)
        csv_button(shown, "cricbuzz_players.csv", "⬇️ Download Player Directory")

    st.divider()
    for title, df in [("Teams", teams), ("Series", series), ("Venues", venues), ("Partnerships", partnerships)]:
        with st.expander(title):
            show_df(df)

# =========================================================
# 13. SQL REPORTS
# =========================================================

SQL_REPORTS = {
    "Runs Scored by Match": """
        SELECT m.match_id AS Match_ID, m.match_description AS Match_Description,
               SUM(i.runs) AS Total_Runs
        FROM matches m JOIN innings_scores i ON m.match_id = i.match_id
        GROUP BY m.match_id, m.match_description
        ORDER BY Total_Runs DESC
    """,
    "Innings Score Summary": """
        SELECT score_id AS Score_ID, match_id AS Match_ID, team_id AS Team_ID,
               runs AS Runs, wickets AS Wickets
        FROM innings_scores ORDER BY match_id, score_id
    """,
    "Top Run Scorers": """
        SELECT p.player_name AS Player_Name, SUM(b.runs) AS Total_Runs,
               SUM(b.balls_faced) AS Total_Balls, SUM(b.fours) AS Total_Fours,
               SUM(b.sixes) AS Total_Sixes
        FROM batting_performance b JOIN players p ON b.player_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Total_Runs DESC LIMIT 10
    """,
    "Top Wicket Takers": """
        SELECT p.player_name AS Player_Name, SUM(b.wickets) AS Total_Wickets,
               SUM(b.runs_conceded) AS Runs_Conceded
        FROM bowling_performance b JOIN players p ON b.player_id = p.player_id
        GROUP BY p.player_id, p.player_name
        ORDER BY Total_Wickets DESC LIMIT 10
    """,
    "Team Run Analytics": """
        SELECT t.team_name AS Team_Name, SUM(i.runs) AS Total_Runs,
               SUM(i.wickets) AS Total_Wickets
        FROM teams t JOIN innings_scores i ON t.team_id = i.team_id
        GROUP BY t.team_id, t.team_name
        ORDER BY Total_Runs DESC
    """,
}

with tabs[6]:
    st.caption("Run predefined MySQL reports and export results as CSV.")
    report_choice = st.selectbox("Select SQL Report", list(SQL_REPORTS), key="sql_report_choice")

    if st.button("▶ Run SQL Report", key="run_sql_report"):
        try:
            with get_engine().connect() as conn:
                st.session_state["sql_report_df"] = pd.read_sql(text(SQL_REPORTS[report_choice]), conn)
            st.session_state["sql_report_name"] = report_choice
        except Exception:
            logger.exception("SQL report failed: %s", report_choice)
            st.error("Unable to run this report. Check the server logs.")

    rdf = st.session_state.get("sql_report_df")
    rname = st.session_state.get("sql_report_name", "SQL Report")

    if rdf is None:
        st.info("Select a report and click Run SQL Report.")
    elif rdf.empty:
        st.info("The selected report returned no rows.")
    else:
        st.subheader(f"📋 {rname}")
        st.success(f"{len(rdf)} rows")
        show_df(rdf)
        csv_button(rdf, rname.lower().replace(" ", "_") + ".csv", "⬇️ Download Report as CSV")

        metrics = [
            c for c in rdf.select_dtypes("number").columns
            if not c.lower().endswith("_id") and c.lower() != "id"
        ]
        if metrics:
            metric = st.selectbox("Metric to visualize", metrics, key="sql_chart_metric")
            label = rdf.columns[0]
            d = rdf[[label, metric]].dropna(subset=[metric]).head(10)
            d[label] = d[label].astype(str)
            bar_chart(d, label, metric, f"{metric} by {label}")

# =========================================================
# 14. EXPORT & DATA QUALITY
# =========================================================

with tabs[7]:
    st.subheader("🔍 Data Quality Check")
    rows = []
    for name in TABLE_NAMES:
        df = table_data[name]
        rows.append({
            "Table": name,
            "Rows": len(df),
            "Columns": len(df.columns),
            "Missing Cells": int(df.isna().sum().sum()) if not df.empty else 0,
            "Duplicate Rows": int(df.duplicated().sum()) if not df.empty else 0,
            "Status": "Load Error" if name in table_errors else "Loaded",
        })
    quality = pd.DataFrame(rows)
    show_df(quality)
    csv_button(quality, "cricbuzz_data_quality.csv", "⬇️ Download Data Quality Report")

    st.divider()
    st.subheader("📥 Complete Excel Report")
    if st.button("Prepare Excel Report"):
        available = {n: d for n, d in table_data.items() if not d.empty}
        if not available:
            st.warning("There is no data available to export.")
        else:
            try:
                st.session_state["excel_bytes"] = make_excel(available)
            except Exception:
                logger.exception("Excel export failed")
                st.error("Could not prepare the Excel report.")

    if "excel_bytes" in st.session_state:
        st.download_button(
            "⬇️ Download Excel Report",
            st.session_state["excel_bytes"],
            file_name="Cricbuzz_LiveStats_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel",
        )

# =========================================================
# 15. FOOTER
# =========================================================

st.markdown(
    f"""
    <div class="footer">
        Cricbuzz LiveStats · Real-Time Cricket Insights · SQL-Based Analytics<br>
        Last dashboard render: {datetime.now().strftime("%d %b %Y, %I:%M %p")}
    </div>
    """,
    unsafe_allow_html=True,
)
