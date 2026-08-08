-- V016: separa classificacao aproximada de MEI de verificacao oficial.
set search_path = mei_email, public;

alter table empresas
  add column if not exists mei_verificado boolean not null default false,
  add column if not exists mei_verificado_em timestamptz,
  add column if not exists mei_verificado_origem text;

comment on column empresas.mei_verificado is
  'true somente quando uma fonte oficial de Simples/MEI confirmou o CNPJ basico como optante pelo MEI.';
comment on column empresas.mei_verificado_origem is
  'Fonte auditavel da verificacao, por exemplo receita_simples_opcao_mei.';

-- Nao reescrevemos o historico em massa. Registros antigos rotulados MEI por
-- heuristica permanecem com o rotulo legado, mas ficam inelegiveis enquanto
-- mei_verificado=false. Novas cargas do espelho usam MEI_CANDIDATO.
create index if not exists idx_empresas_mei_verificado
  on empresas (mei_verificado)
  where mei_verificado = true;

create or replace view vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.enviado = false
   and e.marketing_autorizado = true
   and (
        e.tipo_regime not in ('MEI', 'MEI_CANDIDATO')
        or e.mei_verificado = true
   )
   and not exists (
     select 1
       from envios x
      where x.cnpj = e.cnpj
        and x.status::text in ('submitted', 'enviado', 'bounced', 'pendente', 'enviando')
   )
   and not exists (
     select 1
       from envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status::text in ('submitted', 'enviado', 'bounced', 'pendente', 'enviando')
   );

comment on view vw_empresas_elegiveis is
  'Fonte fail-closed: ativa, autorizada, sem supressoes/duplicidade e, para MEI ou candidato a MEI, com enquadramento oficialmente verificado.';
