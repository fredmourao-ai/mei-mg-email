-- V025: remove PII da base operacional apos envio/rejeicao e impede reimportacao.
--
-- Regra operacional solicitada:
--   * enviado/submitted: email e CNPJ originais saem de empresas/envios;
--   * rejeitado definitivamente pelo filtro: sai da base operacional;
--   * email/CNPJ suprimidos nunca podem ser reimportados;
--   * um ledger anonimo permanece em envios por no maximo 24h somente para
--     preservar a janela movel de rate limit do Microsoft 365.
set search_path = mei_email, public;

alter table mei_email.email_suppressions
    drop constraint if exists email_suppressions_scope_check;

alter table mei_email.email_suppressions
    add constraint email_suppressions_scope_check
    check (scope = any (array['email'::text, 'domain'::text, 'cnpj'::text]));

create or replace function mei_email.is_cnpj_suppressed(p_cnpj text)
returns boolean
language sql
stable
as $function$
  select exists(
    select 1
      from mei_email.email_suppressions s
     where s.active
       and s.scope = 'cnpj'
       and upper(btrim(s.value::text)) = upper(btrim(p_cnpj))
  );
$function$;

create or replace function mei_email.register_operational_suppression(
    p_cnpj text,
    p_email public.citext,
    p_reason text,
    p_source text default 'operational_retention',
    p_source_ref text default null,
    p_event_at timestamptz default now()
)
returns void
language plpgsql
as $function$
begin
  if p_email is not null and btrim(p_email::text) <> '' then
    insert into mei_email.email_suppressions
        (scope, value, reason, source, source_ref, active, created_at, updated_at)
    values
        ('email', lower(btrim(p_email::text))::public.citext, p_reason, p_source,
         p_source_ref, true, coalesce(p_event_at, now()), now())
    on conflict (scope, value) where active = true
    do update set
        reason = excluded.reason,
        source = excluded.source,
        source_ref = coalesce(excluded.source_ref, mei_email.email_suppressions.source_ref),
        updated_at = now();
  end if;

  if p_cnpj is not null and btrim(p_cnpj) <> '' then
    insert into mei_email.email_suppressions
        (scope, value, reason, source, source_ref, active, created_at, updated_at)
    values
        ('cnpj', upper(btrim(p_cnpj))::public.citext, p_reason, p_source,
         p_source_ref, true, coalesce(p_event_at, now()), now())
    on conflict (scope, value) where active = true
    do update set
        reason = excluded.reason,
        source = excluded.source,
        source_ref = coalesce(excluded.source_ref, mei_email.email_suppressions.source_ref),
        updated_at = now();
  end if;
end;
$function$;

create or replace function mei_email.operational_filter_rejection_reason(
    p_situacao text,
    p_uf text,
    p_email public.citext,
    p_opt_out boolean,
    p_provavel_terceiro boolean,
    p_marketing_autorizado boolean,
    p_tipo_regime text,
    p_mei_verificado boolean
)
returns text
language sql
immutable
as $function$
  select case
    when coalesce(p_opt_out, false) then 'opt_out'
    when coalesce(upper(btrim(p_situacao)), '') <> 'ATIVA' then 'filter_inactive'
    when coalesce(upper(btrim(p_uf)), '') <> 'MG' then 'filter_uf'
    when p_email is null or btrim(p_email::text) = '' then 'filter_email_missing'
    when coalesce(p_provavel_terceiro, false) then 'filter_third_party'
    when not coalesce(p_marketing_autorizado, false) then 'filter_marketing_not_authorized'
    when coalesce(upper(btrim(p_tipo_regime)), '') <> 'MEI' then 'filter_not_mei'
    when not coalesce(p_mei_verificado, false) then 'filter_mei_not_verified'
    else null
  end;
$function$;

create or replace function mei_email.trg_block_suppressed_or_rejected_insert()
returns trigger
language plpgsql
as $function$
declare
  rejection text;
