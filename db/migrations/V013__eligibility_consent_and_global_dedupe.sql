-- Fail-closed eligibility for commercial campaigns.
-- Only active, explicitly authorized, never-contacted addresses can enter a new queue.
set search_path = mei_email, public;

alter table empresas
  add column if not exists marketing_autorizado boolean not null default false,
  add column if not exists marketing_autorizado_em timestamptz,
  add column if not exists marketing_autorizado_origem text;

comment on column empresas.marketing_autorizado is
  'true somente quando existe permissao/base operacional validada para comunicacao comercial. Importacao de base publica permanece false por padrao.';
comment on column empresas.marketing_autorizado_origem is
  'origem auditavel da autorizacao, por exemplo cadastro_site, cliente_ativo ou importacao_consentida.';

alter type status_envio add value if not exists 'bloqueado';

create index if not exists idx_empresas_marketing_autorizado
  on empresas (marketing_autorizado)
  where marketing_autorizado = true;

create index if not exists idx_envios_email_normalizado
  on envios (lower(btrim(email::text)));

drop view if exists vw_empresas_elegiveis;

create view vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem
  from empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.enviado = false
   and e.marketing_autorizado = true
   and not exists (
     select 1
       from envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
   );

comment on view vw_empresas_elegiveis is
  'Fonte fail-closed para campanhas: ativa, sem opt-out/terceiro, autorizada e sem qualquer tentativa previa para o mesmo e-mail normalizado.';
