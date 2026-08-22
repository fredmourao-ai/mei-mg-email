-- V037: keep recovered/open queues fail-closed after V033/V036 and retire
-- legacy copy that claimed public CNPJ discovery as the reason for marketing.
-- This migration does not create recipients or grant consent.
set search_path = mei_email, public;

-- Permanently neutralize legacy campaign copy, including campaigns that may be
-- reopened later by recovery. Worker eligibility still requires current
-- authorization at send time.
update campanhas
   set assunto = 'Contabilidade Melo para MEI: plano mensal e suporte fiscal',
       corpo_template = replace(
           corpo_template,
           'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
           'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
       )
 where corpo_template ilike '%base pública de CNPJ%';

-- Remove currently open work that no longer satisfies the live eligibility
-- contract. This prevents old queue rows from consuming worker cycles after
-- consent or MEI verification was revoked by forward migrations.
update envios e
   set status = 'bloqueado',
       erro = 'V037: fila aberta tornou-se inelegivel; bloqueio fail-closed'
  from empresas emp
 where e.cnpj = emp.cnpj
   and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
   and (
       emp.marketing_autorizado is not true
       or emp.mei_verificado is not true
       or emp.opt_out is true
       or emp.situacao_cadastral <> 'ATIVA'
       or emp.provavel_terceiro is true
       or emp.email is null
       or btrim(emp.email::text) = ''
       or not mei_email.is_valid_email_address(emp.email)
       or mei_email.is_email_suppressed(emp.email)
       or mei_email.is_cnpj_suppressed(emp.cnpj::text)
   );

-- Any lot left with no open recipients is complete; lots with remaining open
-- recipients are returned to the normal queue state for queue-first processing.
-- status is an enum, so cast the CASE result explicitly instead of relying on
-- PostgreSQL to coerce text branches to status_lote.
update lotes l
   set status = (case
       when exists (
           select 1 from envios e
            where e.lote_id = l.id
              and e.status::text in ('pendente', 'enviando', 'pending', 'processing')
       ) then 'pendente'
       else 'concluido'
   end)::status_lote,
       iniciado_em = null,
       erro = null
 where l.status::text in ('pendente', 'processando', 'processing');
