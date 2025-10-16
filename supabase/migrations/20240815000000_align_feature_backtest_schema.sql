-- Align feature_registry and backtest_results schema with project specifications.

-- Rename feature registry identifiers and metadata fields.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'feature_registry'
          AND column_name = 'feature_id'
    ) THEN
        ALTER TABLE public.feature_registry
            RENAME COLUMN feature_id TO id;
    END IF;
END$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'feature_registry'
          AND column_name = 'file_path'
    ) THEN
        ALTER TABLE public.feature_registry
            RENAME COLUMN file_path TO path;
    END IF;
END$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'feature_registry'
          AND column_name = 'metadata'
    ) THEN
        ALTER TABLE public.feature_registry
            RENAME COLUMN metadata TO meta;
    END IF;
END$$;

ALTER TABLE public.feature_registry
    ALTER COLUMN path SET NOT NULL;

ALTER TABLE public.feature_registry
    ALTER COLUMN meta SET DEFAULT '{}'::jsonb;

-- Ensure backtest_results uses jsonb artifacts and embeds strategy metadata.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'backtest_results'
          AND column_name = 'strategy_id'
    ) THEN
        UPDATE public.backtest_results
        SET config = jsonb_set(
            COALESCE(config, '{}'::jsonb),
            '{strategy_id}',
            to_jsonb(strategy_id),
            true
        )
        WHERE strategy_id IS NOT NULL
          AND (config->>'strategy_id') IS NULL;
    END IF;
END$$;

ALTER TABLE public.backtest_results
    ADD COLUMN IF NOT EXISTS artifacts jsonb DEFAULT '{}'::jsonb;

UPDATE public.backtest_results
SET artifacts = COALESCE(artifacts, '{}'::jsonb) || jsonb_build_object('legacy_path', artifacts_path)
WHERE artifacts_path IS NOT NULL;

ALTER TABLE public.backtest_results
    ALTER COLUMN artifacts SET DEFAULT '{}'::jsonb,
    ALTER COLUMN artifacts SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = 'backtest_results_strategy_idx'
    ) THEN
        DROP INDEX public.backtest_results_strategy_idx;
    END IF;
END$$;

ALTER TABLE public.backtest_results
    DROP COLUMN IF EXISTS artifacts_path,
    DROP COLUMN IF EXISTS strategy_id,
    DROP COLUMN IF EXISTS run_at;
