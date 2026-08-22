-- V039: corrige regressao introduzida pelo callback beforeMigrate.
--
-- O callback historico recriava is_email_suppressed() aplicando lower/btrim
-- sobre email_suppressions.value. Isso impede o lookup direto pelos indices
-- (active, scope, value) e pode fazer a contagem de elegibilidade exceder o
-- statement_timeout em bases grandes. A funcao abaixo normaliza apenas o
-- parametro e compara value diretamente como CITEXT.
set search_path = mei_email, public;

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
         (s.scope = 'email'
          and s.value = lower(btrim(p_email::text))::public.citext)
         or
         (s.scope = 'domain'
          and s.value = split_part(lower(btrim(p_email::text)), '@', 2)::public.citext)
       )
  );
$function$;

comment on function mei_email.is_email_suppressed(public.citext) is
  'Consulta suppressions por igualdade CITEXT indexavel; nao aplicar funcoes sobre email_suppressions.value.';
