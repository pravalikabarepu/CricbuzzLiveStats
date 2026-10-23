USE cricbuzz_livestats;

SELECT COUNT(*) AS total_teams FROM teams;
SELECT COUNT(*) AS total_series FROM series;
SELECT COUNT(*) AS total_matches FROM matches;
USE cricbuzz_livestats;

SELECT COUNT(*) AS total_matches
FROM matches;
USE cricbuzz_livestats;

SELECT COUNT(*) AS total_teams
FROM teams;

SELECT *
FROM teams
LIMIT 10;
SELECT COUNT(*) AS total_teams
FROM teams;

SELECT team_id, team_name, team_short_name
FROM teams;

USE cricbuzz_livestats;

SELECT COUNT(*) AS total_innings
FROM innings_scores;
USE cricbuzz_livestats;

SELECT *
FROM innings_scores
LIMIT 10;
USE cricbuzz_livestats;

SELECT
    m.match_id,
    t.team_name,
    i.innings_number,
    i.runs,
    i.wickets,
    i.overs_text
FROM innings_scores i
JOIN matches m
    ON i.match_id = m.match_id
JOIN teams t
    ON i.team_id = t.team_id
ORDER BY m.match_id, i.innings_number
LIMIT 10;
show tables;

USE cricbuzz_livestats;

SELECT 'teams' AS table_name, COUNT(*) AS total_records FROM teams
UNION ALL
SELECT 'series', COUNT(*) FROM series
UNION ALL
SELECT 'venues', COUNT(*) FROM venues
UNION ALL
SELECT 'matches', COUNT(*) FROM matches
UNION ALL
SELECT 'innings_scores', COUNT(*) FROM innings_scores
UNION ALL
SELECT 'players', COUNT(*) FROM players
UNION ALL
SELECT 'batting_performance', COUNT(*) FROM batting_performance
UNION ALL
SELECT 'bowling_performance', COUNT(*) FROM bowling_performance
UNION ALL
SELECT 'partnerships', COUNT(*) FROM partnerships;


USE cricbuzz_livestats;

SELECT
    m.match_id,
    m.match_description,
    m.match_format,
    m.match_status,
    t1.team_name AS team1,
    t2.team_name AS team2
FROM matches m
LEFT JOIN teams t1 ON m.team1_id = t1.team_id
LEFT JOIN teams t2 ON m.team2_id = t2.team_id
ORDER BY m.match_id
LIMIT 10;


USE cricbuzz_livestats;

SELECT
    m.match_description,
    t.team_name,
    i.innings_number,
    i.runs,
    i.wickets,
    i.overs_text
FROM innings_scores i
JOIN matches m
    ON i.match_id = m.match_id
JOIN teams t
    ON i.team_id = t.team_id
ORDER BY i.runs DESC
LIMIT 10;


USE cricbuzz_livestats;

SELECT
    match_format,
    COUNT(*) AS total_matches
FROM matches
GROUP BY match_format
ORDER BY total_matches DESC;


USE cricbuzz_livestats;

SELECT
    match_status,
    COUNT(*) AS total_matches
FROM matches
GROUP BY match_status
ORDER BY total_matches DESC;


USE cricbuzz_livestats;

SELECT
    t.team_name,
    SUM(i.runs) AS total_runs
FROM innings_scores i
JOIN teams t
    ON i.team_id = t.team_id
GROUP BY t.team_id, t.team_name
ORDER BY total_runs DESC
LIMIT 10;


USE cricbuzz_livestats;

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
JOIN matches m
    ON i.match_id = m.match_id
JOIN teams t
    ON i.team_id = t.team_id
ORDER BY m.match_id DESC
LIMIT 15;


USE cricbuzz_livestats;

SELECT
    match_id,
    COUNT(*) AS record_count
FROM matches
GROUP BY match_id
HAVING COUNT(*) > 1;

USE cricbuzz_livestats;

SELECT COUNT(*) AS total_matches
FROM matches;

SELECT COUNT(*) AS total_innings
FROM innings_scores;

