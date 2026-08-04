-- V004: add enviado and enviado_em columns to empresas, update vw_empresas_elegiveis
set search_path = mei_email, public;

alter table empresas
  add column enviado boolean not null default false,
  add column enviado_em timestamptz;

create index idx_empresas_enviado on empresas (enviado) where enviado = false;

-- Recreate view to exclude already sent companies
create or replace view vw_empresas_elegiveis as
select *
  from empresas
 where uf = 'MG'
   and situacao_cadastral = 'ATIVA'
   and opt_out = false
   and provavel_terceiro = false
   and email is not null
   and enviado = false;
