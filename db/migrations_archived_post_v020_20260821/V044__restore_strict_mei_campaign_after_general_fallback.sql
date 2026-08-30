-- V044: restore the strict MEI campaign contract after the temporary V043 fallback.
--
-- This migration is intentionally fail-closed. It does not grant consent, does
-- not reopen terminal sends, and does not remove opt-outs or suppressions.
-- It rejects the synthetic campaign-authorization origin introduced by the
-- temporary production fallback, blocks only still-open affected queue rows,
-- and restores MEI verification as a durable DB-side send gate.
set search_path = mei_email, public;

-- Preserve the origin as audit evidence while revoking the synthetic grant.
update mei_email.empresas
   set campo_autorizacao_legado = false,
       atualizado_em = now()
 where campo_autorizacao_legado_origem = 'user_campaign_authorization_2026-08-20'
   and campo_autorizacao_legado is distinct from false;

-- Never touch terminal history. Only remove unsafe never-terminal work from
-- eligibility by blocking rows that are still open.
update mei_email.envios e
   set status = 'bloqueado'::status_envio,
       erro = case
         when coalesce(e.erro, '') = '' then
           'V044: synthetic campaign authorization rejected; open row blocked'
         else e.erro || ' | V044: synthetic campaign authorization rejected; open row blocked'
       end
  from mei_email.empresas emp
 where emp.cnpj = e.cnpj
   and emp.campo_autorizacao_legado_origem = 'user_campaign_authorization_2026-08-20'
   and e.status::text in ('pendente', 'pending', 'enviando', 'processing');

-- Historical callers still use this signature. MEI classification and verified
-- MEI evidence are again hard requirements for this campaign.
create or replace function mei_email.operational_filter_rejection_reason(
    p_situacao text,
    p_uf text,
    p_email public.citext,
    p_opt_out boolean,
    p_provavel_terceiro boolean,
    p_campo_autorizacao_legado boolean,
    p_tipo_regime text,
    p_mei_verificado boolean
)
returns text
language sql
immutable
as $function$
  select case
    when coalesce(p_opt_out, false) then 'opt_out'
    when coalesce(upper(btrim(p_situacao)), '') <> 'ATIVA' then 'filter_inactive'
    when coalesce(upper(btrim(p_uf)), '') <> 'MG' then 'filter_uf'
    when p_email is null or btrim(p_email::text) = '' then 'filter_email_missing'
    when not mei_email.is_valid_email_address(p_email) then 'filter_email_invalid'
    when coalesce(p_provavel_terceiro, false) then 'filter_third_party'
    when not coalesce(p_campo_autorizacao_legado, false) then 'filter_marketing_not_authorized'
    when coalesce(upper(btrim(p_tipo_regime)), '') <> 'MEI' then 'filter_not_mei'
    when not coalesce(p_mei_verificado, false) then 'filter_mei_not_verified'
    else null
  end;
$function$;

create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.campo_autorizacao_legado,
       e.campo_autorizacao_legado_em, e.campo_autorizacao_legado_origem,
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
   and mei_email.is_independent_marketing_authorization(
       e.campo_autorizacao_legado, e.campo_autorizacao_legado_origem
   )
   and e.campo_autorizacao_legado_origem <> 'user_campaign_authorization_2026-08-20'
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
    new.status := 'bloqueado'::status_envio;
    new.erro := 'V044: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_independent_marketing_authorization(
          emp.campo_autorizacao_legado, emp.campo_autorizacao_legado_origem
      )
      and emp.campo_autorizacao_legado_origem <> 'user_campaign_authorization_2026-08-20'
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
    new.status := 'bloqueado'::status_envio;
    new.erro := case
      when already_terminal then 'V044: destinatario ja terminal; bloqueio anti-replay'
      else 'V044: consentimento/MEI/elegibilidade invalida; bloqueio fail-closed'
    end;
  end if;

  return new;
end
$function$;

drop trigger if exists trg_envio_live_eligibility on mei_email.envios;
create trigger trg_envio_live_eligibility
before insert or update of status, cnpj, email on mei_email.envios
for each row execute function mei_email.enforce_envio_live_eligibility();

comment on view mei_email.vw_empresas_elegiveis is
  'MEI MG ativo com opt-in e verificacao MEI independentes; exclui opt-out, supressoes, origem sintetica, email invalido/contabil, duplicidade e replay terminal.';
