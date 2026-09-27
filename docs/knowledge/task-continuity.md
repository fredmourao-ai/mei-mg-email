# Global task continuity

Policy: `GLOBAL_TASK_CONTINUITY_V8`.

Este repositório consome o controlador canônico detached em
`Vivaliz-site/site-shopvivaliz`. O adapter local fixa
`repository=fredmourao-ai/mei-mg-email` e falha fechado se o controlador não
for injetado. Certificação exige `continuity_e2e_pass` real para a mesma
identidade de repositório.

Background recovery é Gemini-only. Codex não participa do daemon e permanece a
última opção finita explícita.
