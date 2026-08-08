-- V010: prioriza lotes criados pela sincronizacao de novas inclusoes.
set search_path = mei_email, public;

alter table lotes
  add column if not exists prioridade_data timestamptz;

create index if not exists idx_lotes_fila_prioridade
  on lotes (status, prioridade_data desc, criado_em)
  where status = 'pendente';

create index if not exists idx_envios_cnpj
  on envios (cnpj);

create index if not exists idx_envios_email
  on envios (email);
