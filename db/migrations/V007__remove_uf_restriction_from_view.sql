-- V007: adiciona filtro_uf em campanhas e remove restricao fixa de uf='MG' da view
set search_path = mei_email, public;

drop view if exists vw_empresas_elegiveis;

alter table campanhas
  add column if not exists filtro_uf varchar(2);

comment on column campanhas.filtro_uf is
  'Filtro opcional por UF da empresa (ex: MG, SP, RJ). Se null, seleciona empresas de todos os estados.';

create or replace view vw_empresas_elegiveis as
select cnpj, razao_social, nome_fantasia, situacao_cadastral, uf, email,
       ddd_1, telefone_1, data_abertura, provavel_terceiro, opt_out,
       opt_out_em, opt_out_motivo, enviado, enviado_em, importado_em, atualizado_em,
       tipo_regime
  from empresas
 where situacao_cadastral = 'ATIVA'
   and opt_out = false
   and provavel_terceiro = false
   and email is not null
   and enviado = false;
