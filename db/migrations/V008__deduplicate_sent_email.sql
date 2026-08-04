-- V008: impede novo envio para o mesmo endereco de e-mail, mesmo em CNPJs distintos.
set search_path = mei_email, public;

create index if not exists idx_empresas_email_enviado
  on empresas (email)
  where enviado = true and email is not null;

drop view if exists vw_empresas_elegiveis;

create view vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime
  from empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and e.enviado = false
   and not exists (
     select 1
       from empresas ja_contatada
      where ja_contatada.email = e.email
        and ja_contatada.enviado = true
   );
