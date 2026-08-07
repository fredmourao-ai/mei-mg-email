-- V009: curva de aquecimento gradual de envios/dia, configuravel via tabela.
-- Objetivo: nao queimar a reputacao do dominio/remetente comecando a enviar
-- no limite maximo do plano gratuito da Brevo (300/dia) desde o primeiro dia.
-- "dia_a_partir" = numero de dias desde o primeiro envio REAL bem-sucedido
-- (status='enviado'), 0-indexado. O worker sempre usa a linha com o maior
-- dia_a_partir que seja <= dias_passados (a curva "sobe em degraus" e
-- estabiliza no ultimo valor apos o ultimo degrau).
set search_path = mei_email, public;

create table if not exists aquecimento_envio (
    dia_a_partir integer primary key,
    limite_diario integer not null check (limite_diario > 0),
    atualizado_em timestamptz not null default now()
);

comment on table aquecimento_envio is
    'Curva de aquecimento de envio de e-mail: limite diario de envios reais '
    'em funcao dos dias desde o primeiro envio bem-sucedido. Editavel direto '
    'via UPDATE/INSERT nesta tabela, sem precisar de deploy.';

-- Curva default sugerida: ~25/dia na semana 1, dobrando a cada semana ate
-- estabilizar perto do teto do plano gratuito (300/dia, com margem de
-- seguranca ja aplicada separadamente via MAX_ENVIOS_POR_DIA no .env).
insert into aquecimento_envio (dia_a_partir, limite_diario) values
    (0, 25),
    (7, 50),
    (14, 100),
    (21, 150),
    (28, 200),
    (35, 250),
    (42, 300)
on conflict (dia_a_partir) do nothing;
