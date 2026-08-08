-- V015: trilha auditavel das sincronizacoes da base de CNPJ.
set search_path = mei_email, public;

create table if not exists base_sync_runs (
  id                 bigserial primary key,
  source_name        text not null,
  source_revision    text,
  source_last_modified timestamptz,
  status             text not null check (status in ('running','success','no_change','source_stale','failed')),
  started_at         timestamptz not null default now(),
  finished_at        timestamptz,
  rows_before        bigint,
  rows_after         bigint,
  rows_added         bigint,
  details            jsonb not null default '{}'::jsonb,
  error              text
);

create index if not exists idx_base_sync_runs_source_started
  on base_sync_runs (source_name, started_at desc);

create index if not exists idx_base_sync_runs_success_revision
  on base_sync_runs (source_name, source_revision, finished_at desc)
  where status in ('success','no_change','source_stale');

comment on table base_sync_runs is
  'Auditoria de cada verificacao/sincronizacao da fonte de CNPJ. Permite provar execucao diaria e diferenciar fonte sem mudanca de falha de ingestao.';
