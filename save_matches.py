
from datetime import datetime, timezone

import requests

from cricbuzz_api import get_live_matches, get_match_scorecard
from db_connection import get_connection


# =========================================================
# 1. HELPER FUNCTIONS
# =========================================================

def convert_timestamp(value):
    """Convert Cricbuzz millisecond timestamps to MySQL datetime."""
    if not value:
        return None

    try:
        return datetime.fromtimestamp(
            int(value) / 1000,
            tz=timezone.utc
        ).replace(tzinfo=None)
    except (ValueError, TypeError, OSError):
        return None


def convert_overs_to_balls(overs):
    """Convert overs notation such as 19.4 into 118 balls."""
    if overs is None:
        return 0

    try:
        parts = str(overs).split(".")
        completed_overs = int(parts[0])
        balls_in_over = int(parts[1]) if len(parts) == 2 else 0

        if not 0 <= balls_in_over <= 5:
            return 0

        return completed_overs * 6 + balls_in_over

    except (ValueError, TypeError, IndexError):
        return 0


def normalize_name(name):
    """Normalize names for matching."""
    return " ".join(str(name or "").strip().casefold().split())


def get_team_id(cursor, team_name, team_aliases):
    """Find a team ID using its name or alias."""
    normalized = normalize_name(team_name)

    if not normalized:
        return None

    if normalized in team_aliases:
        return team_aliases[normalized]

    cursor.execute(
        """
        SELECT team_id
        FROM teams
        WHERE LOWER(TRIM(team_name)) = LOWER(TRIM(%s))
        LIMIT 1
        """,
        (team_name,)
    )

    result = cursor.fetchone()
    return result[0] if result else None


def save_player(cursor, player):
    """Insert or update a player."""
    player_id = player.get("id")
    player_name = player.get("name") or player.get("nickname")

    if player_id is None or not player_name:
        return None

    cursor.execute(
        """
        INSERT INTO players (player_id, player_name, country)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            player_name = VALUES(player_name)
        """,
        (player_id, player_name, None)
    )

    return player_id


# =========================================================
# 2. SAVE SCORECARD, BATTING, BOWLING AND PARTNERSHIPS
# =========================================================

