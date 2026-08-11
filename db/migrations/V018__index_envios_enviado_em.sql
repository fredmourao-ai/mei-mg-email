-- V018: acelera a checagem da janela movel de 24h executada pelo worker antes de cada envio.
set search_path = mei_email, public;

create index if not exists idx_envios_enviado_em
  on envios (enviado_em)
  where enviado_em is not null;
