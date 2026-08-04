-- V006: adiciona coluna tipo_regime (MEI, SIMPLES, OUTROS) em empresas
set search_path = mei_email, public;

-- Drop dependent view first
drop view if exists vw_empresas_elegiveis;

alter table empresas
  add column if not exists tipo_regime varchar(20) not null default 'MEI';

alter table campanhas
  add column if not exists filtro_tipo_regime varchar(20);

comment on column empresas.tipo_regime is
  'Tipo de regime tributário/cadastral: MEI, SIMPLES ou OUTROS. Permite segmentar campanhas por modelo de e-mail.';

-- Recreate view including tipo_regime
create or replace view vw_empresas_elegiveis as
select cnpj, razao_social, nome_fantasia, situacao_cadastral, uf, email,
       ddd_1, telefone_1, data_abertura, provavel_terceiro, opt_out,
       opt_out_em, opt_out_motivo, enviado, enviado_em, importado_em, atualizado_em,
       tipo_regime
  from empresas
 where uf = 'MG'
   and situacao_cadastral = 'ATIVA'
   and opt_out = false
   and provavel_terceiro = false
   and email is not null
   and enviado = false;
