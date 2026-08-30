-- V033: a public CNPJ listing is discovery data, not proof of commercial opt-in.
-- Preserve independently obtained/auditable authorization sources, but revoke
-- the legacy flag that was granted solely by the 2026-08-13 public-base import.
set search_path = mei_email, public;

update empresas
   set campo_autorizacao_legado = false,
       campo_autorizacao_legado_em = null,
       campo_autorizacao_legado_origem = 'base_publica_sem_opt_in_20260819'
 where campo_autorizacao_legado = true
   and campo_autorizacao_legado_origem = 'politica_importacao_operador_2026-08-13';

comment on column empresas.campo_autorizacao_legado is
  'Somente true quando ha autorizacao comercial independente e auditavel; presenca em base publica nao constitui opt-in.';
