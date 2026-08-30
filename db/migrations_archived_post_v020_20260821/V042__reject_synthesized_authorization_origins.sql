-- V042: reject authorization origins that were synthesized by temporary
-- operator/recovery workflows rather than backed by independent opt-in.
--
-- This migration does not grant consent, create recipients, reopen terminal
-- sends, alter opt-outs/suppressions, or bypass provider/sender-block limits.
set search_path = mei_email, public;

create or replace function mei_email.is_independent_marketing_authorization(
    p_authorized boolean,
    p_origin text
)
returns boolean
language sql
immutable
parallel safe
as $function$
  select coalesce(p_authorized, false)
     and nullif(btrim(coalesce(p_origin, '')), '') is not null
     and btrim(p_origin) not in (
       'confirmacao_operador_2026-08-12',
       'confirmacao_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13',
       'user_explicit_authorization_2026-08-20'
     )
     and lower(btrim(p_origin)) not like '%operator_authorization_true%';
$function$;

-- Neutralize only the two known classes of synthesized authorization. Preserve
-- all other audited/independent origins exactly as stored.
update empresas
   set campo_autorizacao_legado = false,
       campo_autorizacao_legado_em = null,
       campo_autorizacao_legado_origem = 'synthesized_authorization_rejected_20260820'
 where campo_autorizacao_legado is true
   and (
       btrim(coalesce(campo_autorizacao_legado_origem, '')) = 'user_explicit_authorization_2026-08-20'
       or lower(btrim(coalesce(campo_autorizacao_legado_origem, ''))) like '%operator_authorization_true%'
   );

create or replace function mei_email.enforce_independent_empresa_sources()
returns trigger
language plpgsql
as $function$
declare
  marketing_origin text := btrim(coalesce(new.campo_autorizacao_legado_origem, ''));
  mei_origin text := btrim(coalesce(new.mei_verificado_origem, ''));
begin
  if new.campo_autorizacao_legado is true
     and (
       marketing_origin in (
         'confirmacao_operador_2026-08-12',
         'confirmacao_operador_2026-08-13',
         'politica_importacao_operador_2026-08-13',
         'user_explicit_authorization_2026-08-20'
       )
       or lower(marketing_origin) like '%operator_authorization_true%'
     )
  then
    new.campo_autorizacao_legado := false;
    new.campo_autorizacao_legado_em := null;
    new.campo_autorizacao_legado_origem := 'synthesized_authorization_rejected_20260820';
  end if;

  if new.mei_verificado is true
     and mei_origin in (
       'override_operador_2026-08-13',
       'politica_importacao_operador_2026-08-13'
     )
  then
    new.mei_verificado := false;
    new.mei_verificado_em := null;
    new.mei_verificado_origem := 'legacy_operator_verification_rejected_20260820';
    if new.tipo_regime = 'MEI' then
      new.tipo_regime := 'MEI_CANDIDATO';
    end if;
  end if;

  return new;
end
$function$;

-- Existing open queue rows whose authorization became invalid are blocked;
-- submitted/enviado/delivered evidence is not touched or reopened.
update envios e
   set status = 'bloqueado',
       erro = 'V042: origem de autorizacao sintetizada; bloqueio fail-closed'
  from empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and not mei_email.is_independent_marketing_authorization(
       emp.campo_autorizacao_legado, emp.campo_autorizacao_legado_origem
   );

-- Recreate the eligibility view so autoqueue rejects these rows before LIMIT.
create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.campo_autorizacao_legado,
       e.campo_autorizacao_legado_em, e.campo_autorizacao_legado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and upper(e.uf) = 'MG'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and mei_email.is_valid_email_address(e.email)
   and mei_email.is_independent_marketing_authorization(
       e.campo_autorizacao_legado, e.campo_autorizacao_legado_origem
   )
   and mei_email.is_independent_mei_verification(
       e.mei_verificado, e.mei_verificado_origem
   )
   and e.enviado = false
   and e.tipo_regime = 'MEI'
   and not mei_email.is_email_suppressed(e.email)
   and not mei_email.is_cnpj_suppressed(e.cnpj::text)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status::text in (
          'pendente','enviando','pending','processing',
          'submitted','enviado','delivered','bounced','bounce_permanent'
        )
   );

comment on function mei_email.is_independent_marketing_authorization(boolean, text) is
  'true only for non-empty independent authorization sources; synthesized operator/recovery origins are rejected.';
