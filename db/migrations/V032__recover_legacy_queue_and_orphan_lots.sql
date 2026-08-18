-- Recover queue rows left under legacy English labels and reopen lots that
-- were incorrectly marked completed while they still contained open work.
-- Idempotent: rerunning leaves a normalized queue unchanged.
set search_path = mei_email, public;

update envios
   set status = 'pendente',
       erro = case
           when coalesce(erro, '') = '' then
               'recuperado V032: estado legado normalizado'
           else erro || ' | recuperado V032: estado legado normalizado'
       end
 where status in ('pending', 'processing');

update envios e
   set status = 'pendente',
       erro = case
           when coalesce(e.erro, '') = '' then
               'recuperado V032: processamento interrompido'
           else e.erro || ' | recuperado V032: processamento interrompido'
       end
  from lotes l
 where l.id = e.lote_id
   and e.status = 'enviando'
   and l.status = 'processando'
   and l.iniciado_em < now() - interval '15 minutes';

update lotes l
   set status = 'pendente',
       iniciado_em = null,
       concluido_em = null,
       erro = case
           when coalesce(l.erro, '') = '' then
               'recuperado V032: lote continha envios abertos'
           else l.erro || ' | recuperado V032: lote continha envios abertos'
       end
 where l.status <> 'pendente'
   and exists (
       select 1
         from envios e
        where e.lote_id = l.id
          and e.status in ('pendente', 'enviando', 'pending', 'processing')
   );

create index if not exists idx_envios_open_queue_lote
    on envios (lote_id, criado_em, id)
 where status in ('pendente', 'enviando', 'pending', 'processing');

create index if not exists idx_lotes_open_queue
    on lotes (criado_em, numero, id)
 where status = 'pendente';

analyze empresas;
analyze envios;
analyze lotes;
