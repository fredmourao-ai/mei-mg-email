-- V036: retire the legacy operator policy that auto-authorized every imported
-- public CNPJ row for marketing and auto-verified it as MEI.
-- Public discovery data is not consent, and MEI verification must come from
-- the official Simples/OPCAO_PELO_MEI path. This migration is fail-closed and
-- preserves independently recorded authorization/verification sources.
set search_path = mei_email, public;

-- Stop future inserts from receiving authorization/verification by legacy
-- trigger. The historical migration remains immutable; this forward migration
-- changes the effective policy.
drop trigger if exists empresas_aplicar_politica_importacao_operador on empresas;
drop function if exists mei_email.trg_aplicar_politica_importacao_operador();

-- New operational rows are unauthorized unless a separate audited workflow
-- explicitly records authorization. MEI verification is also false by default.
alter table empresas alter column campo_autorizacao_legado set default false;
alter table empresas alter column mei_verificado set default false;

-- Catch rows inserted after V033 by the still-active legacy trigger. Rows whose
-- authorization source has since been replaced by an independent source are
-- untouched.
update empresas
   set campo_autorizacao_legado = false,
       campo_autorizacao_legado_em = null,
       campo_autorizacao_legado_origem = 'base_publica_sem_opt_in_20260819'
 where campo_autorizacao_legado = true
   and campo_autorizacao_legado_origem = 'politica_importacao_operador_2026-08-13';

-- The same legacy trigger also claimed MEI verification without an official
-- source. Revoke only that legacy-origin verification. Officially verified
-- rows use a different origin and are preserved.
update empresas
   set mei_verificado = false,
       mei_verificado_em = null,
       mei_verificado_origem = 'nao_verificado_legacy_operator_policy_revoked',
       tipo_regime = case when tipo_regime = 'MEI' then 'MEI_CANDIDATO' else tipo_regime end
 where mei_verificado = true
   and mei_verificado_origem = 'politica_importacao_operador_2026-08-13';

comment on column empresas.campo_autorizacao_legado is
  'true somente quando existe autorizacao comercial independente e auditavel; importacao de base publica nao concede opt-in.';
comment on column empresas.mei_verificado is
  'true somente quando fonte oficial de Simples/MEI confirmou o enquadramento.';
