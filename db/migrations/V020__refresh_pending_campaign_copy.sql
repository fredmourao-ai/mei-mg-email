-- V020: aplica a copia de recuperacao de reputacao tambem nas campanhas ja enfileiradas.
-- Somente campanhas que ainda possuem envios pendentes/enviando sao alteradas.
set search_path = mei_email, public;

update campanhas c
   set assunto = 'Contabilidade Melo para MEI: plano mensal e suporte fiscal',
       corpo_template = replace(
         replace(
           replace(
             replace(
               corpo_template,
               'Pensando nisso, a <strong>Contabilidade Melo</strong> preparou uma condição especial para ajudar o seu MEI a ficar regularizado, emitir notas fiscais com segurança e economizar tempo.',
               'A <strong>Contabilidade Melo</strong> oferece suporte contábil para MEI, com acompanhamento das obrigações fiscais e apoio na emissão de notas.'
             ),
             '<strong>Certificado Digital GRÁTIS</strong> para sua empresa',
             '<strong>Certificado digital incluído</strong> no plano'
           ),
           'Quero falar no WhatsApp',
           'Falar com a Contabilidade Melo'
         ),
         'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ. Caso não queira receber novas mensagens, acesse: <a href="{{unsubscribe_url}}" style="color:#0b1f3a;">descadastrar</a>.',
         'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato. Se não quiser receber novas mensagens da Contabilidade Melo, use o link de <a href="{{unsubscribe_url}}" style="color:#0b1f3a;">descadastro</a>.'
       )
 where exists (
   select 1
     from envios e
    where e.campanha_id = c.id
      and e.status::text in ('pendente', 'enviando')
 );
