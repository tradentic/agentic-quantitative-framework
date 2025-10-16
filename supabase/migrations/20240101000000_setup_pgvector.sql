-- Enable extensions required for pgvector workflows.
create extension if not exists vector;
create extension if not exists pgcrypto;
create extension if not exists btree_gist;
