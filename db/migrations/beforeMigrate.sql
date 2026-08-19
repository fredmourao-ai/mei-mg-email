-- Callback pre-migration recuperado da producao em 2026-08-13.
--
-- A V019 historica depende destes objetos. Eles ja existiam na producao antes
-- da V019 e nao podem ser introduzidos alterando migrations versionadas ja
-- aplicadas. Como este callback fica na location padrao de migrations, Flyway
-- 10.x o descobre sem depender de callbackLocations separado.

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

-- IMPORTANTE: manter a comparacao direta em CITEXT. Aplicar lower/btrim sobre
-- s.value desabilita o uso efetivo de idx_email_suppressions_lookup e pode
-- transformar a elegibilidade em varredura ampla. O parametro e normalizado
-- uma unica vez; value ja e CITEXT e e gravado normalizado.
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
         (s.scope = 'email'
          and s.value = lower(btrim(p_email::text))::public.citext)
         or
         (s.scope = 'domain'
          and s.value = split_part(lower(btrim(p_email::text)), '@', 2)::public.citext)
       )
  );
$function$;
