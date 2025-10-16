-- Ensure signal_fingerprints.fingerprint retains the canonical vector(128) shape.
alter table if exists public.signal_fingerprints
    alter column fingerprint type vector(128),
    alter column fingerprint set not null;
