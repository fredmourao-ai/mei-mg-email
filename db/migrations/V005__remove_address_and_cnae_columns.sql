-- V005: remove address and CNAE columns from empresas and campanhas tables
set search_path = mei_email, public;

-- Drop dependent view first
drop view if exists vw_empresas_elegiveis;

alter table empresas
  drop column if exists cnae,
  drop column if exists cnae_descricao,
  drop column if exists municipio,
  drop column if exists cep;

alter table campanhas
  drop column if exists filtro_municipio,
  drop column if exists filtro_cnae;

-- Recreate view specifying exact required columns (no cnae/municipio/cep)
create or replace view vw_empresas_elegiveis as
select cnpj, razao_social, nome_fantasia, situacao_cadastral, uf, email,
       ddd_1, telefone_1, data_abertura, provavel_terceiro, opt_out,
       opt_out_em, opt_out_motivo, enviado, enviado_em, importado_em, atualizado_em
  from empresas
 where uf = 'MG'
   and situacao_cadastral = 'ATIVA'
   and opt_out = false
   and provavel_terceiro = false
   and email is not null
   and enviado = false;
