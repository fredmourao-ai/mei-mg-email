-- V046: supersede the V042 helper-signature conflict without rewriting history.
--
-- Production can already contain is_independent_marketing_authorization(boolean,text)
-- with historical input parameter names. PostgreSQL does not allow CREATE OR
-- REPLACE FUNCTION to rename input parameters, so replaying V042 can fail even
-- though its policy is still required. This forward migration avoids replacing
-- that historical helper. It introduces a new policy helper and makes every
-- durable live-send gate use it explicitly.
--
-- ONLINE-SAFETY: this migration deliberately does not rewrite every historical
-- empresa row. On the production corpus that full-table UPDATE can exceed the
-- bounded statement timeout and delay installation of the actual live-send
-- guards. Existing synthesized origins remain audit evidence but are rejected
-- immediately by the view, queue predicates and live trigger below. Historical
-- physical cleanup, when desired, must be done separately in bounded batches.
--
-- This migration never grants consent, never creates recipients, never reopens
-- terminal sends and never clears opt-outs, suppressions or sender-block state.
set search_path = mei_email, public;

create or replace function mei_email.is_allowed_marketing_authorization_source(
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
     and btrim(p_origin) not in (
       'confirmacao_operador_2026-08-12',
       'confirmacao_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13',
       'user_explicit_authorization_2026-08-20',
       'user_campaign_authorization_2026-08-20'
     )
     and lower(btrim(p_origin)) not like '%operator_authorization_true%';
$function$;

create or replace function mei_email.enforce_independent_empresa_sources()
returns trigger
language plpgsql
set search_path = mei_email, public
as $function$
declare
  mei_origin text := btrim(coalesce(new.mei_verificado_origem, ''));
begin
  if new.marketing_autorizado is true
     and not mei_email.is_allowed_marketing_authorization_source(
       new.marketing_autorizado, new.marketing_autorizado_origem
     )
  then
    new.marketing_autorizado := false;
    new.marketing_autorizado_em := null;
  end if;

  if new.mei_verificado is true
     and mei_origin in (
       'override_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13'
     )
  then
    new.mei_verificado := false;
    new.mei_verificado_em := null;
    new.mei_verificado_origem := 'legacy_operator_verification_rejected_20260820';
    if new.tipo_regime = 'MEI' then
      new.tipo_regime := 'MEI_CANDIDATO';
    end if;
  end if;

  return new;
end
$function$;

-- V040 created this trigger. Recreate only if schema drift removed it.
do $do$
begin
  if not exists (
    select 1
      from pg_trigger t
      join pg_class c on c.oid=t.tgrelid
      join pg_namespace n on n.oid=c.relnamespace
     where not t.tgisinternal
       and n.nspname='mei_email'
       and c.relname='empresas'
       and t.tgname='zz_empresas_enforce_independent_sources'
  ) then
    create trigger zz_empresas_enforce_independent_sources
    before insert or update of marketing_autorizado, marketing_autorizado_origem,
      mei_verificado, mei_verificado_origem on mei_email.empresas
    for each row execute function mei_email.enforce_independent_empresa_sources();
  end if;
end
$do$;

-- Only still-open unsafe rows are blocked. Terminal evidence is untouched.
-- OPEN_TOTAL is normally small; unlike the historical empresas table this is
-- a bounded operational set and therefore safe to normalize during migration.
update mei_email.envios e
   set status = 'bloqueado'::mei_email.status_envio,
       erro = 'V046: origem de autorizacao sintetizada/invalida; bloqueio fail-closed'
  from mei_email.empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
       not mei_email.is_allowed_marketing_authorization_source(
         emp.marketing_autorizado, emp.marketing_autorizado_origem
       )
       or upper(coalesce(emp.tipo_regime, '')) <> 'MEI'
       or not mei_email.is_independent_mei_verification(
         emp.mei_verificado, emp.mei_verificado_origem
       )
   );

