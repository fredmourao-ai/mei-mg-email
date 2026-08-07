-- Index de alta performance para a view de elegiveis (MEI / SIMPLES por UF e data_abertura)
CREATE INDEX IF NOT EXISTS idx_empresas_elegiveis_regime_uf
    ON mei_email.empresas (tipo_regime, uf, data_abertura DESC)
 WHERE opt_out = false
   AND provavel_terceiro = false
   AND email IS NOT NULL AND email != '';

