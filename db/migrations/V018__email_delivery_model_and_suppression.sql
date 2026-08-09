-- Applies the delivery model after V017 commits the enum values.
set search_path = mei_email, public;

alter table envios
  add column if not exists submitted_at timestamptz,
  add column if not exists delivered_at timestamptz,
  add column if not exists bounced_at timestamptz,
  add column if not exists failed_at timestamptz,
  add column if not exists graph_request_id text,
  add column if not exists internet_message_id text,
  add column if not exists ndr_code text,
  add column if not exists ndr_reason text,
  add column if not exists last_error text,
  add column if not exists reconciled_at timestamptz;

update envios
   set status = case status
                  when 'pendente' then 'pending'
                  when 'enviando' then 'processing'
                  when 'enviado' then 'submitted'
                  when 'falhou' then 'failed'
                  when 'bounced' then 'bounce_permanent'
                  when 'opt_out' then 'suppressed'
                  when 'bloqueado' then 'cancelled'
                  else status
                end,
       submitted_at = case when status in ('enviado', 'submitted', 'delivered') then coalesce(submitted_at, enviado_em) else submitted_at end,
       delivered_at = case when status = 'delivered' then coalesce(delivered_at, enviado_em) else delivered_at end,
       bounced_at = case when status in ('bounced', 'bounce_temporary', 'bounce_permanent', 'sender_blocked') then coalesce(bounced_at, criado_em) else bounced_at end,
       failed_at = case when status in ('falhou', 'failed', 'cancelled', 'suppressed') then coalesce(failed_at, criado_em) else failed_at end,
       graph_request_id = coalesce(graph_request_id, provider_message_id),
       internet_message_id = coalesce(internet_message_id, provider_message_id),
       last_error = coalesce(last_error, erro)
 where status in ('pendente', 'enviando', 'enviado', 'falhou', 'bounced', 'opt_out', 'bloqueado');

create table if not exists email_suppressions (
  id uuid primary key default gen_random_uuid(),
  scope text not null check (scope in ('email', 'domain')),
  value citext not null,
  reason text not null,
  source text not null default 'manual',
  source_ref text,
  ndr_code text,
  ndr_reason text,
  active boolean not null default true,
  reactivate_after timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_email_suppressions_active_scope_value
  on email_suppressions (scope, value)
 where active = true;

create index if not exists idx_email_suppressions_lookup
  on email_suppressions (active, scope, value);

create index if not exists idx_envios_email_status_lookup
  on envios (lower(btrim(email::text)), status);

create index if not exists idx_envios_graph_request_id
  on envios (graph_request_id)
 where graph_request_id is not null;

create index if not exists idx_envios_internet_message_id
  on envios (internet_message_id)
 where internet_message_id is not null;

create unique index if not exists uq_envios_email_active
  on envios (lower(btrim(email::text)))
 where status in ('pending', 'processing', 'submitted');

create or replace function mei_email.is_email_suppressed(p_email citext)
returns boolean
language sql
stable
as $$
  select exists(
    select 1
      from mei_email.email_suppressions s
     where s.active
       and (
         (s.scope = 'email' and lower(btrim(s.value::text)) = lower(btrim(p_email::text)))
         or
         (s.scope = 'domain' and lower(btrim(s.value::text)) = split_part(lower(btrim(p_email::text)), '@', 2))
       )
  );
$$;

create or replace view mei_email.vw_empresas_elegiveis as
select e.cnpj, e.razao_social, e.nome_fantasia, e.situacao_cadastral, e.uf, e.email,
       e.ddd_1, e.telefone_1, e.data_abertura, e.provavel_terceiro, e.opt_out,
       e.opt_out_em, e.opt_out_motivo, e.enviado, e.enviado_em, e.importado_em,
       e.atualizado_em, e.tipo_regime, e.marketing_autorizado,
       e.marketing_autorizado_em, e.marketing_autorizado_origem,
       e.mei_verificado, e.mei_verificado_em, e.mei_verificado_origem
  from mei_email.empresas e
 where e.situacao_cadastral = 'ATIVA'
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.email is not null
   and btrim(e.email::text) <> ''
   and e.marketing_autorizado = true
   and e.enviado = false
   and (
        e.tipo_regime not in ('MEI', 'MEI_CANDIDATO')
        or e.mei_verificado = true
   )
   and not mei_email.is_email_suppressed(e.email)
   and not exists (
     select 1
       from mei_email.envios x
      where lower(btrim(x.email::text)) = lower(btrim(e.email::text))
        and x.status in (
          'pending', 'processing', 'submitted', 'delivered',
          'bounce_temporary', 'bounce_permanent'
        )
   );
