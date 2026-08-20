# Runtime secrets

This directory is mounted read-only at `/run/secrets` in `config-check` and `backup`.
For encrypted off-site backups, create an untracked `restic-password` file owned by the
deployment operator, mode `0600`, and set:

```dotenv
RESTIC_PASSWORD=
RESTIC_PASSWORD_FILE=/run/secrets/restic-password
```

Never commit secret payloads here.
