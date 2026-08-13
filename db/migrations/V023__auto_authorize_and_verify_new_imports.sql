-- V023: politica operacional para novos registros importados.
--
-- Toda nova linha inserida em empresas recebe os dois flags solicitados pelo
-- operador. As origens deixam claro que a autorizacao/verificacao resultam da
-- politica operacional, e nao de um claim de consentimento da fonte publica.
-- Opt-out continua sendo um campo independente e permanece soberano na view e
-- no worker.
set search_path = mei_email, public;

create or replace function mei_email.trg_aplicar_politica_importacao_operador()
returns trigger language plpgsql as $$
begin
  new.marketing_autorizado := true;
  new.marketing_autorizado_em := coalesce(new.marketing_autorizado_em, now());
  new.marketing_autorizado_origem := coalesce(
      nullif(btrim(new.marketing_autorizado_origem), ''),
      'politica_importacao_operador_2026-08-13'
  );

  new.mei_verificado := true;
  new.mei_verificado_em := coalesce(new.mei_verificado_em, now());
  new.mei_verificado_origem := coalesce(
      nullif(btrim(new.mei_verificado_origem), ''),
      'politica_importacao_operador_2026-08-13'
  );
  return new;
end;
$$;

drop trigger if exists empresas_aplicar_politica_importacao_operador on empresas;
create trigger empresas_aplicar_politica_importacao_operador
  before insert on empresas
  for each row execute function mei_email.trg_aplicar_politica_importacao_operador();

comment on function mei_email.trg_aplicar_politica_importacao_operador() is
  'Politica do operador de 2026-08-13: novos registros entram marketing_autorizado=true e mei_verificado=true com origem auditavel. Opt-out nao e alterado.';
