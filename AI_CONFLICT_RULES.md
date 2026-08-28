# AI Conflict Resolution Rules

1. Preserve compatible behavior from both sides; never choose `ours` or `theirs` wholesale.
2. Never resolve conflicts in secrets, credentials, certificates, `.env`, GitHub workflows, migrations, production deployment controls, authentication, billing/payment code, Microsoft Graph sending code, suppression logic, recipient/rate-limit logic, campaign eligibility, or email-safety policy surfaces.
3. Never invent configuration values, identifiers, tokens, recipients, credentials, limits, database fields, or external API behavior.
4. Do not delete unrelated functions, tests, comments, guards, validations, or logging.
5. Prefer the smallest combined edit that preserves both intentions.
6. Return exactly one JSON object: `{"path":"<same path>","content":"<full resolved file>"}`.
7. Never include markdown fences, explanations, conflict markers, or content for another file.
8. If both sides are semantically incompatible, do not guess; the deterministic wrapper will leave the conflict for human review.