-- Execute manualmente no banco de relatórios antes de ativar REPORT_DB_ENABLED.
-- Para usar outro schema, ajuste este arquivo e REPORT_DB_SCHEMA igualmente.
CREATE SCHEMA IF NOT EXISTS qa_reports;

CREATE TABLE IF NOT EXISTS qa_reports.qa_test_runs (
    id uuid PRIMARY KEY,
    project text NOT NULL CHECK (project IN ('early', 'after')),
    environment text NOT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL,
    duration_ms bigint NOT NULL CHECK (duration_ms >= 0),
    status text NOT NULL CHECK (status IN ('passed', 'failed')),
    exit_code integer NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_reports.qa_test_scenarios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES qa_reports.qa_test_runs(id),
    test_node_id text,
    test_name text NOT NULL,
    title text NOT NULL,
    bdd text,
    duration_ms bigint CHECK (duration_ms >= 0),
    pytest_status text CHECK (pytest_status IN ('passed', 'failed', 'skipped', 'error'))
);

CREATE TABLE IF NOT EXISTS qa_reports.qa_test_results (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id bigint NOT NULL REFERENCES qa_reports.qa_test_scenarios(id),
    scope_type text NOT NULL CHECK (scope_type IN ('client', 'environment', 'infrastructure')),
    client_id text,
    scope_label text NOT NULL,
    validation_type text NOT NULL,
    status text NOT NULL CHECK (status IN ('passed', 'failed', 'info')),
    message text NOT NULL,
    raw_message text NOT NULL,
    sequence integer NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scenario_id, sequence)
);

CREATE INDEX IF NOT EXISTS qa_test_runs_filter_idx ON qa_reports.qa_test_runs (project, environment, started_at DESC);
CREATE INDEX IF NOT EXISTS qa_test_scenarios_run_idx ON qa_reports.qa_test_scenarios (run_id, test_name);
CREATE INDEX IF NOT EXISTS qa_test_results_filter_idx ON qa_reports.qa_test_results (scenario_id, validation_type, status, client_id);
