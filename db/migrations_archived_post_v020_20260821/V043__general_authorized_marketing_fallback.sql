-- V043: general authorized MG marketing fallback after MEI stock.
--
-- Marketing authorization and MEI classification are independent facts.
-- A contact no longer needs verified MEI status to be generally eligible for
-- an authorized marketing campaign. MEI verification remains useful for
-- prioritization/classification, not as a universal send gate.
--
-- This migration does NOT grant authorization, reopen terminal sends, remove
-- opt-outs, clear hard-bounce/complaint suppressions, or change Microsoft rate
-- limits. It preserves MG scope and adds the current email-quality exclusions.
set search_path = mei_email, public;

-- Keep the legacy function signature because historical triggers call it, but
-- do not reject a company solely for not being MEI / not having MEI evidence.
create or replace function mei_email.operational_filter_rejection_reason(
    p_situacao text,
    p_uf text,
    p_email public.citext,
    p_opt_out boolean,
    p_provavel_terceiro boolean,
    p_marketing_autorizado boolean,
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
    when not coalesce(p_marketing_autorizado, false) then 'filter_marketing_not_authorized'
    else null
  end;
$function$;

-- General live view. Exactly two source registrations for the same normalized
-- email remain allowed; 3+ distinct CNPJs are excluded. Actual sends remain
-- deduplicated by normalized email through envios history/open rows.
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
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and mei_email.is_valid_email_address(e.email)
   and position('contabil' in lower(btrim(e.email::text))) = 0
   and mei_email.is_independent_marketing_authorization(
       e.marketing_autorizado, e.marketing_autorizado_origem
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
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status::text in (
          'pendente','enviando','pending','processing',
          'submitted','enviado','delivered','bounced','bounce_permanent'
        )
   );

-- Send-time DB guard mirrors the general live view and retains terminal
-- anti-replay. It deliberately does not require tipo_regime=MEI or
-- is_independent_mei_verification().
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
    new.erro := 'V043: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_independent_marketing_authorization(
          emp.marketing_autorizado, emp.marketing_autorizado_origem
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
         and lower(btrim(prior.email::text)) = lower(btrim(new.email::text))
         and prior.status::text in (
           'submitted', 'enviado', 'delivered', 'bounced', 'bounce_permanent'
         )
  ) into already_terminal;

  if coalesce(eligible, false) is false or already_terminal then
    new.status := 'bloqueado'::status_envio;
    new.erro := case
      when already_terminal then 'V043: destinatario ja terminal; bloqueio anti-replay'
      else 'V043: autorizacao/elegibilidade invalida; bloqueio fail-closed'
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
  'MG ativo e marketing autorizado; MEI e priorizacao, nao gate universal; exclui opt-out, terceiro, email invalido/contabil, 3+ CNPJs, supressoes e replay.';
