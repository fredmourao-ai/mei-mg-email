#!/usr/bin/env bash
set -Eeuo pipefail
root="$(git rev-parse --show-toplevel)"
cd "$root"
protocol='AI-TO-CLI-PROTOCOL.md'
marker='Continuidade obrigatoria diante de falha de ferramenta ou comando'
[ -f "$protocol" ] || { echo "BLOCKED: missing $protocol" >&2; exit 61; }
grep -Fq "$marker" "$protocol" || { echo "BLOCKED: continuity protocol section missing" >&2; exit 62; }
for f in AGENTS.md AGENTS.override.md CLAUDE.md GEMINI.md .github/copilot-instructions.md .cursor/rules/nonstop-continuity.mdc .windsurf/rules/nonstop-continuity.md; do
  [ -f "$f" ] || { echo "BLOCKED: missing agent entrypoint $f" >&2; exit 63; }
  grep -Fq 'AI-TO-CLI-PROTOCOL.md' "$f" || { echo "BLOCKED: $f does not reference canonical protocol" >&2; exit 64; }
done
grep -Fq 'unknown option/subcommand' "$protocol" || { echo 'BLOCKED: command incompatibility fallback rule missing' >&2; exit 65; }
grep -Fq 'nao e estado terminal da tarefa' "$protocol" || { echo 'BLOCKED: non-terminal tool failure rule missing' >&2; exit 66; }
grep -Fq 'PROTOCOLO OBRIGATORIO DE CONCLUSAO DE TAREFAS' "$protocol" || { echo 'BLOCKED: end-to-end completion protocol missing' >&2; exit 67; }
grep -Fq 'falha de ferramenta, comando, plugin, CLI, API, browser, sessao ou timeout nao e estado final' "$protocol" || { echo 'BLOCKED: broad tool fallback rule missing' >&2; exit 68; }
grep -Fq 'CONCLUIDO' "$protocol" || { echo 'BLOCKED: CONCLUIDO terminal state missing' >&2; exit 69; }
grep -Fq 'BLOQUEADO' "$protocol" || { echo 'BLOCKED: BLOQUEADO terminal state missing' >&2; exit 70; }
echo 'agent continuity protocol: PASS'
