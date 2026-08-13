# Credential hygiene follow-up - 2026-08-13

## Finding

A legacy Gmail SMTP test file previously contained a hardcoded application credential in repository history. The file was removed from the active tree and the current CI includes `scripts/auditar_segredos_repo.py` to reject similar working-tree regressions.

The historical credential value is intentionally not reproduced here.

## External action still required

Deleting a credential from the repository does not revoke the credential. The corresponding Gmail/Google application password must be revoked/rotated in the account security controls. This repository has no Google account administration credential and must not attempt to store the replacement secret.

## Repository safeguards

- SMTP test scripts with hardcoded credentials removed.
- `.gitignore` blocks common private-key/token artifacts.
- CI scans tracked text for private keys, access tokens, app passwords and hardcoded SMTP login calls.
- Production email provider remains Microsoft Graph app-only X.509.

## History

If repository history is ever rewritten to remove the old blob, coordinate that as a separate maintenance event because history rewriting changes commit SHAs and requires all clones/automation to resynchronize. Credential revocation is the immediate security control regardless of history cleanup.
