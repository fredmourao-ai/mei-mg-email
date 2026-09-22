<!-- GEPETO_EVERY_TASK_V1 -->
## Gepeto e Superpowers obrigatorios em toda tarefa

- Por determinacao do proprietario, toda tarefa, conversa, sessao e retomada deve acionar o plugin Gepeto junto com Superpowers, sem exigir nova mencao do usuario. A regra vale globalmente e em todos os repositorios de Vivaliz-site e fredmourao-ai.
- No inicio da tarefa, localizar e ler a skill de instrucoes do Gepeto no catalogo do runtime (plugin gpt-4d1b51dc23427fe5106bbd896a5b7a0e; skill instructions), usando suas ferramentas pertinentes. Reutilizar a leitura na mesma sessao enquanto estiver atual; nao repetir chamadas sem necessidade.
- Aplicar Gepeto na execucao, revisao critica e validacao com evidencias; selecionar a disciplina Superpowers adequada a cada etapa material, inclusive retome/continue/prossiga.
- Um plugin fornece instrucoes e ferramentas ao agente atual; nao implica outro agente autonomo, fila recebida, atividade em segundo plano ou revisao independente. So declarar delegacao/revisao externa quando houver execucao e resposta comprovadas.
- Se a capacidade nao estiver exposta, registrar GEPETO_UNAVAILABLE (ou SUPERPOWERS_UNAVAILABLE), informar a limitacao e continuar o trabalho autorizado com as regras disponiveis. Nunca simular invocacao, resposta, consenso ou aprovacao.
- Ao delegar uma tarefa autorizada, transmitir esta regra e o contexto minimo necessario. Gepeto nao substitui OpenAI, Claude ou Gemini nem conta como quarto provider do Buscador.
- Esta regra nao instala nem habilita plugins automaticamente em outra conta/conversa e nao amplia permissoes, escopo, custo ou autorizacao. Preservar secrets, gates, revisoes independentes exigidas, limites de execucao e proibicao de IA paga em loops/rotinas permanentes.
<!-- /GEPETO_EVERY_TASK_V1 -->

