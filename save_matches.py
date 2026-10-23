import logging
from datetime import datetime, timezone

import requests

from cricbuzz_api import (
    CricbuzzAPIError,
    get_live_matches,
    get_match_scorecard,
    iter_matches,
)
from db_connection import get_connection

logger = logging.getLogger("cricbuzz_livestats")

# Each scorecard costs one API request. Keep this within your plan's quota.
MAX_SCORECARDS_PER_RUN = 10

NOT_OUT_TEXTS = {"not out", "batting"}


# =========================================================
# 1. HELPER FUNCTIONS
# =========================================================

def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def convert_timestamp(value):
    """Convert Cricbuzz millisecond timestamps to MySQL datetime."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(
            int(value) / 1000, tz=timezone.utc
        ).replace(tzinfo=None)
    except (ValueError, TypeError, OSError):
        return None


def convert_overs_to_balls(overs):
    """Convert overs notation such as 19.4 into 118 balls."""
    if overs is None:
        return 0
    try:
        parts = str(overs).split(".")
        completed = int(parts[0])
        extra = int(parts[1]) if len(parts) == 2 else 0
        if not 0 <= extra <= 5:
            return 0
        return completed * 6 + extra
    except (ValueError, TypeError, IndexError):
        return 0


def normalize_name(name):
    return " ".join(str(name or "").strip().casefold().split())


def other_team(team_id, team1_id, team2_id):
    """Return the opposing team's id (used for bowlers)."""
    if team_id is None:
        return None
    if team_id == team1_id:
        return team2_id
    if team_id == team2_id:
        return team1_id
    return None


def get_team_id(cursor, team_name, team_aliases):
    normalized = normalize_name(team_name)
    if not normalized:
        return None
    if normalized in team_aliases:
        return team_aliases[normalized]

    cursor.execute(
        """
        SELECT team_id FROM teams
        WHERE LOWER(TRIM(team_name)) = LOWER(TRIM(%s))
        LIMIT 1
        """,
        (team_name,),
    )
    result = cursor.fetchone()
    return result[0] if result else None


def save_player(cursor, player):
    player_id = player.get("id")
    player_name = player.get("name") or player.get("nickname")
    if player_id is None or not player_name:
        return None

    cursor.execute(
        """
        INSERT INTO players (player_id, player_name, country)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE player_name = VALUES(player_name)
        """,
        (player_id, player_name, None),
    )
    return player_id


# =========================================================
# 2. SAVE TEAMS, SERIES, VENUE AND MATCH ROW
# =========================================================

def save_match_details(cursor, info):
    """Upsert teams, series, venue and the match. Returns ids + aliases."""
    match_id = info.get("matchId")
    team1 = info.get("team1") or {}
    team2 = info.get("team2") or {}
    venue = info.get("venueInfo") or {}

    team1_id = team1.get("teamId")
    team2_id = team2.get("teamId")
    series_id = info.get("seriesId")
    venue_id = venue.get("id")

    team_aliases = {}

    for team in (team1, team2):
        current_id = team.get("teamId")
        if current_id is None:
            continue

        team_name = team.get("teamName") or "Unknown"
        short_name = team.get("teamSName") or ""

        cursor.execute(
            """
            INSERT INTO teams (team_id, team_name, team_short_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                team_name = VALUES(team_name),
                team_short_name = VALUES(team_short_name)
            """,
            (current_id, team_name, short_name),
        )

        team_aliases[normalize_name(team_name)] = current_id
        if short_name:
            team_aliases[normalize_name(short_name)] = current_id

    if series_id is not None:
        cursor.execute(
            """
            INSERT INTO series (series_id, series_name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE series_name = VALUES(series_name)
            """,
            (series_id, info.get("seriesName") or "Unknown"),
        )

    if venue_id is not None:
        cursor.execute(
            """
            INSERT INTO venues (venue_id, venue_name, city, timezone)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                venue_name = VALUES(venue_name),
                city = VALUES(city),
                timezone = VALUES(timezone)
            """,
            (
                venue_id,
                venue.get("ground") or "Unknown",
                venue.get("city") or "",
                venue.get("timezone") or "",
            ),
        )

    cursor.execute(
        """
        INSERT INTO matches (
            match_id, series_id, team1_id, team2_id, venue_id,
            match_description, match_format, start_date, end_date,
            match_state, match_status, current_batting_team_id,
            toss_winner_team_id, toss_decision
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            series_id = VALUES(series_id),
            team1_id = VALUES(team1_id),
            team2_id = VALUES(team2_id),
            venue_id = VALUES(venue_id),
            match_description = VALUES(match_description),
            match_format = VALUES(match_format),
            start_date = VALUES(start_date),
            end_date = VALUES(end_date),
            match_status = VALUES(match_status),
            match_state = VALUES(match_state),
            current_batting_team_id = VALUES(current_batting_team_id)
        """,
        (
            match_id,
            series_id,
            team1_id,
            team2_id,
            venue_id,
            info.get("matchDesc") or "",
            info.get("matchFormat") or "",
            convert_timestamp(info.get("startDate")),
            convert_timestamp(info.get("endDate")),
            info.get("state") or "",
            info.get("status") or "",
            info.get("currBatTeamId"),
            None,
            None,
        ),
    )

    return team_aliases, team1_id, team2_id


