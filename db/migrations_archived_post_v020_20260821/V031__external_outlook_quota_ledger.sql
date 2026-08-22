-- V031: ledger de cota para envios comprovados fora de mei_email.envios.
--
-- Alguns envios podem ser submetidos pelo Outlook/Graph fora da fila do worker,
-- mas ainda consomem reputacao e janela movel do mesmo remetente. Esta tabela
-- registra esses envios de forma auditavel sem quebrar as FKs de envios, que
-- exigem campanha/lote/cnpj.
set search_path = mei_email, public;

create table if not exists envios_externos_cota (
  id                  uuid primary key default gen_random_uuid(),
  email               citext not null,
  subject             text not null,
  sent_at             timestamptz not null,
  source              text not null default 'outlook_reconciliation',
  provider_message_id text,
  metadata            jsonb not null default '{}'::jsonb,
  criado_em           timestamptz not null default now(),

  constraint envios_externos_cota_provider_unique unique (provider_message_id)
);

create index if not exists idx_envios_externos_cota_sent_at
  on envios_externos_cota (sent_at);

create index if not exists idx_envios_externos_cota_email_normalizado
  on envios_externos_cota (lower(btrim(email::text)));

comment on table envios_externos_cota is
  'Envios comprovados no Outlook/Graph fora da fila envios; usados na cota movel do remetente.';
