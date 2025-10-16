-- RPC that archives low-utility vectors into `signal_embeddings_archive`.

create or replace function public.rpc_prune_vectors(
    max_age_days integer default 90,
    min_t_stat numeric default 0.5,
    regime_diversity integer default 3,
    asset_universe text[] default null
)
returns jsonb
language plpgsql
as
$$
declare
    cutoff timestamptz := timezone('utc', now()) - make_interval(days => max_age_days);
    moved_count integer := 0;
    archived_ids uuid[];
begin
    with candidates as (
        select se.*
        from public.signal_embeddings se
        where (se.meta->>'t_stat')::numeric < min_t_stat
           or se.created_at < cutoff
           or (se.meta->>'regime_count')::integer < regime_diversity
           or (asset_universe is not null and se.asset_symbol <> all(asset_universe))
    ), moved as (
        insert into public.signal_embeddings_archive (id, asset_symbol, time_range, embedding, regime_tag, label, meta)
        select id, asset_symbol, time_range, embedding, regime_tag, label, meta from candidates
        on conflict (id) do nothing
        returning id
    )
    select coalesce(array_agg(id), array[]::uuid[]) into archived_ids from moved;

    if array_length(archived_ids, 1) is not null then
        delete from public.signal_embeddings where id = any(archived_ids);
    end if;

    moved_count := coalesce(array_length(archived_ids, 1), 0);
    return jsonb_build_object('archived', moved_count, 'ids', archived_ids);
end;
$$;
