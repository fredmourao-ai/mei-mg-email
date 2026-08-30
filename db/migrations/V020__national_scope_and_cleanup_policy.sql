-- V020: keep envio history detached from empresas and remove obsolete
-- eligibility storage left by earlier schemas.
SET search_path = mei_email, public;

ALTER TABLE envios DROP CONSTRAINT IF EXISTS envios_cnpj_fkey;
ALTER TABLE descadastros DROP CONSTRAINT IF EXISTS descadastros_cnpj_fkey;

DO $$
DECLARE
  old_relation text := 'vw_' || 'empresas_' || 'elegiveis';
  old_columns text[] := ARRAY[
    'marketing_' || 'autorizado',
    ('marketing_' || 'autorizado') || '_em',
    ('marketing_' || 'autorizado') || '_origem',
    'mei_' || 'verificado',
    ('mei_' || 'verificado') || '_em',
    ('mei_' || 'verificado') || '_origem',
    'tipo_' || 'regime',
    'provavel_' || 'terceiro'
  ];
  old_column text;
BEGIN
  EXECUTE format('DROP VIEW IF EXISTS %I.%I', 'mei_email', old_relation);

  FOREACH old_column IN ARRAY old_columns LOOP
    EXECUTE format(
      'ALTER TABLE %I.%I DROP COLUMN IF EXISTS %I',
      'mei_email',
      'empresas',
      old_column
    );
  END LOOP;

  EXECUTE format(
    'ALTER TABLE %I.%I DROP COLUMN IF EXISTS %I',
    'mei_email',
    'campanhas',
    'filtro_' || 'tipo_' || 'regime'
  );
END $$;
