-- V022: aplica a decisao operacional de 2026-08-13 ao estoque existente.
--
-- O operador confirmou que os registros atuais podem ser usados pela campanha
-- e determinou que a classificacao MEI da base seja aceita operacionalmente.
-- A origem fica explicita para nao confundir este override com verificacao
-- oficial da Receita/Simples.
set search_path = mei_email, public;

update empresas
   set marketing_autorizado = true,
       marketing_autorizado_em = coalesce(marketing_autorizado_em, now()),
       marketing_autorizado_origem = case
           when marketing_autorizado_origem is null
             or btrim(marketing_autorizado_origem) = ''
           then 'confirmacao_operador_2026-08-13'
           else marketing_autorizado_origem
       end
 where marketing_autorizado = false
    or marketing_autorizado_em is null
    or marketing_autorizado_origem is null
    or btrim(marketing_autorizado_origem) = '';

update empresas
   set mei_verificado = true,
       mei_verificado_em = coalesce(mei_verificado_em, now()),
       mei_verificado_origem = case
           when mei_verificado_origem is null
             or btrim(mei_verificado_origem) = ''
           then 'override_operador_2026-08-13'
           else mei_verificado_origem
       end
 where mei_verificado = false
    or mei_verificado_em is null
    or mei_verificado_origem is null
    or btrim(mei_verificado_origem) = '';

-- Reabre apenas itens que estavam bloqueados pelo gate de autorizacao da V019.
-- Opt-out, terceiro provavel, inatividade e supressoes de envio continuam sendo
-- respeitados pelo worker/view.
update envios x
   set status = 'pendente',
       erro = null
  from empresas e
 where x.cnpj = e.cnpj
   and x.status::text = 'bloqueado'
   and x.erro = 'deliverability gate: autorizacao comercial sem origem/data auditavel'
   and e.marketing_autorizado = true
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.situacao_cadastral = 'ATIVA';

comment on column empresas.mei_verificado is
  'true quando confirmado por fonte oficial ou aceito por override operacional auditavel; consultar mei_verificado_origem para distinguir a origem.';
