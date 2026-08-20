-- Remove legacy public-CNPJ copy from active campaign templates.
-- Safety:
-- - Does not reopen submitted/enviado/delivered messages.
-- - Does not change opt-out, suppression, sender_block or consent state.
-- - Fails if the legacy phrase still remains in campaign templates.

update mei_email.campanhas
set corpo_template = replace(
  corpo_template,
  'Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.',
  'Você recebe esta mensagem porque há uma autorização comercial registrada para este contato.'
)
where corpo_template like '%Você recebeu este e-mail porque seu contato consta em base pública de CNPJ.%';

update mei_email.campanhas
set corpo_template = replace(
  corpo_template,
  'Voce recebeu este e-mail porque seu contato consta em base publica de CNPJ.',
  'Voce recebe esta mensagem porque ha uma autorizacao comercial registrada para este contato.'
)
where corpo_template like '%Voce recebeu este e-mail porque seu contato consta em base publica de CNPJ.%';

do $$
declare
  remaining integer;
begin
  select count(*)
    into remaining
    from mei_email.campanhas
   where corpo_template ilike '%base pública de CNPJ%'
      or corpo_template ilike '%base publica de CNPJ%';

  if remaining <> 0 then
    raise exception 'legacy public-CNPJ copy remains in % campaign template(s)', remaining;
  end if;
end $$;
