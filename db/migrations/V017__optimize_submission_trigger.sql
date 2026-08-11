-- V017: evita OR caro no trigger de submitted/enviado.
set search_path = mei_email, public;

create or replace function mei_email.trg_marcar_empresa_submetida()
returns trigger language plpgsql as $$
begin
  if new.status::text in ('submitted', 'enviado') then
    update mei_email.empresas e
       set enviado = true,
           enviado_em = coalesce(e.enviado_em, new.enviado_em, now())
     where e.cnpj = new.cnpj;

    if new.email is not null then
      update mei_email.empresas e
         set enviado = true,
             enviado_em = coalesce(e.enviado_em, new.enviado_em, now())
       where lower(btrim(e.email::text)) = lower(btrim(new.email::text))
         and e.cnpj <> new.cnpj;
    end if;
  end if;
  return new;
end;
$$;