SELECT COUNT(*) AS total_matches
FROM matches;

USE cricbuzz_livestats;

DESCRIBE matches;
DESCRIBE batting_performance;
describe players;

SELECT
    p.player_name,
    b.match_id,
    b.innings_number,
    b.runs,
    b.balls_faced,
    b.fours,
    b.sixes,
    b.dismissal_type,
    b.not_out
FROM batting_performance b
JOIN players p
    ON b.player_id = p.player_id
ORDER BY b.runs DESC
LIMIT 10;
SELECT COUNT(*) AS total_batting_records
FROM batting_performance;
SELECT COUNT(*) AS total_players
FROM players;
DESCRIBE bowling_performance;
DESCRIBE partnerships;
USE cricbuzz_livestats;

SELECT team_id, team_name
FROM teams;
DESCRIBE players;
DESCRIBE batting_performance;
DESCRIBE bowling_performance;
describe matches;
DESCRIBE innings_scores;

USE cricbuzz_livestats;

SELECT 'Players' AS table_name, COUNT(*) AS total
FROM players

UNION ALL

SELECT 'Batting Performance', COUNT(*)
FROM batting_performance

UNION ALL

SELECT 'Bowling Performance', COUNT(*)
FROM bowling_performance;
USE cricbuzz_livestats;

SELECT
    (SELECT COUNT(*) FROM matches) AS total_matches,
    (SELECT COUNT(*) FROM innings_scores) AS total_innings,
    (SELECT COUNT(*) FROM players) AS total_players,
    (SELECT COUNT(*) FROM batting_performance) AS batting_records,
    (SELECT COUNT(*) FROM bowling_performance) AS bowling_records;
    DESCRIBE innings_scores;
    SHOW TABLES LIKE '%partnership%';
    DESCRIBE partnerships;
    SELECT COUNT(*) AS total_records,
       SUM(runs_scored) AS total_partnership_runs
FROM partnerships;
SHOW TABLES;
DESCRIBE batting_performance;
SELECT *
FROM batting_performance
LIMIT 5;
DESCRIBE innings_scores;
SELECT COUNT(*) AS total_partnerships
FROM partnerships;
SELECT COUNT(*) AS total_partnerships
FROM partnerships;

SELECT *
FROM partnerships
LIMIT 10;
   SELECT 'matches', COUNT(*) FROM matches
   UNION ALL SELECT 'innings_scores', COUNT(*) FROM innings_scores
   UNION ALL SELECT 'batting_performance', COUNT(*) FROM batting_performance
   UNION ALL SELECT 'bowling_performance', COUNT(*) FROM bowling_performance
   UNION ALL SELECT 'partnerships', COUNT(*) FROM partnerships;
      SELECT p.player_name, t.team_name AS bowling_for
   FROM bowling_performance b
   JOIN players p ON p.player_id = b.player_id
   LEFT JOIN teams t ON t.team_id = b.team_id
   WHERE b.match_id = 173040 LIMIT 10;
   SELECT match_id, innings_number, COUNT(*) FROM innings_scores
GROUP BY match_id, innings_number HAVING COUNT(*) > 1;

SELECT match_id, innings_number, player_id, COUNT(*) FROM batting_performance
GROUP BY match_id, innings_number, player_id HAVING COUNT(*) > 1;

SELECT match_id, innings_number, player_id, COUNT(*) FROM bowling_performance
GROUP BY match_id, innings_number, player_id HAVING COUNT(*) > 1;

SELECT match_id, innings_number, wicket_number, COUNT(*) FROM partnerships
GROUP BY match_id, innings_number, wicket_number HAVING COUNT(*) > 1;
  UPDATE bowling_performance b
  JOIN innings_scores i
    ON i.match_id = b.match_id AND i.innings_number = b.innings_number
  JOIN matches m ON m.match_id = b.match_id
  SET b.team_id = CASE
      WHEN i.team_id = m.team1_id THEN m.team2_id
      WHEN i.team_id = m.team2_id THEN m.team1_id
      ELSE b.team_id
  END;