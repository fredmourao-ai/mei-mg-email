-- V030: indice compacto para a janela movel de 24h do worker.
set search_path = mei_email, public;

create index if not exists idx_envios_quota_24h
    on mei_email.envios (enviado_em)
    where enviado_em is not null
      and status in ('submitted', 'enviado');

comment on index mei_email.idx_envios_quota_24h is
  'Janela movel de envios submetidos/enviados usada para o teto operacional de 24h.';
