-- One recipient per normalized address, even when several CNPJs share it.
-- The duplicate marker remains available for audit but no longer excludes a
-- valid recipient from the campaign selection.
set search_path = mei_email, public;

create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.marketing_autorizado = true
   and e.enviado = false
   and (
        e.tipo_regime not in ('MEI', 'MEI_CANDIDATO')
        or e.mei_verificado = true
   )
   and not mei_email.is_email_suppressed(e.email)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status in (
          'pending', 'processing', 'submitted', 'delivered',
          'bounce_temporary', 'bounce_permanent'
        )
   );

comment on view mei_email.vw_empresas_elegiveis is
  'Fonte fail-closed: ativa, autorizada, sem opt-out ou supressao e, para MEI, com enquadramento oficial. O enfileirador deduplica por e-mail e envia uma unica vez.';
