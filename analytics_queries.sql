
USE cricbuzz_livestats;

-- 1. Total matches
SELECT COUNT(*) AS total_matches
FROM matches;

-- 2. Total teams
SELECT COUNT(*) AS total_teams
FROM teams;

-- 3. Matches by format
SELECT match_format, COUNT(*) AS total_matches
FROM matches
GROUP BY match_format
ORDER BY total_matches DESC;

-- 4. Matches by status
SELECT match_status, COUNT(*) AS total_matches
FROM matches
GROUP BY match_status
ORDER BY total_matches DESC;

-- 5. Match details with team names
SELECT
    m.match_id,
    m.match_description,
    t1.team_name AS team1,
    t2.team_name AS team2,
    m.match_status
FROM matches m
LEFT JOIN teams t1 ON m.team1_id = t1.team_id
LEFT JOIN teams t2 ON m.team2_id = t2.team_id;

-- 6. Highest-scoring innings
SELECT
    m.match_description,
    t.team_name,
    i.innings_number,
    i.runs,
    i.wickets,
    i.overs_text
FROM innings_scores i
JOIN matches m ON i.match_id = m.match_id
JOIN teams t ON i.team_id = t.team_id
ORDER BY i.runs DESC
LIMIT 10;

-- 7. Total recorded innings runs by team
SELECT
    t.team_name,
    SUM(i.runs) AS total_runs
FROM innings_scores i
JOIN teams t ON i.team_id = t.team_id
GROUP BY t.team_id, t.team_name
ORDER BY total_runs DESC
LIMIT 10;

-- 8. Innings scores with match status
SELECT
    m.match_id,
    m.match_description,
    t.team_name,
    i.innings_number,
    i.runs,
    i.wickets,
    i.overs_text,
    m.match_status
FROM innings_scores i
JOIN matches m ON i.match_id = m.match_id
JOIN teams t ON i.team_id = t.team_id
ORDER BY m.match_id DESC
LIMIT 15;

-- 9. Check for duplicate match IDs
SELECT match_id, COUNT(*) AS record_count
FROM matches
GROUP BY match_id
HAVING COUNT(*) > 1;

-- 10. Count stored innings records
SELECT COUNT(*) AS total_innings_records
FROM innings_scores;
