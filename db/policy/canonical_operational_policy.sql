BEGIN;
SET search_path = mei_email, public;

DROP EVENT TRIGGER IF EXISTS mei_email_policy_ddl_guard;
DROP TRIGGER IF EXISTS zz_empresas_block_suppressed_or_rejected_insert ON mei_email.empresas;
DROP TRIGGER IF EXISTS zz_empresas_purge_rejected_after_update ON mei_email.empresas;
DROP FUNCTION IF EXISTS mei_email.trg_archive_envio_and_purge_pii();

CREATE OR REPLACE FUNCTION mei_email.operational_filter_rejection_reason(
    p_situacao text,
    p_uf text,
    p_email public.citext,
    p_opt_out boolean,
    p_provavel_terceiro boolean,
    p_marketing_autorizado boolean,
    p_tipo_regime text,
    p_mei_verificado boolean
) RETURNS text
LANGUAGE sql IMMUTABLE
AS $function$
  SELECT CASE
    WHEN coalesce(p_opt_out,false) THEN 'opt_out'
    WHEN coalesce(upper(btrim(p_situacao)),'') <> 'ATIVA' THEN 'filter_inactive'
    WHEN p_email IS NULL OR btrim(p_email::text)='' THEN 'filter_email_missing'
    WHEN NOT mei_email.is_valid_email_address(p_email) THEN 'filter_email_invalid'
    WHEN position('contabil' in lower(btrim(p_email::text))) > 0 THEN 'filter_email_contabil'
    ELSE NULL
  END;
$function$;

CREATE OR REPLACE FUNCTION mei_email.enforce_envio_live_eligibility()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'mei_email','public'
AS $function$
DECLARE
  ok_live boolean;
  already_used boolean;
BEGIN
  IF NEW.status::text NOT IN ('pendente','enviando','pending','processing') THEN
    RETURN NEW;
  END IF;
  IF TG_OP='UPDATE' AND OLD.status::text IN
     ('submitted','enviado','delivered','bounced','bounce_permanent') THEN
    NEW.status := 'bloqueado'::mei_email.status_envio;
    NEW.erro := 'FIRSTSEND: tentativa de reabrir envio terminal; bloqueio anti-replay';
    RETURN NEW;
  END IF;

  SELECT (
    emp.situacao_cadastral='ATIVA'
    AND coalesce(emp.opt_out,false)=false
    AND emp.email IS NOT NULL
    AND btrim(emp.email::text)<>''
    AND lower(btrim(emp.email::text))=lower(btrim(NEW.email::text))
    AND mei_email.is_valid_email_address(emp.email)
    AND position('contabil' in lower(btrim(emp.email::text)))=0
    AND NOT mei_email.is_email_suppressed(emp.email)
    AND NOT mei_email.is_cnpj_suppressed(emp.cnpj::text)
    AND (SELECT count(*) FROM (
      SELECT 1 FROM mei_email.empresas emp2
       WHERE lower(btrim(emp2.email::text))=lower(btrim(emp.email::text))
       LIMIT 3
    ) z) <= 2
  ) INTO ok_live
  FROM mei_email.empresas emp
  WHERE emp.cnpj=NEW.cnpj;

  SELECT EXISTS (
    SELECT 1 FROM mei_email.envios prior
     WHERE prior.id <> NEW.id
       AND (prior.cnpj=NEW.cnpj OR lower(btrim(prior.email::text))=lower(btrim(NEW.email::text)))
       AND prior.status::text IN (
         'pendente','enviando','pending','processing',
         'submitted','enviado','delivered','bounced','bounce_permanent'
       )
  ) INTO already_used;

  IF coalesce(ok_live,false) IS FALSE OR already_used THEN
    NEW.status := 'bloqueado'::mei_email.status_envio;
    NEW.erro := CASE WHEN already_used
      THEN 'FIRSTSEND: destinatario ja enviado ou enfileirado; bloqueio anti-replay'
      ELSE 'FIRSTSEND: contrato canonico de elegibilidade rejeitou destinatario'
    END;
  END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mei_email.purge_invalid_operational_emails(p_limit integer DEFAULT 200)
RETURNS integer
LANGUAGE plpgsql
AS $function$
DECLARE
  r record;
  handled integer := 0;
BEGIN
  IF p_limit IS NULL OR p_limit < 1 OR p_limit > 2000 THEN
    RAISE EXCEPTION 'p_limit precisa estar entre 1 e 2000';
  END IF;
  FOR r IN
    SELECT e.cnpj,e.email FROM mei_email.empresas e
     WHERE e.email IS NOT NULL
       AND NOT mei_email.is_valid_email_address(e.email)
     ORDER BY e.cnpj LIMIT p_limit
  LOOP
    PERFORM mei_email.register_operational_suppression(
      r.cnpj::text,r.email,'filter_email_invalid',
      'canonical_invalid_email_observation',NULL,now()
    );
    UPDATE mei_email.envios x
       SET status='bloqueado'::mei_email.status_envio,
           erro=concat_ws(' | ',nullif(x.erro,''),'canonical policy: invalid email')
     WHERE x.cnpj=r.cnpj
       AND x.status::text IN ('pendente','enviando','pending','processing');
    handled := handled + 1;
  END LOOP;
  RETURN handled;
END;
$function$;

CREATE OR REPLACE FUNCTION mei_email.guard_canonical_policy_ddl()
RETURNS event_trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog','mei_email','public'
AS $function$
DECLARE
  src text;
  marker text;
  required text[] := ARRAY[
    'situacao_cadastral','opt_out','is_valid_email_address',
    'is_email_suppressed','is_cnpj_suppressed','limit 3','prior.status'
  ];
BEGIN
  SELECT lower(p.prosrc) INTO src
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='mei_email'
     AND p.proname='enforce_envio_live_eligibility';
  IF src IS NULL THEN
    RAISE EXCEPTION 'POLICY_GUARD: enforce_envio_live_eligibility ausente';
  END IF;
  FOREACH marker IN ARRAY required LOOP
    IF position(marker in src)=0 THEN
      RAISE EXCEPTION 'POLICY_GUARD: marcador canonico ausente: %',marker;
    END IF;
  END LOOP;
  IF position('contabil' in src)=0 THEN
    RAISE EXCEPTION 'POLICY_GUARD: filtro contabil ausente';
  END IF;
  IF src LIKE '%filter_uf%' OR src LIKE '%filter_not_mei%'
     OR src LIKE '%filter_marketing_not_authorized%'
     OR src LIKE '%filter_mei_not_verified%' THEN
    RAISE EXCEPTION 'POLICY_GUARD: filtro legado detectado';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_trigger t
    JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='mei_email' AND c.relname='empresas'
      AND NOT t.tgisinternal AND t.tgenabled<>'D'
      AND t.tgname IN ('zz_empresas_purge_rejected_after_update','zz_empresas_block_suppressed_or_rejected_insert')
  ) THEN
    RAISE EXCEPTION 'POLICY_GUARD: trigger legado de empresas ativo';
  END IF;
END;
$function$;

CREATE EVENT TRIGGER mei_email_policy_ddl_guard
ON ddl_command_end
EXECUTE FUNCTION mei_email.guard_canonical_policy_ddl();

COMMIT;
