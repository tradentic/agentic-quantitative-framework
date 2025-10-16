# Local Development with Supabase CLI

This project is fully compatible with local-first development using the `supabase` CLI.

## Prerequisites
- Docker installed
- [Supabase CLI](https://supabase.com/docs/guides/cli) (`brew install supabase`)
- Python 3.11+
- Node.js 24+
- Poetry or pip for Python dependency management

## Setup Steps

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Initialize Supabase local
supabase init
supabase start

# Apply database schema and RPC helpers
supabase db push
supabase db execute --file supabase/sql/signal_embedding_triggers.sql

# Set up environment variables
cp .env.example .env
# Edit .env with your Supabase keys and project reference

# Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Supabase Services Used
- PostgreSQL (with pgvector extension)
- Storage (for raw data or model snapshots)
- Realtime (agent triggers, data event tracking)

## Vector DB Configuration
Use `supabase/sql/signal_embedding_triggers.sql` as a starting point for enabling pgvector and registering automation triggers.

