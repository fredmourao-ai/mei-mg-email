-- V045: repair runtime eligibility function enum casts without requiring
-- relation-level trigger recreation. Existing trg_envio_live_eligibility calls
-- this function by OID/name, so CREATE OR REPLACE updates the live behavior in
-- place while the worker remains available.
--
-- This migration does not grant consent, create recipients, reopen terminal
-- sends, remove suppressions/opt-outs, change provider limits, or clear a
-- Microsoft sender-block sentinel.
set search_path = mei_email, public;

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
  'Live MEI eligibility and anti-replay guard with schema-qualified enum casts; V045.';
