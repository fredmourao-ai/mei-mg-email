-- V038: enforce the live marketing eligibility contract at write time.
-- This migration never grants consent, never creates recipients and never
-- bypasses opt-out, suppression, sender-block or provider limits.
set search_path = mei_email, public;

-- Normalize any legacy campaign copy that may have been recreated after V037.
update campanhas
   set corpo_template = replace(
       corpo_template,
       'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
       'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
   )
 where corpo_template ilike '%base pública de CNPJ%';

-- Fail the migration if a variant of the legacy claim survived normalization.
do $$
begin
  if exists (
      select 1
        from campanhas
       where corpo_template ilike '%base pública de CNPJ%'
  ) then
    raise exception 'V038: legacy public-CNPJ campaign copy remains after normalization';
  end if;
end
$$;

create or replace function mei_email.enforce_campaign_copy_policy()
returns trigger
language plpgsql
as $$
begin
  if new.corpo_template ilike '%base pública de CNPJ%' then
    new.corpo_template := replace(
      new.corpo_template,
      'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
      'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
    );
  end if;

  if new.corpo_template ilike '%base pública de CNPJ%' then
    raise exception 'legacy public-CNPJ marketing copy is forbidden';
  end if;

  return new;
end
$$;

drop trigger if exists trg_campaign_copy_policy on campanhas;
create trigger trg_campaign_copy_policy
before insert or update of corpo_template on campanhas
for each row execute function mei_email.enforce_campaign_copy_policy();

-- Clear any currently-open work that does not satisfy the live contract.
update envios e
   set status = 'bloqueado',
       erro = 'V038: fila aberta inelegivel; bloqueio fail-closed'
  from empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
       emp.marketing_autorizado is not true
       or emp.mei_verificado is not true
       or emp.opt_out is true
       or emp.situacao_cadastral <> 'ATIVA'
       or emp.provavel_terceiro is true
       or emp.email is null
       or btrim(emp.email::text) = ''
       or not mei_email.is_valid_email_address(emp.email)
       or mei_email.is_email_suppressed(emp.email)
       or mei_email.is_cnpj_suppressed(emp.cnpj::text)
   );

create or replace function mei_email.enforce_envio_live_eligibility()
returns trigger
language plpgsql
as $$
declare
  eligible boolean;
begin
  if new.status::text not in ('pendente', 'enviando', 'pending', 'processing') then
    return new;
  end if;

  select (
      emp.marketing_autorizado is true
      and emp.mei_verificado is true
      and emp.opt_out is false
      and emp.situacao_cadastral = 'ATIVA'
      and emp.provavel_terceiro is false
      and emp.email is not null
      and btrim(emp.email::text) <> ''
      and mei_email.is_valid_email_address(emp.email)
      and not mei_email.is_email_suppressed(emp.email)
      and not mei_email.is_cnpj_suppressed(emp.cnpj::text)
  )
    into eligible
    from empresas emp
   where emp.cnpj = new.cnpj;

  if coalesce(eligible, false) is false then
    new.status := 'bloqueado'::status_envio;
    new.erro := 'V038: envio aberto inelegivel; bloqueio fail-closed';
  end if;

  return new;
end
$$;

drop trigger if exists trg_envio_live_eligibility on envios;
create trigger trg_envio_live_eligibility
before insert or update of status, cnpj, email on envios
for each row execute function mei_email.enforce_envio_live_eligibility();

-- Reconcile lot state after fail-closed cleanup. status_lote is an enum, so
-- cast the CASE result explicitly.
update lotes l
   set status = (case
       when exists (
           select 1
             from envios e
            where e.lote_id = l.id
              and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
       ) then 'pendente'
       else 'concluido'
   end)::status_lote,
       iniciado_em = null,
       erro = null
 where l.status::text in ('pendente', 'processando', 'processing');
