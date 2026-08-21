-- V047: fail closed for legacy numeric CNPJs that are unequivocally filiais.
--
-- Under the legacy numeric CNPJ format, establishment order 0001 identifies
-- the matriz and 0002+ identifies a filial. A MEI cannot have/open a filial.
-- Therefore a legacy numeric CNPJ whose establishment order is not 0001
-- cannot remain mei_verificado=true, regardless of a stale/imported label.
--
-- This migration does not grant marketing consent, does not clear opt-out or
-- suppressions, and does not reopen terminal send history. It only invalidates
-- impossible MEI verification and discards never-dispatched open queue rows.
set search_path = mei_email, public;

create or replace function mei_email.trg_reject_legacy_numeric_mei_filial()
returns trigger language plpgsql as $$
declare
  v_cnpj text := upper(regexp_replace(btrim(new.cnpj::text), '[^0-9A-Z]', '', 'g'));
  v_guard text := 'invalidated_legacy_numeric_filial_mei_guard_2026-08-21';
begin
  if v_cnpj ~ '^[0-9]{14}$'
     and substring(v_cnpj from 9 for 4) <> '0001' then
    new.mei_verificado := false;
    new.mei_verificado_em := now();
    if position(v_guard in coalesce(new.mei_verificado_origem, '')) = 0 then
      new.mei_verificado_origem := concat_ws(
        '|', nullif(btrim(new.mei_verificado_origem), ''), v_guard
      );
    end if;
  end if;
  return new;
end;
$$;

update mei_email.empresas e
   set mei_verificado = false,
       mei_verificado_em = now(),
       mei_verificado_origem = case
         when position(
           'invalidated_legacy_numeric_filial_mei_guard_2026-08-21'
           in coalesce(e.mei_verificado_origem, '')
         ) > 0 then e.mei_verificado_origem
         else concat_ws(
           '|',
           nullif(btrim(e.mei_verificado_origem), ''),
           'invalidated_legacy_numeric_filial_mei_guard_2026-08-21'
         )
       end
 where upper(regexp_replace(btrim(e.cnpj::text), '[^0-9A-Z]', '', 'g')) ~ '^[0-9]{14}$'
   and substring(
         upper(regexp_replace(btrim(e.cnpj::text), '[^0-9A-Z]', '', 'g'))
         from 9 for 4
       ) <> '0001'
   and e.mei_verificado = true;

update mei_email.envios x
   set status = 'descartado'::mei_email.status_envio,
       erro = concat_ws(
         ' | ',
         nullif(btrim(x.erro), ''),
         'V047: CNPJ numerico de filial e incompativel com MEI; descartado antes do envio'
       )
  from mei_email.empresas e
 where e.cnpj = x.cnpj
   and upper(regexp_replace(btrim(e.cnpj::text), '[^0-9A-Z]', '', 'g')) ~ '^[0-9]{14}$'
   and substring(
         upper(regexp_replace(btrim(e.cnpj::text), '[^0-9A-Z]', '', 'g'))
         from 9 for 4
       ) <> '0001'
   and x.status::text in ('pendente', 'enviando', 'pending', 'processing');

drop trigger if exists empresas_reject_legacy_numeric_mei_filial on mei_email.empresas;
create trigger empresas_reject_legacy_numeric_mei_filial
  before insert or update of cnpj, mei_verificado, mei_verificado_origem
  on mei_email.empresas
  for each row execute function mei_email.trg_reject_legacy_numeric_mei_filial();

comment on function mei_email.trg_reject_legacy_numeric_mei_filial() is
  'Fail-closed: legacy numeric CNPJ de filial nao pode permanecer MEI verificado; preserva trilha da origem invalidada.';
