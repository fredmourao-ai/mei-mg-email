-- V002: campanhas de disparo, fila de lotes (batches de 100) e envios individuais.
-- A fila é a própria tabela `lotes`, consumida via SELECT ... FOR UPDATE SKIP
-- LOCKED pelo worker. Isso evita depender de Redis/RabbitMQ nessa primeira
-- versão, mas o desenho (lote isolado, status, tentativas) migra fácil pra
-- uma fila de verdade depois se o volume justificar.
set search_path = mei_email, public;

create type status_campanha as enum (
  'rascunho', 'enfileirada', 'em_andamento', 'pausada', 'concluida', 'cancelada'
);

create type status_lote as enum (
  'pendente', 'processando', 'concluido', 'falhou'
);

create type status_envio as enum (
  'pendente', 'enviando', 'enviado', 'falhou', 'bounced', 'opt_out'
);

create table campanhas (
  id                uuid primary key default gen_random_uuid(),
  nome              text not null,
  assunto           text not null,
  corpo_template    text not null,       -- suporta {{razao_social}}, {{municipio}}, {{cnpj}}
  filtro_municipio  text,                -- opcional: null = todos os municipios de MG
  filtro_cnae       text,                -- opcional: prefixo de CNAE
  tamanho_lote      integer not null default 100 check (tamanho_lote > 0),
  status            status_campanha not null default 'rascunho',
  total_empresas    integer not null default 0,
  total_enviados    integer not null default 0,
  total_falhas      integer not null default 0,
  criado_em         timestamptz not null default now(),
  iniciado_em       timestamptz,
  concluido_em      timestamptz
);

create table lotes (
  id                uuid primary key default gen_random_uuid(),
  campanha_id       uuid not null references campanhas(id) on delete cascade,
  numero            integer not null,
  status            status_lote not null default 'pendente',
  tamanho           integer not null,
  tentativas        integer not null default 0,
  criado_em         timestamptz not null default now(),
  iniciado_em       timestamptz,
  concluido_em      timestamptz,
  erro              text,

  constraint lote_numero_unico unique (campanha_id, numero)
);

create table envios (
  id                uuid primary key default gen_random_uuid(),
  campanha_id       uuid not null references campanhas(id) on delete cascade,
  lote_id           uuid not null references lotes(id) on delete cascade,
  cnpj              char(14) not null references empresas(cnpj),
  email             citext not null,
  status            status_envio not null default 'pendente',
  tentativas        integer not null default 0,
  provider_message_id text,
  enviado_em        timestamptz,
  erro              text,
  criado_em         timestamptz not null default now(),

  -- Um CNPJ só pode ser alvo de um envio por campanha (evita duplicidade se
  -- a fila for reprocessada).
  constraint envio_unico_por_campanha unique (campanha_id, cnpj)
);

create index idx_lotes_fila on lotes (status, criado_em) where status = 'pendente';
create index idx_envios_lote on envios (lote_id, status);
create index idx_envios_campanha_status on envios (campanha_id, status);

-- Tabela de descadastro: registra o pedido mesmo antes de termos um provedor
-- de e-mail real conectado (o link de descadastro no template já pode
-- apontar pra cá). Fica separada de `empresas.opt_out` pra manter o
-- historico de pedidos (uma empresa pode, em teoria, pedir mais de uma vez
-- por canais diferentes).
create table descadastros (
  id            uuid primary key default gen_random_uuid(),
  cnpj          char(14) references empresas(cnpj),
  email         citext not null,
  campanha_id   uuid references campanhas(id),
  origem        text not null default 'link_email', -- link_email, manual, bounce_hard
  criado_em     timestamptz not null default now()
);

create index idx_descadastros_cnpj on descadastros (cnpj);
