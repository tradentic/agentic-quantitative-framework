# Local Development with Supabase CLI

This project is fully compatible with local-first development using the `supabase` CLI.

## Prerequisites
- Docker installed
- [Supabase CLI](https://supabase.com/docs/guides/cli) installed (`brew install supabase`)
- Python 3.10+, Poetry or virtualenv

## Setup Steps

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Initialize Supabase local
supabase init
supabase start

# Set up environment variables
cp .env.example .env
# Edit .env with your Supabase keys and project reference

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Supabase Services Used
- PostgreSQL (with pgvector extension)
- Storage (for raw data or model snapshots)
- Realtime (agent triggers, data event tracking)

## Vector DB Configuration
Use `supabase/vector_db/setup_pgvector.sql` to enable pgvector and initialize similarity tables.

