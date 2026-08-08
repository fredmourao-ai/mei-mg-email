-- Normalize delivery-state semantics used by Microsoft Graph/Exchange.
-- HTTP 202 is only submission acceptance; it is never positive delivery proof.
set search_path = mei_email, public;

alter type status_envio add value if not exists 'submitted';
alter type status_envio add value if not exists 'sender_blocked';
alter type status_envio add value if not exists 'bloqueado';
alter type status_envio add value if not exists 'descartado';

comment on type status_envio is
  'pendente/enviando = queue lifecycle; submitted = Graph/Exchange accepted for processing; enviado = positively reconciled delivery; sender_blocked/bounced/falhou = failure classes; bloqueado/opt_out/descartado = local suppression classes';
