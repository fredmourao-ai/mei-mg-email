-- V018: acelera a checagem da janela movel de 24h executada pelo worker antes de cada envio.
-- Usa nome v2 para nao reaproveitar um indice concorrente antigo que possa ter ficado invalido.
set search_path = mei_email, public;

create index if not exists idx_envios_enviado_em_v2
  on envios (enviado_em)
  where enviado_em is not null;
