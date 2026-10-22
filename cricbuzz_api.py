
import requests
from config import RAPIDAPI_KEY, RAPIDAPI_HOST


def get_live_matches():
    """Fetch live matches from Cricbuzz."""
    url = f"https://{RAPIDAPI_HOST}/matches/v1/live"

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def get_match_scorecard(match_id):
    """Fetch a match scorecard from Cricbuzz."""
    url = f"https://{RAPIDAPI_HOST}/mcenter/v1/{match_id}/scard"

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    if not RAPIDAPI_KEY:
        print("Error: RAPIDAPI_KEY is not configured.")
    else:
        try:
            data = get_live_matches()
            print("Live matches API connected successfully!")

            match_id = None

            for type_match in data.get("typeMatches", []):
                for series_match in type_match.get("seriesMatches", []):
                    wrapper = series_match.get("seriesAdWrapper", {})

                    for match in wrapper.get("matches", []):
                        match_info = match.get("matchInfo") or {}
                        match_id = match_info.get("matchId")

                        if match_id:
                            break

                    if match_id:
                        break

                if match_id:
                    break

            if not match_id:
                print("No live match ID found.")
            else:
                scorecard = get_match_scorecard(match_id)

                print("Scorecard API connected successfully!")
                print("Match ID:", match_id)
                print("Response keys:", list(scorecard.keys()))

                for innings in scorecard.get("scorecard", []):
                    print("\nInnings keys:", list(innings.keys()))
                    print("Innings ID:", innings.get("inningsid"))
                    print("Batting team:", innings.get("batteamname"))

                    partnership_data = innings.get("partnership") or {}
                    partnerships = partnership_data.get("partnership", [])

                    print("Partnership count:", len(partnerships))

                    for partnership in partnerships[:3]:
                        print({
                            "player1": partnership.get("bat1name"),
                            "player2": partnership.get("bat2name"),
                            "runs": partnership.get("totalruns"),
                            "balls": partnership.get("totalballs")
                        })

        except requests.RequestException as error:
            print("API request failed:", error)