# =========================================================
# 3. SAVE SCORECARD (innings, batting, bowling, partnerships)
# =========================================================

def save_scorecard(cursor, match_id, scorecard, team_aliases,
                   team1_id, team2_id):
    innings_saved = batting_saved = bowling_saved = partnerships_saved = 0

    innings_list = scorecard.get("scorecard")

    if not innings_list:
        if "scoreCard" in scorecard:
            print(
                f"Match {match_id}: scorecard uses the newer camelCase "
                "format, but this script reads the older lowercase "
                "format. Nothing was saved for this match."
            )
        return 0, 0, 0, 0

    for innings in innings_list:
        innings_number = to_int(innings.get("inningsid"), default=None)
        if innings_number is None:
            continue

        team_name = innings.get("batteamname") or innings.get("batteamsname")
        team_id = get_team_id(cursor, team_name, team_aliases)
        bowling_team_id = other_team(team_id, team1_id, team2_id)

        # ---- innings totals ----
        cursor.execute(
            "DELETE FROM innings_scores "
            "WHERE match_id = %s AND innings_number = %s",
            (match_id, innings_number),
        )
        overs = innings.get("overs")
        cursor.execute(
            """
            INSERT INTO innings_scores (
                match_id, team_id, innings_number, runs, wickets,
                overs_text, balls_bowled
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                match_id,
                team_id,
                innings_number,
                to_int(innings.get("score")),
                to_int(innings.get("wickets")),
                str(overs) if overs is not None else None,
                convert_overs_to_balls(overs),
            ),
        )
        innings_saved += 1

        # ---- batting ----
        cursor.execute(
            "DELETE FROM batting_performance "
            "WHERE match_id = %s AND innings_number = %s",
            (match_id, innings_number),
        )
        for batsman in innings.get("batsman") or []:
            runs = to_int(batsman.get("runs"))
            balls = to_int(batsman.get("balls"))
            dismissal = str(batsman.get("outdec") or "").strip()

            # Skip players who did not bat.
            if not dismissal and runs == 0 and balls == 0:
                continue

            player_id = save_player(cursor, batsman)
            if player_id is None:
                continue

            not_out = dismissal.lower() in NOT_OUT_TEXTS or not dismissal

            cursor.execute(
                """
                INSERT INTO batting_performance (
                    match_id, player_id, team_id, innings_number,
                    runs, balls_faced, fours, sixes,
                    dismissal_type, not_out
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    player_id,
                    team_id,
                    innings_number,
                    runs,
                    balls,
                    to_int(batsman.get("fours")),
                    to_int(batsman.get("sixes")),
                    None if not_out else dismissal[:50],
                    1 if not_out else 0,
                ),
            )
            batting_saved += 1

        # ---- partnerships ----
        cursor.execute(
            "DELETE FROM partnerships "
            "WHERE match_id = %s AND innings_number = %s",
            (match_id, innings_number),
        )
        partnership_data = innings.get("partnership") or {}
        partnership_list = (
            partnership_data.get("partnership") or []
            if isinstance(partnership_data, dict)
            else []
        )

        for number, p in enumerate(partnership_list, start=1):
            player1_id = save_player(
                cursor, {"id": p.get("bat1id"), "name": p.get("bat1name")}
            )
            player2_id = save_player(
                cursor, {"id": p.get("bat2id"), "name": p.get("bat2name")}
            )
            if player1_id is None or player2_id is None:
                continue

            cursor.execute(
                """
                INSERT INTO partnerships (
                    match_id, innings_number, player1_id, player2_id,
                    runs_scored, balls_faced, wicket_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    innings_number,
                    player1_id,
                    player2_id,
                    to_int(p.get("totalruns")),
                    to_int(p.get("totalballs")),
                    number,
                ),
            )
            partnerships_saved += 1

        # ---- bowling (bowlers belong to the OTHER team) ----
        cursor.execute(
            "DELETE FROM bowling_performance "
            "WHERE match_id = %s AND innings_number = %s",
            (match_id, innings_number),
        )
        for bowler in innings.get("bowler") or []:
            player_id = save_player(cursor, bowler)
            if player_id is None:
                continue

            balls_value = bowler.get("balls")
            if balls_value is None:
                balls_value = convert_overs_to_balls(bowler.get("overs"))

            cursor.execute(
                """
                INSERT INTO bowling_performance (
                    match_id, player_id, team_id, innings_number,
                    balls_bowled, runs_conceded, wickets, maidens,
                    wides, no_balls
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    player_id,
                    bowling_team_id,
                    innings_number,
                    to_int(balls_value),
                    to_int(bowler.get("runs")),
                    to_int(bowler.get("wickets")),
                    to_int(bowler.get("maidens")),
                    0,
                    0,
                ),
            )
            bowling_saved += 1

    return innings_saved, batting_saved, bowling_saved, partnerships_saved


