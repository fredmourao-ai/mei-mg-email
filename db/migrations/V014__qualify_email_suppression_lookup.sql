-- V014: qualifica referencias para evitar dependencia implícita de search_path.
set search_path = mei_email, public;

create or replace function mei_email.is_email_suppressed(p_email citext)
returns boolean
language sql
stable
as $$
  select exists(
    select 1
      from mei_email.email_suppressions s
     where s.active
       and (
         (s.scope = 'email' and lower(btrim(s.value::text)) = lower(btrim(p_email::text)))
         or
         (s.scope = 'domain' and lower(btrim(s.value::text)) = split_part(lower(btrim(p_email::text)), '@', 2))
       )
  );
$$;

create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.marketing_autorizado = true
   and e.enviado = false
   and not mei_email.is_email_suppressed(e.email)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status in ('pending', 'processing', 'submitted', 'delivered')
   );
