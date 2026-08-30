-- V040: make authorization source part of the live eligibility contract.
--
-- Historical operator migrations V021-V023 can mark discovery rows as
-- authorized/verified without independent consent or official MEI evidence.
-- Those origins must never be treated as live eligibility, even if a divergent
-- Flyway history exposes their old boolean values. This migration does not
-- grant authorization and does not create recipients.
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
     and btrim(p_origin) not in (
       'confirmacao_operador_2026-08-12',
       'confirmacao_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13'
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
     and btrim(p_origin) not in (
       'override_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13'
     );
$function$;

-- Future writes cannot revive one of the historical operator overrides. The
-- trigger runs after the old V023 trigger alphabetically and neutralizes only
-- the explicitly retired origins; independent audited sources are preserved.
create or replace function mei_email.enforce_independent_empresa_sources()
returns trigger
language plpgsql
as $function$
begin
  if new.campo_autorizacao_legado is true
     and btrim(coalesce(new.campo_autorizacao_legado_origem, '')) in (
       'confirmacao_operador_2026-08-12',
       'confirmacao_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13'
     )
  then
    new.campo_autorizacao_legado := false;
    new.campo_autorizacao_legado_em := null;
    new.campo_autorizacao_legado_origem := 'legacy_operator_authorization_rejected_20260820';
  end if;

  if new.mei_verificado is true
     and btrim(coalesce(new.mei_verificado_origem, '')) in (
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

drop trigger if exists zz_empresas_enforce_independent_sources on empresas;
create trigger zz_empresas_enforce_independent_sources
before insert or update of campo_autorizacao_legado, campo_autorizacao_legado_origem,
    mei_verificado, mei_verificado_origem on empresas
for each row execute function mei_email.enforce_independent_empresa_sources();

-- Existing open work sourced only from the retired operator overrides is not
-- allowed to reach the worker. Existing retention triggers preserve technical
-- evidence/suppression when a blocked row is purged.
update envios e
   set status = 'bloqueado',
       erro = 'V040: origem de autorizacao/verificacao legado; bloqueio fail-closed'
  from empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
       not mei_email.is_independent_marketing_authorization(
           emp.campo_autorizacao_legado, emp.campo_autorizacao_legado_origem
       )
       or not mei_email.is_independent_mei_verification(
           emp.mei_verificado, emp.mei_verificado_origem
       )
   );

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
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and mei_email.is_valid_email_address(e.email)
   and mei_email.is_independent_marketing_authorization(
       e.campo_autorizacao_legado, e.campo_autorizacao_legado_origem
   )
   and mei_email.is_independent_mei_verification(
       e.mei_verificado, e.mei_verificado_origem
   )
   and e.enviado = false
   and e.tipo_regime = 'MEI'
   and not mei_email.is_email_suppressed(e.email)
   and not mei_email.is_cnpj_suppressed(e.cnpj::text)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status::text in (
          'pendente','enviando','pending','processing',
          'submitted','enviado','delivered','bounced'
        )
   );

-- Replace V038's live gate with source-aware authorization and an explicit
-- same-row terminal-state replay barrier. A row that was already terminal can
-- never be reopened to an active send state.
create or replace function mei_email.enforce_envio_live_eligibility()
returns trigger
language plpgsql
as $function$
declare
  eligible boolean;
  already_sent boolean;
begin
  if new.status::text not in ('pendente', 'enviando', 'pending', 'processing') then
    return new;
  end if;

  if tg_op = 'UPDATE'
     and old.status::text in ('submitted', 'enviado', 'delivered') then
    new.status := 'bloqueado'::status_envio;
    new.erro := 'V040: tentativa de reabrir envio terminal; bloqueio anti-replay';
    return new;
  end if;

  select (
      mei_email.is_independent_marketing_authorization(
          emp.campo_autorizacao_legado, emp.campo_autorizacao_legado_origem
      )
      and mei_email.is_independent_mei_verification(
          emp.mei_verificado, emp.mei_verificado_origem
      )
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

  select exists (
      select 1
        from envios prior
       where prior.id <> new.id
         and lower(btrim(prior.email::text)) = lower(btrim(new.email::text))
         and prior.status::text in ('submitted', 'enviado', 'delivered')
  ) into already_sent;

  if coalesce(eligible, false) is false or already_sent then
    new.status := 'bloqueado'::status_envio;
    new.erro := case
      when already_sent then 'V040: destinatario ja submetido/entregue; bloqueio anti-replay'
      else 'V040: origem/autorizacao/elegibilidade invalida; bloqueio fail-closed'
    end;
  end if;

  return new;
end
$function$;

-- V038 already created the trigger; recreate it defensively in case production
-- schema history was reconciled from partial structural state.
drop trigger if exists trg_envio_live_eligibility on envios;
create trigger trg_envio_live_eligibility
before insert or update of status, cnpj, email on envios
for each row execute function mei_email.enforce_envio_live_eligibility();

comment on function mei_email.is_independent_marketing_authorization(boolean, text) is
  'true only for non-empty authorization sources other than retired V021-V023 operator/public-base overrides.';
comment on function mei_email.is_independent_mei_verification(boolean, text) is
  'true only for non-empty MEI verification sources other than retired operator overrides.';
