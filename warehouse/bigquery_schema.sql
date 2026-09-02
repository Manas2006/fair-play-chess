-- Thin analytical tables are appropriate for BigQuery's free tier; keep raw PGN and
-- high-volume move traces in compressed object storage / local Parquet.

CREATE TABLE IF NOT EXISTS fairplay.account_snapshots (
  snapshot_id STRING NOT NULL,
  account_id_hash STRING NOT NULL,
  as_of TIMESTAMP NOT NULL,
  window_games INT64 NOT NULL,
  rating_bucket INT64,
  dominant_speed STRING,
  engine_match_rate FLOAT64,
  hard_position_match_rate FLOAT64,
  cp_loss_median FLOAT64,
  move_time_cv FLOAT64,
  model_version STRING NOT NULL,
  calibrated_risk FLOAT64 NOT NULL
)
PARTITION BY DATE(as_of)
CLUSTER BY dominant_speed, rating_bucket;

CREATE TABLE IF NOT EXISTS fairplay.review_events (
  snapshot_id STRING NOT NULL,
  reviewed_at TIMESTAMP NOT NULL,
  decision STRING NOT NULL,
  reason_code STRING,
  reviewer_hash STRING,
  seconds_to_decision INT64
)
PARTITION BY DATE(reviewed_at)
CLUSTER BY decision;

-- Daily reviewer yield at each fixed capacity.
SELECT
  DATE(s.as_of) AS score_date,
  COUNT(*) AS reviewed,
  COUNTIF(r.decision = 'escalate') AS escalated,
  SAFE_DIVIDE(COUNTIF(r.decision = 'escalate'), COUNT(*)) AS reviewer_yield
FROM fairplay.account_snapshots s
JOIN fairplay.review_events r USING (snapshot_id)
GROUP BY score_date
ORDER BY score_date DESC;
