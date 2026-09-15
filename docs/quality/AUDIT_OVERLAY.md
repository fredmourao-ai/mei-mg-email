# Overlay de Auditoria do Projeto

Este arquivo complementa o protocolo universal. Ele não substitui `AGENTS.md`, README, ADRs, arquitetura, regras de negócio ou runbooks existentes.

## Regra de uso
Antes de iniciar uma auditoria extrema, o agente deve reconstruir as regras específicas deste repositório a partir das fontes autoritativas existentes e transformar essas regras em **invariantes verificáveis**. Não é permitido auditar apenas contra boas práticas genéricas.

## Fontes obrigatórias quando existirem
1. `AGENTS.md` e arquivos referenciados por ele;
2. README e documentação de arquitetura;
3. ADRs e decisões vigentes do proprietário;
4. migrations/schema e contratos públicos;
5. runbooks operacionais/deploy;
6. testes que expressem regras históricas;
7. configuração e comportamento real do ambiente.

## Classes de domínio a considerar
Se presentes no projeto, trate como área crítica: dinheiro/preço/reembolso; prazos e datas-limite; efeitos externos; autenticação/autorização; isolamento multi-tenant; dados pessoais/sensíveis; automações periódicas; filas/workers; integrações de terceiros; reconciliação; backups/restores; deploy e proveniência da versão.

## Matriz de invariantes específica
A auditoria deve criar no relatório uma tabela `Invariante | Fonte da regra | Garantia técnica | Teste/evidência | Resultado`. Regras conflitantes devem ser resolvidas pela hierarquia de autoridade já definida no projeto; se não houver hierarquia clara, registre o conflito como achado.

## Mudança deste overlay
Quando uma auditoria revelar uma regra estrutural e duradoura que não está adequadamente documentada em outra fonte autoritativa, atualize este overlay no mesmo fluxo de PR. Não copie detalhes temporários, secrets ou estado operacional volátil.
