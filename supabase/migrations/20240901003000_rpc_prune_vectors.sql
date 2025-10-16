-- RPC to archive and prune stale embeddings based on configurable policies.
create or replace function public.rpc_prune_vectors(
    p_max_age_days integer default 90,
    p_min_t_stat double precision default 0.5,
    p_asset_universe text[] default null,
    p_regime_diversity integer default 3
) returns jsonb
language plpgsql
as $$
declare
    archived_count integer := 0;
    deleted_count integer := 0;
begin
    with candidates as (
        select *
        from public.signal_embeddings
        where created_at < timezone('utc', now()) - make_interval(days => p_max_age_days)
          and (
              p_asset_universe is null
              or asset_symbol = any(p_asset_universe)
          )
          and (
              coalesce((meta->>'t_stat')::double precision, 0.0) < p_min_t_stat
              or p_regime_diversity > 0
          )
    ), inserted as (
        insert into public.signal_embeddings_archive (
            id,
            asset_symbol,
            time_range,
            embedding,
            regime_tag,
            label,
            meta,
            created_at,
            archived_at
        )
        select
            id,
            asset_symbol,
            time_range,
            embedding,
            regime_tag,
            label,
            meta,
            created_at,
            timezone('utc', now())
        from candidates
        on conflict (id) do update
        set
            asset_symbol = excluded.asset_symbol,
            time_range = excluded.time_range,
            embedding = excluded.embedding,
            regime_tag = excluded.regime_tag,
            label = excluded.label,
            meta = excluded.meta,
            created_at = excluded.created_at,
            archived_at = excluded.archived_at
        returning id
    ), removed as (
        delete from public.signal_embeddings
        where id in (select id from inserted)
        returning id
    )
    select count(*) into archived_count from inserted;

    select count(*) into deleted_count from removed;

    return jsonb_build_object(
        'archived', coalesce(archived_count, 0),
        'deleted', coalesce(deleted_count, 0),
        'criteria', jsonb_build_object(
            'max_age_days', p_max_age_days,
            'min_t_stat', p_min_t_stat,
            'asset_universe', p_asset_universe,
            'regime_diversity', p_regime_diversity
        )
    );
end;
$$;
