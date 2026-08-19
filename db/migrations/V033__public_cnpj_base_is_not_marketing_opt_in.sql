-- V033: a public CNPJ listing is discovery data, not proof of commercial opt-in.
-- Preserve independently obtained/auditable authorization sources, but revoke
-- the legacy flag that was granted solely by the 2026-08-13 public-base import.
set search_path = mei_email, public;

update empresas
   set marketing_autorizado = false,
       marketing_autorizado_em = null,
       marketing_autorizado_origem = 'base_publica_sem_opt_in_20260819'
 where marketing_autorizado = true
   and marketing_autorizado_origem = 'politica_importacao_operador_2026-08-13';

comment on column empresas.marketing_autorizado is
  'Somente true quando ha autorizacao comercial independente e auditavel; presenca em base publica nao constitui opt-in.';
