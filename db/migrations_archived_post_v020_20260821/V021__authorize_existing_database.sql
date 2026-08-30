-- V021: registra a confirmacao do operador de que todo o estoque atual do banco
-- ja possui autorizacao comercial. Esta migration afeta somente registros que
-- existem no momento em que ela roda; novas importacoes continuam usando o
-- default campo_autorizacao_legado=false e precisam de regra/confirmacao posterior.
set search_path = mei_email, public;

-- A V019 exigia uma lista fechada de origens. A partir desta confirmacao, a
-- origem continua auditavel, mas deixa de ser usada como trava operacional.
alter table empresas
  drop constraint if exists chk_empresas_marketing_autorizacao_auditavel;

update empresas
   set campo_autorizacao_legado = true,
       campo_autorizacao_legado_em = coalesce(campo_autorizacao_legado_em, now()),
       campo_autorizacao_legado_origem = coalesce(
           nullif(btrim(campo_autorizacao_legado_origem), ''),
           'confirmacao_operador_2026-08-12'
       );

-- Mantem apenas a consistencia de auditoria: se o booleano estiver ligado,
-- data e origem precisam existir. Nao ha allowlist de origem no envio/fila.
alter table empresas
  add constraint chk_empresas_marketing_autorizacao_auditavel
  check (
    not campo_autorizacao_legado
    or (
      campo_autorizacao_legado_em is not null
      and campo_autorizacao_legado_origem is not null
      and btrim(campo_autorizacao_legado_origem) <> ''
    )
  );

-- Reabre somente itens bloqueados pela V019 por falta de origem/data. Opt-out,
-- terceiro provavel e empresa inativa continuam sendo bloqueados pelo worker e
-- pela view de elegibilidade.
update envios x
   set status = 'pendente',
       erro = null
  from empresas e
 where x.cnpj = e.cnpj
   and x.status::text = 'bloqueado'
   and x.erro = 'deliverability gate: autorizacao comercial sem origem/data auditavel'
   and e.campo_autorizacao_legado = true
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.situacao_cadastral = 'ATIVA';

create or replace view vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.campo_autorizacao_legado,
       e.campo_autorizacao_legado_em, e.campo_autorizacao_legado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.enviado = false
   and e.campo_autorizacao_legado = true
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
  'Fonte fail-closed: ativa, sem opt-out/terceiro, campo_autorizacao_legado=true, sem duplicidade e MEI oficialmente verificado.';
