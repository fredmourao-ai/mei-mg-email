-- Bootstrap pre-Flyway recuperado da producao em 2026-08-13.
--
-- Estes objetos existiam antes da V019 historica e, por isso, nao podem ser
-- introduzidos alterando uma migration versionada ja aplicada. Em bancos novos,
-- docker-entrypoint-initdb.d executa este arquivo antes do Flyway. Em bancos
-- existentes, o script de init do PostgreSQL nao e reexecutado.

create table if not exists mei_email.email_suppressions (
    id uuid default gen_random_uuid() not null,
    scope text not null,
    value public.citext not null,
    reason text not null,
    source text default 'manual'::text not null,
    source_ref text,
    ndr_code text,
    ndr_reason text,
    active boolean default true not null,
    reactivate_after timestamp with time zone,
    created_at timestamp with time zone default now() not null,
    updated_at timestamp with time zone default now() not null,
    constraint email_suppressions_pkey primary key (id),
    constraint email_suppressions_scope_check check (scope = any (array['email'::text, 'domain'::text]))
);

create index if not exists idx_email_suppressions_lookup
    on mei_email.email_suppressions using btree (active, scope, value);

create unique index if not exists uq_email_suppressions_active_scope_value
    on mei_email.email_suppressions using btree (scope, value)
    where active = true;

create or replace function mei_email.is_email_suppressed(p_email public.citext)
returns boolean
language sql
stable
as $function$
  select exists(
    select 1
      from mei_email.email_suppressions s
     where s.active
       and (
         (s.scope = 'email' and lower(btrim(s.value::text)) = lower(btrim(p_email::text)))
         or
         (s.scope = 'domain' and lower(btrim(s.value::text)) = split_part(lower(btrim(p_email::text)), '@', 2))
       )
  );
$function$;
