-- Completes the delivery-status vocabulary after historical V012/V013 drift.
set search_path = mei_email, public;

alter type status_envio add value if not exists 'pending';
alter type status_envio add value if not exists 'processing';
alter type status_envio add value if not exists 'submitted';
alter type status_envio add value if not exists 'delivered';
alter type status_envio add value if not exists 'bounce_temporary';
alter type status_envio add value if not exists 'bounce_permanent';
alter type status_envio add value if not exists 'sender_blocked';
alter type status_envio add value if not exists 'suppressed';
alter type status_envio add value if not exists 'cancelled';
alter type status_envio add value if not exists 'failed';
