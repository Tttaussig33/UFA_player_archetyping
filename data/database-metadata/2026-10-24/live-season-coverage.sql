-- Executed read-only in the user's existing DBeaver session-pooler connection
-- on 2026-10-24. Results observed directly in the DBeaver result grid.
WITH throw_counts AS (
  SELECT "GameID", COUNT(*) AS throws
  FROM prod.throws
  GROUP BY "GameID"
)
SELECT g."Year" AS season,
       COUNT(*) AS listed_games,
       COUNT(t."GameID") AS games_with_throws,
       COALESCE(SUM(t.throws), 0)::bigint AS throws
FROM prod.games g
LEFT JOIN throw_counts t ON t."GameID" = g."GameID"
GROUP BY g."Year"
ORDER BY g."Year";
