-- V026: remove o sequential scan recorrente do enfileirador.
-- O cron consulta pendente/enviando a cada 10 minutos; sem indice de status,
-- cada contador relia toda a tabela envios.
set search_path = mei_email, public;

create index if not exists idx_envios_status
    on mei_email.envios (status);

analyze mei_email.envios;
