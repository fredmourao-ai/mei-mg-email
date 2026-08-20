-- Callback pre-migration recuperado da producao em 2026-08-13.
--
-- A V019 historica depende destes objetos. Eles ja existiam na producao antes
-- da V019 e nao podem ser introduzidos alterando migrations versionadas ja
-- aplicadas. Como este callback fica na location padrao de migrations, Flyway
-- 10.x o descobre sem depender de callbackLocations separado.
--
-- Fail closed para historico Flyway divergente: se artefatos inequivocamente
-- posteriores ja existem, mas o schema history diz que a versao ainda nao foi
-- aplicada, nao podemos deixar o Flyway reproduzir migrations historicas de
-- autorizacao (V021-V023). A reconciliacao precisa ser explicita e auditada.
do $flyway_history_guard$
declare
  v_max integer;
begin
  if to_regclass('mei_email.flyway_schema_history') is not null then
    select max(
      case when version ~ '^[0-9]+$' then version::integer else null end
    )
      into v_max
      from mei_email.flyway_schema_history
     where success;

    if v_max is not null and (
         (v_max < 31 and to_regclass('mei_email.envios_externos_cota') is not null)
         or
         (v_max < 34 and to_regprocedure('mei_email.guard_uncertain_graph_dispatch_replay()') is not null)
       )
    then
      raise exception using
        errcode = 'P0001',
        message = format(
          'FLYWAY_HISTORY_DIVERGENCE: max_history=%s but later migration artifacts already exist; refusing to replay V021-V023 authorization migrations',
          v_max
        );
    end if;
  end if;
end
$flyway_history_guard$;

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
