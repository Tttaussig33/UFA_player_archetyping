-- Read-only queries executed in the user's existing DBeaver connection,
-- November 20, 2026 (America/New_York). Results transcribed in the receipt.
-- Do not execute stored functions or change privileges to bypass denied access.

SELECT table_schema, table_name,
       string_agg(column_name, ', ' ORDER BY ordinal_position) AS relevant_columns
FROM information_schema.columns
WHERE table_schema IN ('prod','dd_metrics','public')
  AND (column_name ~* '(^cp$|cpoe|model|train|fold|predict|complet|drop)'
       OR table_name ~* '(model|train|predict)')
GROUP BY table_schema, table_name ORDER BY table_schema, table_name;

SELECT n.nspname AS schema, c.relname AS relation, a.attname AS column,
       has_table_privilege(c.oid,'SELECT') AS readable
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE a.attnum>0 AND NOT a.attisdropped
  AND n.nspname IN ('prod','dd_metrics','public')
  AND (a.attname ~* '(model|train|fold|prediction)'
       OR c.relname ~* '(model|train|prediction)')
ORDER BY 1,2,3;

SELECT n.nspname AS schema, p.proname AS function, p.prokind AS kind
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname IN ('prod','dd_metrics','public')
  AND p.proname ~* '(cp|complet|metric|model|predict|stats|throw)'
ORDER BY 1,2;

SELECT n.nspname||'.'||c.relname AS relation, a.attname AS field,
       format_type(a.atttypid,a.atttypmod) AS type,
       col_description(c.oid,a.attnum) AS note
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
WHERE a.attnum>0 AND NOT a.attisdropped AND
 ((n.nspname='public' AND c.relname='model_files') OR
  (n.nspname='prod' AND c.relname='throws' AND a.attname IN ('cp','cpoe','DroppedThrow')) OR
  (n.nspname='dd_metrics' AND c.relname='throws' AND a.attname='model_version'))
ORDER BY 1,a.attnum;

SELECT 'player_stats_game field' AS item, column_name AS value
FROM information_schema.columns
WHERE table_schema='prod' AND table_name='player_stats_game'
  AND column_name ~* '(complet|drop|cpoe)'
UNION ALL SELECT 'model filename readable', has_column_privilege('public.model_files','filename','SELECT')::text
UNION ALL SELECT 'model binary readable', has_column_privilege('public.model_files','file_data','SELECT')::text;

SELECT count(*) AS rows_2026,
 count(*) FILTER (WHERE "ThrowAttempts">throws_dropped) AS comparable,
 count(*) FILTER (WHERE "ThrowAttempts">throws_dropped
   AND abs(completion_percentage-"Completions"/NULLIF("ThrowAttempts"-throws_dropped,0))<1e-8) AS omit_matches,
 count(*) FILTER (WHERE throws_dropped>0 AND "ThrowAttempts">throws_dropped) AS drop_groups,
 count(*) FILTER (WHERE throws_dropped>0 AND "ThrowAttempts">throws_dropped
   AND abs(completion_percentage-"Completions"/NULLIF("ThrowAttempts"-throws_dropped,0))<1e-8) AS drop_matches
FROM prod.player_stats_game WHERE left("GameID",4)='2026';

SELECT left("GameID",4) AS season, count(*) AS rows,
       count(DISTINCT "GameID") AS games,
       count(*) FILTER (WHERE cp IS NULL) AS missing_cp
FROM prod.throws GROUP BY 1 ORDER BY 1;
