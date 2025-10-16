-- Trigger helpers for realtime notifications and timestamp management.

create or replace function public.touch_signal_embeddings_updated_at()
returns trigger
language plpgsql
as
$$
begin
    new.updated_at := timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists signal_embeddings_set_updated_at on public.signal_embeddings;
create trigger signal_embeddings_set_updated_at
    before update on public.signal_embeddings
    for each row execute function public.touch_signal_embeddings_updated_at();

create or replace function public.handle_signal_embedding_change()
returns trigger
language plpgsql
as
$$
begin
    perform pg_notify('embedding_ingested', row_to_json(new)::text);
    return new;
end;
$$;

drop trigger if exists signal_embeddings_notify on public.signal_embeddings;
create trigger signal_embeddings_notify
    after insert or update on public.signal_embeddings
    for each row execute function public.handle_signal_embedding_change();

create or replace function public.touch_embedding_jobs_updated_at()
returns trigger
language plpgsql
as
$$
begin
    new.updated_at := timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists embedding_jobs_set_updated_at on public.embedding_jobs;
create trigger embedding_jobs_set_updated_at
    before update on public.embedding_jobs
    for each row execute function public.touch_embedding_jobs_updated_at();
