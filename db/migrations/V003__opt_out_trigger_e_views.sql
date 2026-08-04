-- V003: descadastro efetivo (propaga pra empresas.opt_out automaticamente) e
-- uma view de "empresas elegíveis" que a API usa pra montar campanhas, pra
-- não espalhar a mesma regra de filtro em múltiplos lugares do código.
set search_path = mei_email, public;

create or replace function mei_email.trg_aplicar_opt_out()
returns trigger language plpgsql as $$
begin
  if new.cnpj is not null then
    update empresas
       set opt_out = true,
           opt_out_em = now(),
           opt_out_motivo = coalesce(opt_out_motivo, new.origem)
     where cnpj = new.cnpj
       and opt_out = false;
  else
    -- Descadastro só com e-mail (ex: veio de um link sem CNPJ no token):
    -- aplica em todos os CNPJs que usam esse e-mail.
    update empresas
       set opt_out = true,
           opt_out_em = now(),
           opt_out_motivo = coalesce(opt_out_motivo, new.origem)
     where email = new.email
       and opt_out = false;
  end if;
  return new;
end;
$$;

create trigger descadastros_aplica_opt_out
  after insert on descadastros
  for each row execute function mei_email.trg_aplicar_opt_out();

create or replace view vw_empresas_elegiveis as
select *
  from empresas
 where uf = 'MG'
   and situacao_cadastral = 'ATIVA'
   and opt_out = false
   and provavel_terceiro = false
   and email is not null;

comment on view vw_empresas_elegiveis is
  'Fonte unica de verdade pra quem pode entrar em campanha nova. A API de criar campanha deve sempre consultar essa view, nunca a tabela empresas direto, pra nao esquecer nenhum filtro de compliance.';
