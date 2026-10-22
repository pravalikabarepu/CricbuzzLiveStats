
from cricbuzz_api import get_live_matches


def load_live_matches():
    data = get_live_matches()

    matches = []

    for type_match in data.get("typeMatches", []):
        for series_match in type_match.get("seriesMatches", []):
            series_wrapper = series_match.get("seriesAdWrapper", {})

            for match in series_wrapper.get("matches", []):
                match_info = match.get("matchInfo", {})
                match_score = match.get("matchScore", {})

                matches.append({
                    "match_id": match_info.get("matchId"),
                    "series_name": match_info.get("seriesName"),
                    "match_description": match_info.get("matchDesc"),
                    "match_format": match_info.get("matchFormat"),
                    "state": match_info.get("state"),
                    "status": match_info.get("status"),
                    "team1": match_info.get("team1", {}).get("teamName"),
                    "team2": match_info.get("team2", {}).get("teamName"),
                    "venue": match_info.get("venueInfo", {}).get("ground"),
                    "score": match_score,
                })

    return matches


if __name__ == "__main__":
    try:
        matches = load_live_matches()
        print(f"Matches retrieved: {len(matches)}")

        for match in matches:
            print("-" * 40)
            print("Match ID:", match["match_id"])
            print("Teams:", match["team1"], "vs", match["team2"])
            print("Status:", match["status"])
            print("Score:", match["score"])

    except Exception as error:
        print("Failed to load matches:", error)
