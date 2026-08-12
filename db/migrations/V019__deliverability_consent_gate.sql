-- V019: endurece elegibilidade para recuperacao de reputacao/deliverability.
-- Base publica de CNPJ nunca e consentimento comercial por si so.
set search_path = mei_email, public;

-- Retira da fila atual destinatarios sem evidencia auditavel de autorizacao.
update envios x
   set status = 'bloqueado',
       erro = 'deliverability gate: autorizacao comercial sem origem/data auditavel'
  from empresas e
 where x.cnpj = e.cnpj
   and x.status::text in ('pendente', 'enviando')
   and (
        not e.marketing_autorizado
        or e.marketing_autorizado_em is null
        or e.marketing_autorizado_origem is null
        or lower(btrim(e.marketing_autorizado_origem)) not in (
            'cadastro_site',
            'cliente_ativo',
            'importacao_consentida'
        )
   );

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
   and e.marketing_autorizado_em is not null
   and lower(btrim(e.marketing_autorizado_origem)) in (
       'cadastro_site',
       'cliente_ativo',
       'importacao_consentida'
   )
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
  'Fonte fail-closed: ativa, sem opt-out/terceiro, consentimento auditavel, sem duplicidade e MEI oficialmente verificado.';