def save_scorecard(cursor, match_id, scorecard, team_aliases):
    """Save innings totals, batting, bowling and partnerships."""

    innings_saved = 0
    batting_saved = 0
    bowling_saved = 0
    partnerships_saved = 0

    for innings in scorecard.get("scorecard", []):
        innings_number = innings.get("inningsid")

        if innings_number is None:
            continue

        try:
            innings_number = int(innings_number)
        except (ValueError, TypeError):
            continue

        team_name = (
            innings.get("batteamname")
            or innings.get("batteamsname")
        )

        team_id = get_team_id(
            cursor,
            team_name,
            team_aliases
        )

        # -------------------------------------------------
        # A. SAVE INNINGS TOTALS
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM innings_scores
            WHERE match_id = %s AND innings_number = %s
            """,
            (match_id, innings_number)
        )

        cursor.execute(
            """
            INSERT INTO innings_scores (
                match_id,
                team_id,
                innings_number,
                runs,
                wickets,
                overs_text,
                balls_bowled
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                match_id,
                team_id,
                innings_number,
                innings.get("score") or 0,
                innings.get("wickets") or 0,
                (
                    str(innings.get("overs"))
                    if innings.get("overs") is not None
                    else None
                ),
                convert_overs_to_balls(innings.get("overs"))
            )
        )

        innings_saved += 1

        # -------------------------------------------------
        # B. SAVE BATTING PERFORMANCE
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM batting_performance
            WHERE match_id = %s AND innings_number = %s
            """,
            (match_id, innings_number)
        )

        for batsman in innings.get("batsman", []):
            player_id = save_player(cursor, batsman)

            if player_id is None:
                continue

            dismissal = str(
                batsman.get("outdec") or ""
            ).strip()

            cursor.execute(
                """
                INSERT INTO batting_performance (
                    match_id,
                    player_id,
                    team_id,
                    innings_number,
                    runs,
                    balls_faced,
                    fours,
                    sixes,
                    dismissal_type,
                    not_out
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    player_id,
                    team_id,
                    innings_number,
                    batsman.get("runs") or 0,
                    batsman.get("balls") or 0,
                    batsman.get("fours") or 0,
                    batsman.get("sixes") or 0,
                    dismissal[:50] if dismissal else None,
                    0 if dismissal else 1
                )
            )

            batting_saved += 1

        # -------------------------------------------------
        # C. SAVE PARTNERSHIP PERFORMANCE
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM partnerships
            WHERE match_id = %s AND innings_number = %s
            """,
            (match_id, innings_number)
        )

        partnership_data = innings.get("partnership") or {}

        # Cricbuzz returns a list inside the partnership object.
        if isinstance(partnership_data, dict):
            partnership_list = (
                partnership_data.get("partnership") or []
            )
        else:
            partnership_list = []

        for partnership_number, partnership in enumerate(
            partnership_list,
            start=1
        ):
            player1_id = save_player(
                cursor,
                {
                    "id": partnership.get("bat1id"),
                    "name": partnership.get("bat1name")
                }
            )

            player2_id = save_player(
                cursor,
                {
                    "id": partnership.get("bat2id"),
                    "name": partnership.get("bat2name")
                }
            )

            if player1_id is None or player2_id is None:
                continue

            cursor.execute(
                """
                INSERT INTO partnerships (
                    match_id,
                    innings_number,
                    player1_id,
                    player2_id,
                    runs_scored,
                    balls_faced,
                    wicket_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    innings_number,
                    player1_id,
                    player2_id,
                    partnership.get("totalruns") or 0,
                    partnership.get("totalballs") or 0,
                    partnership_number
                )
            )

            partnerships_saved += 1

        # -------------------------------------------------
        # D. SAVE BOWLING PERFORMANCE
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM bowling_performance
            WHERE match_id = %s AND innings_number = %s
            """,
            (match_id, innings_number)
        )

        for bowler in innings.get("bowler", []):
            player_id = save_player(cursor, bowler)

            if player_id is None:
                continue

            balls_value = bowler.get("balls")

            if balls_value is None:
                balls_value = convert_overs_to_balls(
                    bowler.get("overs")
                )

            cursor.execute(
                """
                INSERT INTO bowling_performance (
                    match_id,
                    player_id,
                    team_id,
                    innings_number,
                    balls_bowled,
                    runs_conceded,
                    wickets,
                    maidens,
                    wides,
                    no_balls
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    match_id,
                    player_id,
                    team_id,
                    innings_number,
                    int(balls_value or 0),
                    bowler.get("runs") or 0,
                    bowler.get("wickets") or 0,
                    bowler.get("maidens") or 0,
                    0,
                    0
                )
            )

            bowling_saved += 1

    return (
        innings_saved,
        batting_saved,
        bowling_saved,
        partnerships_saved
    )


# =========================================================
# 3. SAVE LIVE MATCHES AND SCORECARDS
# =========================================================

