import time

import requests

from config import RAPIDAPI_HOST, RAPIDAPI_KEY

BASE_URL = f"https://{RAPIDAPI_HOST}"

_session = requests.Session()
_session.headers.update({
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
})


class CricbuzzAPIError(RuntimeError):
    """Raised for any failed Cricbuzz API call (never includes the API key)."""


# =========================================================
# HTTP
# =========================================================

def _get(path, retries=2):
    if not RAPIDAPI_KEY:
        raise CricbuzzAPIError("RAPIDAPI_KEY is not configured.")

    url = f"{BASE_URL}{path}"

    for attempt in range(retries + 1):
        try:
            response = _session.get(url, timeout=30)
        except requests.RequestException as error:
            if attempt == retries:
                raise CricbuzzAPIError(
                    f"Request failed: {type(error).__name__}"
                ) from error
            time.sleep(2 ** attempt)
            continue

        if response.status_code in (401, 403):
            raise CricbuzzAPIError(
                "API key rejected, or your plan does not include this endpoint."
            )

        # Rate limit or temporary server error: back off and retry.
        if (response.status_code == 429 or response.status_code >= 500) \
                and attempt < retries:
            time.sleep(2 ** attempt)
            continue

        try:
            response.raise_for_status()
            return response.json()
        except (requests.HTTPError, ValueError) as error:
            raise CricbuzzAPIError(
                f"Bad response from API (status {response.status_code})."
            ) from error


def get_live_matches():
    """Fetch live matches from Cricbuzz."""
    return _get("/matches/v1/live")


def get_match_scorecard(match_id):
    """Fetch a match scorecard from Cricbuzz."""
    try:
        safe_id = int(match_id)
    except (TypeError, ValueError):
        raise CricbuzzAPIError("match_id must be a number.") from None
    return _get(f"/mcenter/v1/{safe_id}/scard")


# =========================================================
# Parsing helpers (tolerate lowercase or camelCase keys)
# =========================================================

def pick(data, *names, default=None):
    """Case-insensitive dict lookup returning the first non-null match."""
    if not isinstance(data, dict):
        return default
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return default


def iter_matches(data):
    """Yield every match dict from typeMatches > seriesMatches > matches."""
    for type_match in (pick(data, "typeMatches") or []):
        for series_match in (pick(type_match, "seriesMatches") or []):
            wrapper = pick(series_match, "seriesAdWrapper") or {}
            for match in (pick(wrapper, "matches") or []):
                yield match


def get_innings_list(scorecard):
    return pick(scorecard, "scoreCard", "scorecard", default=[]) or []


def get_batting_team(innings):
    details = pick(innings, "batTeamDetails")
    if isinstance(details, dict):
        return pick(details, "batTeamName")
    return pick(innings, "batTeamName")


def get_partnerships(innings):
    """Return a list of partnership dicts for either response format."""
    new_style = pick(innings, "partnershipsData")
    if isinstance(new_style, dict):
        return list(new_style.values())

    old_style = pick(innings, "partnership")
    if isinstance(old_style, dict):
        return pick(old_style, "partnership", default=[]) or []
    if isinstance(old_style, list):
        return old_style

    return []


# =========================================================
# Quick manual test
# =========================================================

if __name__ == "__main__":
    try:
        data = get_live_matches()
        print("Live matches API connected successfully!")

        match_id = None
        for match in iter_matches(data):
            match_id = pick(pick(match, "matchInfo") or {}, "matchId")
            if match_id:
                break

        if not match_id:
            print("No live match ID found.")
        else:
            scorecard = get_match_scorecard(match_id)
            print("Scorecard API connected successfully!")
            print("Match ID:", match_id)
            print("Response keys:", list(scorecard.keys()))

            for innings in get_innings_list(scorecard):
                print("\nInnings keys:", list(innings.keys()))
                print("Innings ID:", pick(innings, "inningsId"))
                print("Batting team:", get_batting_team(innings))

                partnerships = get_partnerships(innings)
                print("Partnership count:", len(partnerships))

                for p in partnerships[:3]:
                    print({
                        "player1": pick(p, "bat1Name"),
                        "player2": pick(p, "bat2Name"),
                        "runs": pick(p, "totalRuns"),
                        "balls": pick(p, "totalBalls"),
                    })

    except CricbuzzAPIError as error:
        print("API error:", error)