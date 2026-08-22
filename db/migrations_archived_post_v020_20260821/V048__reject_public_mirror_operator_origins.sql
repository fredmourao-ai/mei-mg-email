-- V048: public/mirror discovery data and operator import policy are not opt-in
-- and are not independent MEI verification.
--
-- A historical mirror importer used origins such as
-- `politica_importacao_operador_2026-08-13_huggingface_upsert`. Earlier gates
-- rejected only the exact base string, so suffixed variants could pass. This
-- migration closes that prefix loophole in every helper used by autoqueue and
-- the live envio trigger. It never grants consent, clears suppressions, or
-- reopens terminal history.
set search_path = mei_email, public;

create or replace function mei_email.is_independent_marketing_authorization(
    p_authorized boolean,
    p_origin text
)
returns boolean
language sql
immutable
parallel safe
as $function$
  select coalesce(p_authorized, false)
     and nullif(btrim(coalesce(p_origin, '')), '') is not null
     and lower(btrim(p_origin)) not like 'politica_importacao_operador%'
     and lower(btrim(p_origin)) not like 'base_publica%'
     and lower(btrim(p_origin)) not like 'user_explicit_authorization%'
     and lower(btrim(p_origin)) not like 'user_campaign_authorization%'
     and lower(btrim(p_origin)) not like '%operator_authorization_true%'
     and btrim(p_origin) not in (
       'confirmacao_operador_2026-08-12',
       'confirmacao_operador_2026-08-13'
     );
$function$;

create or replace function mei_email.is_independent_mei_verification(
    p_verified boolean,
    p_origin text
)
returns boolean
language sql
immutable
parallel safe
as $function$
  select coalesce(p_verified, false)
     and nullif(btrim(coalesce(p_origin, '')), '') is not null
     and lower(btrim(p_origin)) not like 'politica_importacao_operador%'
     and lower(btrim(p_origin)) not like 'override_operador%'
     and lower(btrim(p_origin)) not like 'nao_verificado%'
     and lower(btrim(p_origin)) not like 'legacy_operator_verification_rejected%';
$function$;

-- Keep V046's canonical helper aligned with the same no-public-base policy.
create or replace function mei_email.is_allowed_marketing_authorization_source(
    p_authorized boolean,
    p_origin text
)
returns boolean
language sql
immutable
parallel safe
as $function$
  select mei_email.is_independent_marketing_authorization(p_authorized, p_origin);
$function$;

-- Neutralize future writes from any old importer that is still present. The
-- original origin string is preserved so the evidence remains auditable.
create or replace function mei_email.enforce_independent_empresa_sources()
returns trigger
language plpgsql
set search_path = mei_email, public
as $function$
begin
  if new.marketing_autorizado is true
     and not mei_email.is_independent_marketing_authorization(
       new.marketing_autorizado, new.marketing_autorizado_origem
     )
  then
    new.marketing_autorizado := false;
    new.marketing_autorizado_em := null;
  end if;

  if new.mei_verificado is true
     and not mei_email.is_independent_mei_verification(
       new.mei_verificado, new.mei_verificado_origem
     )
  then
    new.mei_verificado := false;
    new.mei_verificado_em := null;
    if upper(coalesce(new.tipo_regime, '')) = 'MEI' then
      new.tipo_regime := 'MEI_CANDIDATO';
    end if;
  end if;

  return new;
end
$function$;

-- Existing contaminated empresa rows are left as audit evidence; they are now
-- false at the helper level. Only still-open work is normalized immediately.
update mei_email.envios e
   set status = 'bloqueado'::mei_email.status_envio,
       erro = concat_ws(
         ' | ',
         nullif(btrim(e.erro), ''),
         'V048: origem publica/operador nao comprova opt-in ou MEI; bloqueio fail-closed'
       )
  from mei_email.empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
     not mei_email.is_independent_marketing_authorization(
       emp.marketing_autorizado, emp.marketing_autorizado_origem
     )
     or not mei_email.is_independent_mei_verification(
       emp.mei_verificado, emp.mei_verificado_origem
     )
   );

-- Recreate the trigger defensively without touching terminal send records.
drop trigger if exists zz_empresas_enforce_independent_sources on mei_email.empresas;
create trigger zz_empresas_enforce_independent_sources
before insert or update of marketing_autorizado, marketing_autorizado_origem,
  mei_verificado, mei_verificado_origem on mei_email.empresas
for each row execute function mei_email.enforce_independent_empresa_sources();

comment on function mei_email.is_independent_marketing_authorization(boolean, text) is
  'V048: commercial authorization must be independent; public-base/operator-import prefixes are never opt-in.';
comment on function mei_email.is_independent_mei_verification(boolean, text) is
  'V048: MEI verification must be independent; operator-import/override prefixes are rejected.';
