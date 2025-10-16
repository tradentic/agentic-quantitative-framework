---
title: ADR 0002 - Use Supabase as Vector DB
sidebar_position: 2
description: Supabase pgvector replaces standalone vector databases for signal retrieval.
---

## Status

Accepted

## Context

Financial signal discovery requires fast similarity search with tight integration to metadata, triggers, and storage. External services like Pinecone or FAISS introduce additional infrastructure, credential management, and synchronization burdens between vector data and relational metadata.

## Decision

Use the `signal_embeddings` table in Supabase Postgres with the pgvector extension as the canonical vector store. Embeddings are inserted via the Supabase REST client, and RPC functions manage pruning, refreshing, and similarity searches.

## Consequences

- LangGraph tools can rely on a single Supabase client for relational queries, vector operations, and storage interactions.
- Triggers and realtime channels operate on the same database that holds embeddings, simplifying event-driven automation.
- The team avoids maintaining external vector DBs while retaining the ability to scale pgvector with indexes and partitioning.
