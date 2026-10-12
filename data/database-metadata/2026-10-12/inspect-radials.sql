-- Read-only example: Alex Atkins, 2026, 12 direction buckets.
SELECT prod.get_player_throw_directions('aatkins', 2026, 12);

-- Read the installed function definition without changing it.
SELECT pg_get_functiondef(
  'prod.get_player_throw_directions(text,integer,integer)'::regprocedure
);
