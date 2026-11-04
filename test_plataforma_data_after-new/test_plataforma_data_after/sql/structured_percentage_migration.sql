-- Executar uma vez no banco de relatórios, antes de ativar a gravação dos novos campos.
-- Se REPORT_DB_SCHEMA for diferente de qa_reports, ajuste o schema abaixo.
BEGIN;

ALTER TABLE qa_reports.qa_test_results
    ADD COLUMN IF NOT EXISTS index_name text,
    ADD COLUMN IF NOT EXISTS index_type text,
    ADD COLUMN IF NOT EXISTS attribute_name text,
    ADD COLUMN IF NOT EXISTS previous_value numeric,
    ADD COLUMN IF NOT EXISTS current_value numeric,
    ADD COLUMN IF NOT EXISTS variation_percent numeric,
    ADD COLUMN IF NOT EXISTS comparison_direction text,
    ADD COLUMN IF NOT EXISTS comparison_limit_percent numeric,
    ADD COLUMN IF NOT EXISTS max_increase_percent numeric,
    ADD COLUMN IF NOT EXISTS max_decrease_percent numeric,
    ADD COLUMN IF NOT EXISTS previous_date date,
    ADD COLUMN IF NOT EXISTS current_date date,
    ADD COLUMN IF NOT EXISTS reason_code text;

COMMIT;
