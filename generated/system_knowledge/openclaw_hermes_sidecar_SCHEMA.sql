CREATE TABLE hermes_sidecar_run (
  run_ref TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  current_posture TEXT NOT NULL,
  active_steel_thread TEXT NOT NULL,
  recommended_next_package TEXT NOT NULL,
  recommended_model_class TEXT NOT NULL,
  confidence TEXT NOT NULL,
  guardian_required INTEGER NOT NULL CHECK(guardian_required IN (0, 1)),
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_source_ref (
  source_ref TEXT PRIMARY KEY,
  input_ref TEXT NOT NULL,
  path TEXT NOT NULL,
  status TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  required INTEGER NOT NULL CHECK(required IN (0, 1))
);

CREATE TABLE hermes_material_change (
  change_ref TEXT PRIMARY KEY,
  change_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_stale_surface (
  surface_ref TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_ref TEXT NOT NULL
);

CREATE TABLE hermes_authority_drift (
  drift_ref TEXT PRIMARY KEY,
  drift_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE hermes_do_not_touch (
  item_ref TEXT PRIMARY KEY,
  item TEXT NOT NULL,
  source_ref TEXT NOT NULL
);
