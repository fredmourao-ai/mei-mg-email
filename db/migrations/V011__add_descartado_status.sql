-- V011: registra envios descartados por duplicidade excessiva.
set search_path = mei_email, public;

do $$
begin
  alter type status_envio add value 'descartado';
exception
  when duplicate_object then null;
end
$$;
