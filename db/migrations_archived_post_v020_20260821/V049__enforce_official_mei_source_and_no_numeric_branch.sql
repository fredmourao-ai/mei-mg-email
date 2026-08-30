-- V049: make the official MEI source and no-branch rule durable in the DB.
--
-- MEI is a legal/tax classification. The only audited source implemented by
-- this system is Receita/Simples OPCAO_PELO_MEI. A numeric CNPJ whose
-- establishment order (positions 9-12) is not 0001 is a branch, and a MEI
-- cannot have a branch. This migration is fail-closed: it blocks only still-
-- open work and never grants consent, clears suppressions, or reopens terminal
-- send history.
set search_path = mei_email, public;

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
     and lower(btrim(coalesce(p_origin, ''))) = 'receita_simples_opcao_mei';
$function$;

create or replace function mei_email.is_legacy_numeric_branch_cnpj(p_cnpj text)
returns boolean
language sql
immutable
parallel safe
as $function$
  select case
    when regexp_replace(coalesce(p_cnpj, ''), '\\D', '', 'g') ~ '^[0-9]{14}$'
      then substring(regexp_replace(p_cnpj, '\\D', '', 'g') from 9 for 4) <> '0001'
    else false
  end;
$function$;

update mei_email.envios e
   set status = 'bloqueado'::mei_email.status_envio,
       erro = concat_ws(
         ' | ',
         nullif(btrim(e.erro), ''),
         'V049: MEI sem fonte oficial Receita/Simples ou CNPJ de filial; bloqueio fail-closed'
       )
  from mei_email.empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
     not mei_email.is_independent_mei_verification(
       emp.mei_verificado, emp.mei_verificado_origem
     )
     or mei_email.is_legacy_numeric_branch_cnpj(emp.cnpj::text)
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
    new.erro := 'V049: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_independent_marketing_authorization(
          emp.campo_autorizacao_legado, emp.campo_autorizacao_legado_origem
      )
      and mei_email.is_independent_mei_verification(
          emp.mei_verificado, emp.mei_verificado_origem
      )
      and not mei_email.is_legacy_numeric_branch_cnpj(emp.cnpj::text)
      and upper(coalesce(emp.tipo_regime, '')) = 'MEI'
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
      when already_terminal then 'V049: destinatario ja terminal; bloqueio anti-replay'
      else 'V049: consentimento/MEI/elegibilidade invalida; bloqueio fail-closed'
    end;
  end if;

  return new;
end
$function$;

create or replace function mei_email.enforce_independent_empresa_sources()
returns trigger
language plpgsql
set search_path = mei_email, public
as $function$
begin
  if new.campo_autorizacao_legado is true
     and not mei_email.is_independent_marketing_authorization(
       new.campo_autorizacao_legado, new.campo_autorizacao_legado_origem
     )
  then
    new.campo_autorizacao_legado := false;
    new.campo_autorizacao_legado_em := null;
  end if;

  if new.mei_verificado is true
     and (
       not mei_email.is_independent_mei_verification(
         new.mei_verificado, new.mei_verificado_origem
       )
       or mei_email.is_legacy_numeric_branch_cnpj(new.cnpj::text)
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

comment on function mei_email.is_independent_mei_verification(boolean, text) is
  'V049: only the audited Receita/Simples OPCAO_PELO_MEI source is accepted.';
comment on function mei_email.is_legacy_numeric_branch_cnpj(text) is
  'V049: numeric establishment order other than 0001 denotes a branch; MEI cannot have branches.';
comment on function mei_email.enforce_envio_live_eligibility() is
  'V049: durable fail-closed live eligibility including official MEI source, no-branch rule, suppressions and anti-replay.';
