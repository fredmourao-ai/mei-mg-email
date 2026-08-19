-- V034: close the Graph-202/database-commit crash window without replaying mail.
--
-- The worker now persists `enviando` immediately before the external Graph
-- side effect. If the process dies after Exchange accepts the message but
-- before `submitted` is committed, recovery must not blindly return that row
-- to `pendente`, because doing so can deliver a duplicate. For rows carrying
-- the explicit dispatch checkpoint introduced with this migration, stale
-- recovery is therefore fail-closed: account the uncertain dispatch as
-- `submitted`. This is deliberately conservative: it can under-send one row
-- in the narrow crash-before-request window, but it never trades safety for a
-- duplicate commercial message.
set search_path = mei_email, public;

create or replace function mei_email.guard_uncertain_graph_dispatch_replay()
returns trigger language plpgsql as $$
begin
  if old.status::text = 'enviando'
     and new.status::text = 'pendente'
     and coalesce(old.erro, '') like 'dispatch_started:%'
     and coalesce(new.erro, '') like '%recuperado: envio preso em processamento%'
  then
    new.status := 'submitted'::mei_email.status_envio;
    new.enviado_em := coalesce(old.enviado_em, new.enviado_em, now());
    new.erro := 'delivery_uncertain: recuperacao anti-duplicidade assumiu submitted apos checkpoint pre-Graph';
  end if;
  return new;
end;
$$;

drop trigger if exists envios_guard_uncertain_graph_dispatch on mei_email.envios;
create trigger envios_guard_uncertain_graph_dispatch
  before update on mei_email.envios
  for each row execute function mei_email.guard_uncertain_graph_dispatch_replay();

-- `recuperar_lotes_travados` historically reopens the lot before the generic
-- queue recovery runs. Reconcile its explicitly checkpointed in-flight rows
-- first so reopening the lot cannot strand or later replay them.
create or replace function mei_email.guard_uncertain_graph_dispatch_on_lot_recovery()
returns trigger language plpgsql as $$
begin
  if old.status::text = 'processando'
     and new.status::text = 'pendente'
     and coalesce(new.erro, '') = 'recuperado automaticamente apos worker interrompido'
  then
    update mei_email.envios e
       set status = 'submitted'::mei_email.status_envio,
           enviado_em = coalesce(e.enviado_em, now()),
           erro = 'delivery_uncertain: lote interrompido apos checkpoint pre-Graph; assumido submitted para impedir replay'
     where e.lote_id = old.id
       and e.status::text = 'enviando'
       and coalesce(e.erro, '') like 'dispatch_started:%';
  end if;
  return new;
end;
$$;

drop trigger if exists lotes_guard_uncertain_graph_dispatch on mei_email.lotes;
create trigger lotes_guard_uncertain_graph_dispatch
  before update on mei_email.lotes
  for each row execute function mei_email.guard_uncertain_graph_dispatch_on_lot_recovery();

comment on function mei_email.guard_uncertain_graph_dispatch_replay() is
  'Prevents replay of a Graph dispatch whose external result is uncertain after a worker crash; only explicit dispatch_started checkpoints are affected.';
