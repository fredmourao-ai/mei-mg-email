# Weekly database backups

The scheduled database backup workflow runs every Sunday at 04:30 UTC.

- `mei-backend` runs the validated `main` profile on the primary VM.
- `mei-ci` runs the validated `secondary` profile on the secondary VM.
- Each profile creates PostgreSQL custom-format dumps, validates them with `pg_restore -l`, uploads them to OCI Object Storage, and verifies the remote object size.
- `workflow_dispatch` remains available for manual recovery and verification runs.

The workflow is intentionally pinned to the existing self-hosted runner labels so each host backs up only the persistent databases it owns.