def save_matches():
    """Fetch live matches and save their database records."""

    data = get_live_matches()

    connection = get_connection()
    cursor = connection.cursor()

    saved_count = 0
    innings_saved_count = 0
    batting_saved_count = 0
    bowling_saved_count = 0
    partnerships_saved_count = 0
    scorecards_processed = 0

    try:
        for type_match in data.get("typeMatches", []):
            for series_match in type_match.get("seriesMatches", []):
                wrapper = series_match.get("seriesAdWrapper", {})

                for match in wrapper.get("matches", []):
                    info = match.get("matchInfo", {})
                    match_id = info.get("matchId")

                    if not match_id:
                        continue

                    team1 = info.get("team1", {})
                    team2 = info.get("team2", {})
                    venue = info.get("venueInfo") or {}

                    team1_id = team1.get("teamId")
                    team2_id = team2.get("teamId")
                    series_id = info.get("seriesId")
                    venue_id = venue.get("id")

                    # -------------------------------------
                    # A. SAVE TEAMS AND TEAM ALIASES
                    # -------------------------------------

                    team_aliases = {}

                    for team in (team1, team2):
                        current_team_id = team.get("teamId")

                        if current_team_id is None:
                            continue

                        team_name = team.get("teamName") or "Unknown"
                        short_name = team.get("teamSName") or ""

                        cursor.execute(
                            """
                            INSERT INTO teams (
                                team_id,
                                team_name,
                                team_short_name
                            )
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                team_name = VALUES(team_name),
                                team_short_name = VALUES(team_short_name)
                            """,
                            (
                                current_team_id,
                                team_name,
                                short_name
                            )
                        )

                        team_aliases[
                            normalize_name(team_name)
                        ] = current_team_id

                        if short_name:
                            team_aliases[
                                normalize_name(short_name)
                            ] = current_team_id

                    # -------------------------------------
                    # B. SAVE SERIES
                    # -------------------------------------

                    if series_id is not None:
                        cursor.execute(
                            """
                            INSERT INTO series (
                                series_id,
                                series_name
                            )
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE
                                series_name = VALUES(series_name)
                            """,
                            (
                                series_id,
                                info.get("seriesName") or "Unknown"
                            )
                        )

                    # -------------------------------------
                    # C. SAVE VENUE
                    # -------------------------------------

                    if venue_id is not None:
                        cursor.execute(
                            """
                            INSERT INTO venues (
                                venue_id,
                                venue_name,
                                city,
                                timezone
                            )
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
                                venue.get("timezone") or ""
                            )
                        )

                    # -------------------------------------
                    # D. SAVE MATCH DETAILS
                    # -------------------------------------

                    cursor.execute(
                        """
                        INSERT INTO matches (
                            match_id,
                            series_id,
                            team1_id,
                            team2_id,
                            venue_id,
                            match_description,
                            match_format,
                            start_date,
                            end_date,
                            match_state,
                            match_status,
                            current_batting_team_id,
                            toss_winner_team_id,
                            toss_decision
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        ON DUPLICATE KEY UPDATE
                            series_id = VALUES(series_id),
                            team1_id = VALUES(team1_id),
                            team2_id = VALUES(team2_id),
                            venue_id = VALUES(venue_id),
                            match_status = VALUES(match_status),
                            match_state = VALUES(match_state),
                            current_batting_team_id =
                                VALUES(current_batting_team_id)
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
                            None
                        )
                    )

                    # -------------------------------------
                    # E. SAVE LIVE INNINGS TOTALS
                    # -------------------------------------

                    match_score = match.get("matchScore") or {}

                    for team_key, current_team_id in (
                        ("team1Score", team1_id),
                        ("team2Score", team2_id)
                    ):
                        team_score = match_score.get(team_key) or {}

                        for innings_key, live_innings in team_score.items():
                            if not innings_key.startswith("inngs"):
                                continue

                            if not isinstance(live_innings, dict):
                                continue

                            try:
                                innings_number = int(
                                    innings_key.replace("inngs", "")
                                )
                            except ValueError:
                                continue

                            if current_team_id is None:
                                continue

                            cursor.execute(
                                """
                                DELETE FROM innings_scores
                                WHERE match_id = %s
                                  AND innings_number = %s
                                """,
                                (match_id, innings_number)
                            )

                            overs_text = live_innings.get("overs")

                            cursor.execute(
                                """
                                INSERT INTO innings_scores (
                                    match_id,
                                    team_id,
                                    innings_number,
                                    runs,
                                    wickets,
                                    overs_text,
                                    balls_bowled
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    match_id,
                                    current_team_id,
                                    innings_number,
                                    live_innings.get("runs") or 0,
                                    live_innings.get("wickets") or 0,
                                    (
                                        str(overs_text)
                                        if overs_text is not None
                                        else None
                                    ),
                                    convert_overs_to_balls(overs_text)
                                )
                            )

                            innings_saved_count += 1

                    saved_count += 1

                    # -------------------------------------
                    # F. FETCH AND SAVE SCORECARD
                    # -------------------------------------

                    try:
                        scorecard = get_match_scorecard(match_id)

                        (
                            innings_count,
                            batting_count,
                            bowling_count,
                            partnerships_count
                        ) = save_scorecard(
                            cursor,
                            match_id,
                            scorecard,
                            team_aliases
                        )

                        innings_saved_count += innings_count
                        batting_saved_count += batting_count
                        bowling_saved_count += bowling_count
                        partnerships_saved_count += partnerships_count

                        scorecards_processed += 1

                    except requests.RequestException as error:
                        print(
                            f"Could not fetch scorecard for match "
                            f"{match_id}: {error}"
                        )
                        continue

        # ---------------------------------------------
        # G. COMMIT AND PRINT SUMMARY
        # ---------------------------------------------

        connection.commit()

        print("\n========== SAVE SUMMARY ==========")
        print(f"Matches processed: {saved_count}")
        print(f"Scorecards processed: {scorecards_processed}")
        print(f"Innings scores saved: {innings_saved_count}")
        print(f"Batting records saved: {batting_saved_count}")
        print(f"Bowling records saved: {bowling_saved_count}")
        print(
            f"Partnership records saved: "
            f"{partnerships_saved_count}"
        )
        print("==================================")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# =========================================================
# 4. RUN SCRIPT
# =========================================================

if __name__ == "__main__":
    try:
        save_matches()
    except Exception as error:
        print("Could not save matches:", error)
