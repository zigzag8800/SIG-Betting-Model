# Permanent private archive (staged; database required)

Model engines 3.6, 3.7 and 3.8 are unchanged. With no database secret, the
existing session-based workflow remains available. No historical CSV downloads
have been enabled.

## Streamlit Secrets

Add these to the existing Secrets **without replacing existing keys**:

```toml
SIG_DATABASE_URL = "postgresql://DATABASE_USER:DATABASE_PASSWORD@DATABASE_HOST:5432/DATABASE_NAME"
SIG_OWNER_PASSWORD = "CHOOSE_A_LONG_UNIQUE_PASSWORD"
```

Never commit actual values. Use a private managed PostgreSQL database and a
separate application database user with permission to create the two `sig_`
tables and their indexes (or pre-create them and grant only required rights).
The app requires TLS. Use a provider-supported connection URL/port accessible
from Streamlit Community Cloud. Backups/retention must be enabled with the
chosen database provider; this archive is not a substitute for database backups.

Once configured, the app gates archive reads, uploads, tests and API requests
behind the owner password. It fails closed if the database is unavailable.
The old GitHub backtest export is bypassed when the private archive is active.

## Stored data

- Original uploaded historical CSV files, including bookmaker closing odds,
  keyed by SHA-256; no provider files are written to the Git repository.
- API match responses, cached for six hours, scoped by a hash of the API key.
- Download reservations committed **before** network calls; success/failure and
  429 cooldown survive app restart. Shared PostgreSQL advisory locks serialize
  reservations across sessions. One request per seven seconds is enforced.
- Versioned workspace snapshots contain match data, odds, coverage, backtests,
  experiment results and signatures. An optimistic write check rejects stale
  sessions rather than silently overwriting another browser's changes.

Previous downloads made outside the register cannot be inferred. Automatic
Football-Data.co.uk downloads remain disabled. The store supports a rolling
seven-day quota, but this is not authorization to download or proof that all
provider limits are covered. Provider policy: https://football-data.co.uk/contact.php

## Deployment acceptance checks (require actual database)

1. Unauthenticated viewer cannot read or change the archive.
2. Connect with owner password; upload an existing CSV and run an experiment.
3. Open a fresh browser session and confirm source file and results restore.
4. Fetch one API league/season; repeat in a new session within six hours:
   same matches, no extra download reservation.
5. Confirm simultaneous reservations cannot bypass spacing or weekly quotas.
6. Confirm 429 cooldown survives a new Store instance/app restart.
7. Make changes in two sessions; stale save must be rejected.
8. Temporarily use invalid database settings: no fallback network calls.
9. Run original model smoke checks and verify no model engine files changed.

Never test quotas by repeatedly downloading from the real provider. Use a
throwaway database and mocked HTTP responses for those tests.