# =========================================================
# 4. MAIN: FETCH LIVE MATCHES AND SAVE
# =========================================================

def save_matches():
    """Fetch live matches and save them. Commits one match at a time."""
    data = get_live_matches()

    totals = {
        "matches": 0, "scorecards": 0, "innings": 0,
        "batting": 0, "bowling": 0, "partnerships": 0, "failed": 0,
    }
    scorecards_fetched = 0

    connection = get_connection()
    cursor = connection.cursor()

    try:
        for match in iter_matches(data):
            info = match.get("matchInfo") or {}
            match_id = info.get("matchId")
            if not match_id:
                continue

            try:
                team_aliases, team1_id, team2_id = save_match_details(
                    cursor, info
                )
                totals["matches"] += 1

                if scorecards_fetched < MAX_SCORECARDS_PER_RUN:
                    scorecards_fetched += 1
                    try:
                        scorecard = get_match_scorecard(match_id)
                    except (CricbuzzAPIError, requests.RequestException) as e:
                        print(f"Could not fetch scorecard for match "
                              f"{match_id}: {e}")
                        scorecard = None

                    if scorecard:
                        inn, bat, bowl, part = save_scorecard(
                            cursor, match_id, scorecard,
                            team_aliases, team1_id, team2_id,
                        )
                        totals["scorecards"] += 1
                        totals["innings"] += inn
                        totals["batting"] += bat
                        totals["bowling"] += bowl
                        totals["partnerships"] += part

                connection.commit()

            except Exception:
                connection.rollback()
                totals["failed"] += 1
                logger.exception("Failed to save match %s", match_id)

    finally:
        cursor.close()
        connection.close()

    print("\n========== SAVE SUMMARY ==========")
    print(f"Matches saved: {totals['matches']}")
    print(f"Scorecards processed: {totals['scorecards']}")
    print(f"Innings scores saved: {totals['innings']}")
    print(f"Batting records saved: {totals['batting']}")
    print(f"Bowling records saved: {totals['bowling']}")
    print(f"Partnership records saved: {totals['partnerships']}")
    print(f"Matches that failed: {totals['failed']}")
    print("==================================")

    if totals["failed"] and not totals["matches"]:
        raise RuntimeError("No matches could be saved. Check the logs.")

    return totals


if __name__ == "__main__":
    try:
        save_matches()
    except Exception as error:
        print("Could not save matches:", error)