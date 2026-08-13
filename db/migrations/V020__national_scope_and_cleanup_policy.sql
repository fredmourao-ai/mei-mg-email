-- V020: Alterar padrão de marketing_autorizado para true e remover chaves estrangeiras de empresas para permitir exclusão segura de registros de empresas sem quebrar o histórico de envios/descadastros.
SET search_path = mei_email, public;

-- Alterar o valor padrão para true
ALTER TABLE empresas ALTER COLUMN marketing_autorizado SET DEFAULT true;

-- Remover chaves estrangeiras para deleção limpa
ALTER TABLE envios DROP CONSTRAINT IF EXISTS envios_cnpj_fkey;
ALTER TABLE descadastros DROP CONSTRAINT IF EXISTS descadastros_cnpj_fkey;
