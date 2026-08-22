-- Remove o rodape legado de base publica de CNPJ de campanhas/templates ativos.
-- Esta migration nao concede consentimento, nao reabre destinatarios e nao altera
-- suppressions/opt-out. Ela apenas normaliza o texto exibido antes de qualquer
-- novo envio.

update mei_email.campanhas
   set corpo_template = replace(
         replace(
           corpo_template,
           'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
           'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
         ),
         'Você recebeu este e-mail porque seu contato consta em base publica de CNPJ.',
         'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
       )
 where corpo_template ilike '%base pública de CNPJ%'
    or corpo_template ilike '%base publica de CNPJ%';

-- Falha se o texto legado permanecer em qualquer campanha.
do $$
begin
  if exists (
    select 1
      from mei_email.campanhas
     where corpo_template ilike '%base pública de CNPJ%'
        or corpo_template ilike '%base publica de CNPJ%'
  ) then
    raise exception 'legacy public-CNPJ copy remains in campanhas';
  end if;
end $$;