create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and upper(e.uf) = 'MG'
   and upper(coalesce(e.tipo_regime, '')) = 'MEI'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and mei_email.is_valid_email_address(e.email)
   and position('contabil' in lower(btrim(e.email::text))) = 0
   and mei_email.is_allowed_marketing_authorization_source(
       e.marketing_autorizado, e.marketing_autorizado_origem
   )
   and mei_email.is_independent_mei_verification(
       e.mei_verificado, e.mei_verificado_origem
   )
   and e.enviado = false
   and (
     select count(distinct e2.cnpj)
       from mei_email.empresas e2
      where lower(btrim(e2.email::text)) = lower(btrim(e.email::text))
   ) <= 2
   and not mei_email.is_email_suppressed(e.email)
   and not mei_email.is_cnpj_suppressed(e.cnpj::text)
   and not exists (
     select 1
       from mei_email.envios x
      where (
             x.cnpj = e.cnpj
             or lower(btrim(x.email::text)) = lower(btrim(e.email::text))
            )
        and x.status::text in (
          'pendente','enviando','pending','processing',
          'submitted','enviado','delivered','bounced','bounce_permanent'
        )
   );

create or replace function mei_email.enforce_envio_live_eligibility()
returns trigger
language plpgsql
set search_path = mei_email, public
as $function$
declare
  eligible boolean;
  already_terminal boolean;
begin
  if new.status::text not in ('pendente', 'enviando', 'pending', 'processing') then
    return new;
  end if;

  if tg_op = 'UPDATE'
     and old.status::text in ('submitted', 'enviado', 'delivered', 'bounced', 'bounce_permanent') then
    new.status := 'bloqueado'::mei_email.status_envio;
    new.erro := 'V046: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_allowed_marketing_authorization_source(
          emp.marketing_autorizado, emp.marketing_autorizado_origem
      )
      and upper(coalesce(emp.tipo_regime, '')) = 'MEI'
      and mei_email.is_independent_mei_verification(
          emp.mei_verificado, emp.mei_verificado_origem
      )
      and emp.opt_out is false
      and emp.situacao_cadastral = 'ATIVA'
      and upper(emp.uf) = 'MG'
      and emp.provavel_terceiro is false
      and emp.email is not null
      and btrim(emp.email::text) <> ''
      and lower(btrim(emp.email::text)) = lower(btrim(new.email::text))
      and mei_email.is_valid_email_address(emp.email)
      and position('contabil' in lower(btrim(emp.email::text))) = 0
      and (
        select count(distinct emp2.cnpj)
          from mei_email.empresas emp2
         where lower(btrim(emp2.email::text)) = lower(btrim(emp.email::text))
      ) <= 2
      and not mei_email.is_email_suppressed(emp.email)
      and not mei_email.is_cnpj_suppressed(emp.cnpj::text)
  )
    into eligible
    from mei_email.empresas emp
   where emp.cnpj = new.cnpj;

  select exists (
      select 1
        from mei_email.envios prior
       where prior.id <> new.id
         and (
              prior.cnpj = new.cnpj
              or lower(btrim(prior.email::text)) = lower(btrim(new.email::text))
         )
         and prior.status::text in (
           'submitted', 'enviado', 'delivered', 'bounced', 'bounce_permanent'
         )
  ) into already_terminal;

  if coalesce(eligible, false) is false or already_terminal then
    new.status := 'bloqueado'::mei_email.status_envio;
    new.erro := case
      when already_terminal then 'V046: destinatario ja terminal; bloqueio anti-replay'
      else 'V046: consentimento/MEI/elegibilidade invalida; bloqueio fail-closed'
    end;
  end if;

  return new;
end
$function$;

comment on function mei_email.is_allowed_marketing_authorization_source(boolean, text) is
  'V046 canonical consent-source gate; rejects synthesized operator/recovery origins without replacing historical helper signatures.';
comment on view mei_email.vw_empresas_elegiveis is
  'V046 strict MEI/MG eligible pool with independent consent source, verified MEI evidence, suppression and anti-replay gates.';
comment on function mei_email.enforce_envio_live_eligibility() is
  'V046 fail-closed live-send guard with schema-qualified enum and canonical consent-source gate.';
