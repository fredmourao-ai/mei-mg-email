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
echo 'agent continuity protocol: PASS'
