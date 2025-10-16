-- Maintain updated_at stamps and lightweight audit trails for embeddings.
create or replace function public.trg_signal_embeddings_touch()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists trg_signal_embeddings_touch on public.signal_embeddings;
create trigger trg_signal_embeddings_touch
before update on public.signal_embeddings
for each row execute function public.trg_signal_embeddings_touch();

create or replace function public.trg_signal_embeddings_audit()
returns trigger
language plpgsql
as $$
declare
    summary jsonb;
begin
    summary := jsonb_build_object(
        'last_embedding_id', new.id,
        'asset_symbol', new.asset_symbol,
        'time_range', new.time_range,
        'event_at', timezone('utc', now())
    );

    insert into public.agent_state (agent_id, state, updated_at)
    values (
        'vector-ingestion',
        jsonb_build_object('last_event', summary),
        timezone('utc', now())
    )
    on conflict (agent_id) do update
    set
        state = coalesce(public.agent_state.state, '{}'::jsonb) || jsonb_build_object('last_event', summary),
        updated_at = excluded.updated_at;

    return new;
end;
$$;

drop trigger if exists trg_signal_embeddings_audit on public.signal_embeddings;
create trigger trg_signal_embeddings_audit
after insert or update on public.signal_embeddings
for each row execute function public.trg_signal_embeddings_audit();
