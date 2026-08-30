-- V022: aplica a decisao operacional de 2026-08-13 ao estoque existente.
--
-- O operador confirmou que os registros atuais podem ser usados pela campanha
-- e determinou que a classificacao MEI da base seja aceita operacionalmente.
-- A origem fica explicita para nao confundir este override com verificacao
-- oficial da Receita/Simples.
set search_path = mei_email, public;

update empresas
   set campo_autorizacao_legado = true,
       campo_autorizacao_legado_em = coalesce(campo_autorizacao_legado_em, now()),
       campo_autorizacao_legado_origem = case
           when campo_autorizacao_legado_origem is null
             or btrim(campo_autorizacao_legado_origem) = ''
           then 'confirmacao_operador_2026-08-13'
           else campo_autorizacao_legado_origem
       end
 where campo_autorizacao_legado = false
    or campo_autorizacao_legado_em is null
    or campo_autorizacao_legado_origem is null
    or btrim(campo_autorizacao_legado_origem) = '';

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
   and e.campo_autorizacao_legado = true
   and e.opt_out = false
   and e.provavel_terceiro = false
   and e.situacao_cadastral = 'ATIVA';

comment on column empresas.mei_verificado is
  'true quando confirmado por fonte oficial ou aceito por override operacional auditavel; consultar mei_verificado_origem para distinguir a origem.';
