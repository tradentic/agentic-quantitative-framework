---
title: ADR 0001 - Use Supabase for Local Stack
sidebar_position: 1
description: Supabase provides an all-in-one developer stack for local quantitative research.
---

## Status

Accepted

## Context

Developers need a reproducible environment that bundles Postgres, pgvector, file storage, authentication, and realtime triggers. Using separate services for each capability increases setup time and makes it harder for GPT-driven agents to interact with the system consistently across machines.

## Decision

Adopt the Supabase CLI local stack for development. The CLI provisions Postgres with pgvector, storage buckets, realtime servers, authentication, and logging in a single Docker compose profile. Agents and scripts can assume these services exist at predictable ports defined in `.devcontainer/devcontainer.json` and `.env` files.

## Consequences

- Local developers can bootstrap the environment with `supabase start` and immediately run LangGraph agents.
- Supabase migrations, triggers, and RPCs become the primary interface for automating workflows.
- Removing alternative local databases reduces maintenance overhead and ensures parity between local and hosted deployments.
