-- V014: prepara o pipeline para CNPJ alfanumerico e consolida a semantica Graph submitted.
set search_path = mei_email, public;

-- Desde julho/2026 novas inscricoes podem usar letras nas 12 primeiras posicoes.
-- Os dois ultimos caracteres continuam sendo digitos verificadores numericos.
alter table empresas drop constraint if exists empresas_cnpj_check;
alter table empresas
  add constraint empresas_cnpj_check
  check (upper(btrim(cnpj::text)) ~ '^[0-9A-Z]{12}[0-9]{2}$');

create index if not exists idx_envios_cnpj on envios (cnpj);

-- Repara o historico: para Graph, HTTP 202 e persistido como submitted e ja
-- representa uma submissao que nao pode ser novamente enfileirada.
update empresas e
   set enviado = true,
       enviado_em = coalesce(e.enviado_em, h.ultimo_envio)
  from (
    select cnpj, max(enviado_em) as ultimo_envio
      from envios
     where status::text in ('submitted', 'enviado')
     group by cnpj
  ) h
 where e.cnpj = h.cnpj
   and (not e.enviado or e.enviado_em is null);

-- Mantem empresas.enviado coerente para todas as futuras transicoes para
-- submitted/enviado, independentemente do provedor ou do codigo do worker.
create or replace function mei_email.trg_marcar_empresa_submetida()
returns trigger language plpgsql as $$
begin
  if new.status::text in ('submitted', 'enviado') then
    update mei_email.empresas e
       set enviado = true,
           enviado_em = coalesce(e.enviado_em, new.enviado_em, now())
     where e.cnpj = new.cnpj
        or lower(btrim(e.email::text)) = lower(btrim(new.email::text));
  end if;
  return new;
end;
$$;

drop trigger if exists envios_marcar_empresa_submetida on envios;
create trigger envios_marcar_empresa_submetida
  after insert or update on envios
  for each row execute function mei_email.trg_marcar_empresa_submetida();

-- Elegibilidade continua fail-closed por autorizacao, mas uma linha antiga
-- bloqueada/falha nao condena para sempre um cadastro que posteriormente se
-- torne legitimamente elegivel. O bloqueio historico definitivo e para
-- submitted/enviado/bounced e para itens atualmente comprometidos na fila.
create or replace view vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem
  from empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.enviado = false
   and e.marketing_autorizado = true
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
  'Fonte fail-closed: ativa, sem opt-out/terceiro, autorizada, sem fila atual e sem submissao/entrega/bounce anterior pelo CNPJ ou e-mail normalizado.';
