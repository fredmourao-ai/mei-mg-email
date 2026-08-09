-- Fonte oficial de Simples/MEI e responsavel por marcar esta verificacao.
-- Fontes comerciais podem classificar candidatos, mas nunca devem habilita-los
-- para campanha sem esta evidencia.
alter table mei_email.empresas
  add column if not exists mei_verificado boolean not null default false,
  add column if not exists mei_verificado_em timestamptz,
  add column if not exists mei_verificado_origem text;
