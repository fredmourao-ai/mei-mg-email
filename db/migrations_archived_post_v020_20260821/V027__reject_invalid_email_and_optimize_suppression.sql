-- V027: rejeita enderecos de email sintaticamente invalidos antes do Graph,
-- registra supressao permanente e torna consultas de supressao indexaveis.
set search_path = mei_email, public;

create or replace function mei_email.is_valid_email_address(p_email public.citext)
returns boolean
language sql
immutable
parallel safe
as $function$
  select case
    when p_email is null then false
    else
      length(btrim(p_email::text)) between 3 and 254
      and btrim(p_email::text) !~ '[[:space:],;]'
      and (
        length(btrim(p_email::text))
        - length(replace(btrim(p_email::text), '@', ''))
      ) = 1
      and length(split_part(btrim(p_email::text), '@', 1)) between 1 and 64
      and split_part(btrim(p_email::text), '@', 1) ~ '^[A-Za-z0-9!#$%&''*+/=?^_`{|}~.-]+$'
      and split_part(btrim(p_email::text), '@', 1) !~ '(^[.]|[.]$|[.][.])'
      and length(split_part(btrim(p_email::text), '@', 2)) between 3 and 253
      and split_part(btrim(p_email::text), '@', 2) ~ '^[A-Za-z0-9.-]+$'
      and split_part(btrim(p_email::text), '@', 2) like '%.%'
      and split_part(btrim(p_email::text), '@', 2) !~ '(^[.-]|[.-]$|[.][.]|[-][.]|[.][-])'
  end;
$function$;

-- email_suppressions.value e CITEXT e ja e gravado normalizado. Comparar o
-- valor diretamente permite ao PostgreSQL usar os indices (active,scope,value).
create or replace function mei_email.is_email_suppressed(p_email public.citext)
returns boolean
language sql
stable
as $function$
  select exists(
    select 1
      from mei_email.email_suppressions s
     where s.active
       and (
         (s.scope = 'email'
          and s.value = lower(btrim(p_email::text))::public.citext)
         or
         (s.scope = 'domain'
          and s.value = split_part(lower(btrim(p_email::text)), '@', 2)::public.citext)
       )
  );
$function$;

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
       and s.value = upper(btrim(p_cnpj))::public.citext
  );
$function$;

create or replace function mei_email.operational_filter_rejection_reason(
    p_situacao text,
    p_uf text,
    p_email public.citext,
    p_opt_out boolean,
    p_provavel_terceiro boolean,
    p_campo_autorizacao_legado boolean,
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
    when not mei_email.is_valid_email_address(p_email) then 'filter_email_invalid'
    when coalesce(p_provavel_terceiro, false) then 'filter_third_party'
    when not coalesce(p_campo_autorizacao_legado, false) then 'filter_marketing_not_authorized'
    when coalesce(upper(btrim(p_tipo_regime)), '') <> 'MEI' then 'filter_not_mei'
    when not coalesce(p_mei_verificado, false) then 'filter_mei_not_verified'
    else null
  end;
$function$;

-- Defesa em profundidade: a fila nunca seleciona endereco com sintaxe invalida,
-- mesmo que uma carga legada tenha escapado do trigger de insert/update.
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
   and e.campo_autorizacao_legado = true
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

-- Limpeza operacional em lotes pequenos. O caller pode repetir ate retornar 0.
-- Primeiro grava email+CNPJ na supressao; depois apaga fila/historico operacional
-- e empresa para impedir crescimento e reuso acidental.
create or replace function mei_email.purge_invalid_operational_emails(p_limit integer default 200)
returns integer
language plpgsql
as $function$
declare
  r record;
  purged integer := 0;
begin
  if p_limit is null or p_limit < 1 or p_limit > 2000 then
    raise exception 'p_limit precisa estar entre 1 e 2000';
  end if;

  for r in
    select e.cnpj, e.email
      from mei_email.empresas e
     where e.email is not null
       and not mei_email.is_valid_email_address(e.email)
     order by e.cnpj
     limit p_limit
  loop
    perform mei_email.register_operational_suppression(
      r.cnpj::text,
      r.email,
      'filter_email_invalid',
      'v027_invalid_email_cleanup',
      null,
      now()
    );

    delete from mei_email.envios x
     where x.cnpj = r.cnpj;

    delete from mei_email.empresas x
     where x.cnpj = r.cnpj;

    purged := purged + 1;
  end loop;

  return purged;
end;
$function$;

comment on function mei_email.is_valid_email_address(public.citext) is
  'Valida sintaxe operacional minima antes de enfileirar/enviar; nao tenta corrigir enderecos ambiguos.';
comment on function mei_email.purge_invalid_operational_emails(integer) is
  'Suprime e remove em pequenos lotes empresas com email sintaticamente invalido; repetir ate retornar 0.';