begin
  -- Este trigger usa prefixo zz para executar depois da politica de importacao
  -- V023, que preenche os flags de autorizacao/verificacao no BEFORE INSERT.
  if mei_email.is_cnpj_suppressed(new.cnpj::text)
     or (new.email is not null and mei_email.is_email_suppressed(new.email)) then
    return null;
  end if;

  rejection := mei_email.operational_filter_rejection_reason(
      new.situacao_cadastral,
      new.uf,
      new.email,
      new.opt_out,
      new.provavel_terceiro,
      new.marketing_autorizado,
      new.tipo_regime,
      new.mei_verificado
  );

  if rejection is not null then
    perform mei_email.register_operational_suppression(
        new.cnpj::text, new.email, rejection, 'insert_filter_gate', null, now()
    );
    return null;
  end if;

  return new;
end;
$function$;

drop trigger if exists zz_empresas_block_suppressed_or_rejected_insert on mei_email.empresas;
create trigger zz_empresas_block_suppressed_or_rejected_insert
before insert on mei_email.empresas
for each row execute function mei_email.trg_block_suppressed_or_rejected_insert();

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
      new.marketing_autorizado,
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

    delete from mei_email.envios e
     where btrim(e.cnpj::text) = btrim(new.cnpj::text)
        or (new.email is not null and lower(btrim(e.email::text)) = lower(btrim(new.email::text)));

    delete from mei_email.empresas e
     where e.cnpj = new.cnpj;
  end if;

  return null;
end;
$function$;

drop trigger if exists zz_empresas_purge_rejected_after_update on mei_email.empresas;
create trigger zz_empresas_purge_rejected_after_update
after update on mei_email.empresas
for each row execute function mei_email.trg_purge_rejected_company_update();

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

    -- Remove qualquer duplicata operacional ainda pendente para o mesmo alvo.
    delete from mei_email.envios e
     where e.id <> new.id
       and (
         btrim(e.cnpj::text) = original_cnpj
         or lower(btrim(e.email::text)) = lower(btrim(original_email::text))
       );

    delete from mei_email.empresas e
     where btrim(e.cnpj::text) = original_cnpj
        or lower(btrim(e.email::text)) = lower(btrim(original_email::text));

    -- Mantem apenas um ledger anonimo por ate 24h para os contadores de quota.
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

    delete from mei_email.envios e
     where e.email::text like 'quota+%@invalid.local'
       and e.enviado_em < now() - interval '24 hours';

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

    delete from mei_email.envios e
     where btrim(e.cnpj::text) = original_cnpj
        or lower(btrim(e.email::text)) = lower(btrim(original_email::text));

    delete from mei_email.empresas e
     where btrim(e.cnpj::text) = original_cnpj
        or lower(btrim(e.email::text)) = lower(btrim(original_email::text));
  end if;

  return new;
end;
$function$;

drop trigger if exists zz_envios_archive_and_purge_pii on mei_email.envios;
create trigger zz_envios_archive_and_purge_pii
after update of status on mei_email.envios
for each row
when (old.status is distinct from new.status)
execute function mei_email.trg_archive_envio_and_purge_pii();

-- A view final tambem bloqueia CNPJ suprimido e terceiro provavel.
create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and upper(e.uf) = 'MG'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.marketing_autorizado = true
   and e.enviado = false
   and e.tipo_regime = 'MEI'
   and e.mei_verificado = true
   and not mei_email.is_email_suppressed(e.email)
   and not mei_email.is_cnpj_suppressed(e.cnpj::text)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status::text in ('pendente', 'enviando', 'pending', 'processing', 'submitted', 'enviado', 'delivered')
   );

comment on view mei_email.vw_empresas_elegiveis is
  'Base operacional enxuta: somente MEI/MG ativo, verificado, autorizado, nao terceiro, sem opt-out/supressao e ainda nao comprometido na fila.';
