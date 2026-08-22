-- V045: repair the live eligibility trigger without rewriting Flyway history.
--
-- V044 restored the strict MEI gate, but its PL/pgSQL body cast the blocked
-- status using the unqualified enum name `status_envio`. At runtime the
-- function can execute with a search_path that does not include `mei_email`,
-- causing every rejected/open queue insert to abort with UndefinedObject.
-- This migration preserves the same fail-closed policy and only makes the
-- schema dependency explicit and durable.
set search_path = mei_email, public;

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
    new.erro := 'V045: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_independent_marketing_authorization(
          emp.marketing_autorizado, emp.marketing_autorizado_origem
      )
      and emp.marketing_autorizado_origem <> 'user_campaign_authorization_2026-08-20'
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
      when already_terminal then 'V045: destinatario ja terminal; bloqueio anti-replay'
      else 'V045: consentimento/MEI/elegibilidade invalida; bloqueio fail-closed'
    end;
  end if;

  return new;
end
$function$;

comment on function mei_email.enforce_envio_live_eligibility() is
  'Fail-closed live eligibility guard with schema-qualified enum and fixed function search_path (V045).';
