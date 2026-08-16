-- V029: indice parcial pequeno para o universo barato da autoqueue.
-- Nao inclui supressao/dedupe no predicado; esses gates continuam depois do LIMIT.
set search_path = mei_email, public;

create index if not exists idx_empresas_autoqueue_mei_mg
    on mei_email.empresas (cnpj)
    include (email, data_abertura)
    where tipo_regime = 'MEI'
      and uf = 'MG'
      and situacao_cadastral = 'ATIVA'
      and opt_out = false
      and provavel_terceiro = false
      and email is not null
      and enviado = false
      and marketing_autorizado = true
      and mei_verificado = true;

comment on index mei_email.idx_empresas_autoqueue_mei_mg is
  'Pool parcial da autoqueue: MEI/MG ativa, autorizada, verificada e ainda nao enviada. Gates de email valido/supressao/dedupe sao aplicados apos LIMIT.';
