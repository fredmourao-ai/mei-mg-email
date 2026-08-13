-- Callback idempotente recuperado do estado real de producao em 2026-08-13.
--
-- O enum base e criado pela V002. Antes das migrations seguintes, garanta os
-- labels que ja existiam na producao quando a V019 foi aplicada. O callback
-- nao cria o tipo antecipadamente e nao altera checksums das migrations.

do $$
begin
  if exists (
    select 1
      from pg_type t
      join pg_namespace n on n.oid = t.typnamespace
     where n.nspname = 'mei_email'
       and t.typname = 'status_envio'
  ) then
    alter type mei_email.status_envio add value if not exists 'descartado';
    alter type mei_email.status_envio add value if not exists 'submitted';
    alter type mei_email.status_envio add value if not exists 'sender_blocked';
    alter type mei_email.status_envio add value if not exists 'bloqueado';
    alter type mei_email.status_envio add value if not exists 'delivered';
    alter type mei_email.status_envio add value if not exists 'bounce_permanent';
    alter type mei_email.status_envio add value if not exists 'bounce_temporary';
    alter type mei_email.status_envio add value if not exists 'suppressed';
    alter type mei_email.status_envio add value if not exists 'cancelled';
    alter type mei_email.status_envio add value if not exists 'pending';
    alter type mei_email.status_envio add value if not exists 'processing';
    alter type mei_email.status_envio add value if not exists 'failed';
  end if;
end
$$;
