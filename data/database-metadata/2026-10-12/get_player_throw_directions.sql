CREATE OR REPLACE FUNCTION prod.get_player_throw_directions(p_player_id text, p_year integer DEFAULT NULL::integer, p_bucket_count integer DEFAULT 12)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
AS $function$
DECLARE
  v_bucket_count integer;
  v_step numeric;
  v_result jsonb;
BEGIN
  -- Normalize bucket count (4-36)
  v_bucket_count := GREATEST(4, LEAST(p_bucket_count, 36));
  v_step := 360.0::numeric / v_bucket_count;

  WITH all_throws AS (
    SELECT
      t.throw_angle::numeric AS throw_angle,
      CASE WHEN t."Thrower" = p_player_id THEN 1 ELSE 0 END AS is_thrower,
      CASE WHEN t."Receiver" = p_player_id THEN 1 ELSE 0 END AS is_receiver
    FROM prod.throws t
    WHERE (t."Thrower" = p_player_id OR t."Receiver" = p_player_id)
      AND (
        p_year IS NULL
        OR LEFT(t."GameID"::text, 4)::int = p_year
      )
      AND t.throw_angle IS NOT NULL
  ),
  bucketed AS (
    SELECT
      FLOOR(
        (
          (
            ((throw_angle % 360::numeric) + 360::numeric) % 360::numeric
          ) / v_step
        )
      )::integer AS bucket_idx,
      SUM(is_thrower) AS thrower_count,
      SUM(is_receiver) AS receiver_count
    FROM all_throws
    GROUP BY bucket_idx
  ),
  bucket_range AS (
    SELECT generate_series(0, v_bucket_count - 1) AS bucket_idx
  ),
  bucket_data AS (
    SELECT
      br.bucket_idx,
      ROUND((br.bucket_idx * v_step))::text || '°' AS label,
      (br.bucket_idx * v_step) AS center_angle,
      COALESCE(b.thrower_count, 0)::integer AS thrower_count,
      COALESCE(b.receiver_count, 0)::integer AS receiver_count
    FROM bucket_range br
    LEFT JOIN bucketed b ON b.bucket_idx = br.bucket_idx
    ORDER BY br.bucket_idx
  ),
  totals AS (
    SELECT
      SUM(is_thrower)::integer AS total_thrower,
      SUM(is_receiver)::integer AS total_receiver
    FROM all_throws
  )
  SELECT jsonb_build_object(
    'buckets', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'label', label,
          'centerAngle', center_angle,
          'throwerCount', thrower_count,
          'receiverCount', receiver_count
        )
        ORDER BY bucket_idx
      )
      FROM bucket_data
    ),
    'totalThrowsAsThrower', COALESCE((SELECT total_thrower FROM totals), 0),
    'totalThrowsAsReceiver', COALESCE((SELECT total_receiver FROM totals), 0)
  ) INTO v_result;

  RETURN v_result;
END;
$function$

