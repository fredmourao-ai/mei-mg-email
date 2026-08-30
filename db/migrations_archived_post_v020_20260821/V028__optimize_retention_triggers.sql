-- V028: remove scans amplos do caminho critico do worker.
-- Mantem a mesma politica V025 (supressao + purge operacional + ledger anonimo),
-- mas substitui ORs com funcoes por operacoes separadas/indexaveis.
set search_path = mei_email, public;

create or replace function mei_email.trg_purge_rejected_company_update()
returns trigger
language plpgsql
as $function$
declare
  rejection text;
begin
  rejection := mei_email.operational_filter_rejection_reason(
      new.situacao_cadastral,
      new.uf,
      new.email,
      new.opt_out,
      new.provavel_terceiro,
      new.campo_autorizacao_legado,
      new.tipo_regime,
      new.mei_verificado
  );

  if mei_email.is_cnpj_suppressed(new.cnpj::text)
     or (new.email is not null and mei_email.is_email_suppressed(new.email)) then
    rejection := coalesce(rejection, 'already_suppressed');
  end if;

  if rejection is not null then
    perform mei_email.register_operational_suppression(
        new.cnpj::text, new.email, rejection, 'update_filter_gate', null, now()
    );

    -- CNPJ possui indice dedicado/PK: remove primeiro o alvo operacional exato.
    delete from mei_email.envios e
     where e.cnpj = new.cnpj;

    -- Remove duplicatas de fila pelo email em uma instrucao separada para o
    -- indice de expressao idx_envios_email_normalizado poder ser usado.
    if new.email is not null then
      delete from mei_email.envios e
       where lower(btrim(e.email::text)) = lower(btrim(new.email::text));
    end if;

    -- Outras empresas que compartilhem email ficam inelegiveis pela supressao;
    -- nao varremos empresas por email dentro do trigger.
    delete from mei_email.empresas e
     where e.cnpj = new.cnpj;
  end if;

  return null;
end;
$function$;

create or replace function mei_email.trg_archive_envio_and_purge_pii()
returns trigger
language plpgsql
as $function$
declare
  status_text text := new.status::text;
  original_email public.citext := new.email;
  original_cnpj text := btrim(new.cnpj::text);
  ledger_email public.citext;
  ledger_cnpj text;
  suppression_reason text;
begin
  if pg_trigger_depth() > 1 then
    return new;
  end if;

  if status_text in ('submitted', 'enviado', 'delivered') then
    suppression_reason := 'sent';
    perform mei_email.register_operational_suppression(
        original_cnpj,
        original_email,
        suppression_reason,
        'worker_send_success',
        new.id::text,
        coalesce(new.enviado_em, now())
    );

    -- Remove duplicatas por CNPJ usando indice, preservando a linha atual que
    -- sera convertida em ledger anonimo para a cota movel de 24 horas.
    delete from mei_email.envios e
     where e.id <> new.id
       and e.cnpj::text = original_cnpj;

    -- Remove duplicatas por email em instrucao separada; a expressao coincide
    -- com idx_envios_email_normalizado.
    if original_email is not null then
      delete from mei_email.envios e
       where e.id <> new.id
         and lower(btrim(e.email::text)) = lower(btrim(original_email::text));
    end if;

    -- A empresa original sai da base operacional pela chave primaria.
    delete from mei_email.empresas e
     where e.cnpj::text = original_cnpj;

    -- Mantem somente o ledger anonimo necessario ao limite movel.
    ledger_email := ('quota+' || replace(new.id::text, '-', '') || '@invalid.local')::public.citext;
    ledger_cnpj := upper(substr(replace(new.id::text, '-', ''), 1, 14));

    update mei_email.envios
       set email = ledger_email,
           cnpj = ledger_cnpj,
           erro = case
             when erro is null or erro = '' then 'PII_PURGED_RATE_LEDGER'
             else erro || ' | PII_PURGED_RATE_LEDGER'
           end
     where id = new.id;

    -- A limpeza de ledgers expirados nao roda a cada envio; veja a funcao
    -- cleanup_expired_quota_ledgers abaixo.
    return new;
  end if;

  if status_text in (
      'opt_out', 'bloqueado', 'descartado', 'bounced',
      'bounce_permanent', 'bounce_temporary'
  ) then
    suppression_reason := case
      when status_text = 'opt_out' then 'opt_out'
      when status_text in ('bounced', 'bounce_permanent') then 'hard_bounce'
      when status_text = 'bounce_temporary' then 'temporary_bounce_suppressed'
      when status_text = 'descartado' then 'deduplicated'
      else 'filter_rejected'
    end;

    perform mei_email.register_operational_suppression(
        original_cnpj,
        original_email,
        suppression_reason,
        'worker_rejection',
        new.id::text,
        now()
    );

    -- A linha atual e duplicatas do mesmo CNPJ sao operacionais e podem sair.
    delete from mei_email.envios e
     where e.cnpj::text = original_cnpj;

    if original_email is not null then
      delete from mei_email.envios e
       where lower(btrim(e.email::text)) = lower(btrim(original_email::text));
    end if;

    delete from mei_email.empresas e
     where e.cnpj::text = original_cnpj;
  end if;

  return new;
end;
$function$;

create or replace function mei_email.cleanup_expired_quota_ledgers(p_limit integer default 2000)
returns integer
language plpgsql
as $function$
declare
  removed integer;
begin
  if p_limit is null or p_limit < 1 or p_limit > 10000 then
    raise exception 'p_limit precisa estar entre 1 e 10000';
  end if;

  with expired as (
    select id
      from mei_email.envios
     where enviado_em < now() - interval '24 hours'
       and email::text like 'quota+%@invalid.local'
     order by enviado_em
     limit p_limit
  )
  delete from mei_email.envios e
   using expired x
   where e.id = x.id;

  get diagnostics removed = row_count;
  return removed;
end;
$function$;

comment on function mei_email.cleanup_expired_quota_ledgers(integer) is
  'Limpa ledgers anonimos de cota expirados em lotes; executar fora do caminho critico de cada envio.';
