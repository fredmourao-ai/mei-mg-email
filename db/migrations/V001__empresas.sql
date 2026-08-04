-- V001: tabela principal de empresas (MEIs de MG extraídos do CNPJ da Receita)
set search_path = mei_email, public;

create table empresas (
  cnpj                  char(14) primary key check (cnpj ~ '^[0-9]{14}$'),
  razao_social           text,
  nome_fantasia          text,
  situacao_cadastral     text not null,   -- ATIVA, BAIXADA, SUSPENSA, INAPTA, NULA
  cnae                   text,
  cnae_descricao         text,
  municipio              text,
  uf                     char(2) not null check (uf ~ '^[A-Z]{2}$'),
  cep                    char(8),
  email                  citext,
  ddd_1                  varchar(3),
  telefone_1             varchar(15),
  data_abertura          date,

  -- Regra de limpeza: e-mail repetido em mais de 3 CNPJs diferentes é
  -- provavelmente um contador/escritório de contabilidade compartilhado,
  -- não o e-mail direto do MEI. Não deletamos o dado (fica auditável), só
  -- marcamos pra excluir do disparo direto (ver script de ingestão).
  provavel_terceiro     boolean not null default false,

  -- LGPD / anti-spam: opt-out por CNPJ. Uma vez true, nunca mais deve
  -- entrar em nenhuma campanha nova, independente de e-mail.
  opt_out                boolean not null default false,
  opt_out_em             timestamptz,
  opt_out_motivo         text,

  importado_em           timestamptz not null default now(),
  atualizado_em          timestamptz not null default now()
);

comment on column empresas.provavel_terceiro is
  'true quando o mesmo e-mail aparece em mais de 3 CNPJs distintos na importacao (heuristica de contador/terceiro). Excluido da selecao de campanhas por padrao.';

comment on column empresas.opt_out is
  'true quando o CNPJ/e-mail pediu descadastro. Checagem obrigatoria antes de qualquer novo envio.';

create index idx_empresas_uf_situacao on empresas (uf, situacao_cadastral);
create index idx_empresas_email on empresas (email);
create index idx_empresas_elegiveis on empresas (uf, opt_out, provavel_terceiro)
  where email is not null;
create index idx_empresas_razao_social_trgm on empresas using gin (razao_social gin_trgm_ops);

create or replace function mei_email.trg_set_atualizado_em()
returns trigger language plpgsql as $$
begin
  new.atualizado_em := now();
  return new;
end;
$$;

create trigger empresas_atualizado_em
  before update on empresas
  for each row execute function mei_email.trg_set_atualizado_em();
