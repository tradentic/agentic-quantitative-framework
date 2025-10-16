-- RPC to bulk refresh embeddings from JSON payloads produced by agents or flows.
create or replace function public.rpc_refresh_embeddings(
    p_asset_symbol text,
    p_embeddings jsonb default '[]'::jsonb
) returns jsonb
language plpgsql
as $$
declare
    upserted integer := 0;
begin
    if p_asset_symbol is null or length(p_asset_symbol) = 0 then
        raise exception 'rpc_refresh_embeddings requires p_asset_symbol';
    end if;

    if p_embeddings is null then
        p_embeddings := '[]'::jsonb;
    end if;

    with normalized as (
        select
            coalesce((value->>'id')::uuid, gen_random_uuid()) as id,
            coalesce(nullif(value->>'asset_symbol', ''), p_asset_symbol) as asset_symbol,
            coalesce(value->>'time_range', '[1970-01-01T00:00:00Z,1970-01-02T00:00:00Z)') as time_range,
            coalesce(value->>'regime_tag', null) as regime_tag,
            coalesce(value->'label', '{}'::jsonb) as label,
            coalesce(value->'meta', '{}'::jsonb) as meta,
            case
                when value ? 'embedding_literal' then (value->>'embedding_literal')::vector(128)
                when value ? 'embedding' then (
                    select array_agg((embedding_value)::double precision)
                    from jsonb_array_elements_text(value->'embedding') as embedding_value
                )::vector(128)
                else null
            end as embedding_value
        from jsonb_array_elements(p_embeddings) as value
    ),
    upsert as (
        insert into public.signal_embeddings (
            id,
            asset_symbol,
            time_range,
            embedding,
            regime_tag,
            label,
            meta,
            updated_at
        )
        select
            id,
            asset_symbol,
            time_range,
            embedding_value,
            regime_tag,
            label,
            meta,
            timezone('utc', now())
        from normalized
        where embedding_value is not null
        on conflict (id) do update
        set
            asset_symbol = excluded.asset_symbol,
            time_range = excluded.time_range,
            embedding = excluded.embedding,
            regime_tag = excluded.regime_tag,
            label = excluded.label,
            meta = excluded.meta,
            updated_at = timezone('utc', now())
        returning 1
    )
    select count(*) into upserted from upsert;

    return jsonb_build_object(
        'asset_symbol', p_asset_symbol,
        'rows', coalesce(upserted, 0)
    );
end;
$$;
