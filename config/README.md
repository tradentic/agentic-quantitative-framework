# Configuration Artifacts

Centralised configuration for pipelines, agents, and services.

- `model/` holds training hyperparameters and encoder definitions.
- `features/` captures declarative feature recipes referenced by agents.
- `schedules/` defines cron expressions for Supabase Edge Functions.

All configuration files should be versioned YAML or JSON documents so that
agents can diff revisions and explain resulting plan changes.
