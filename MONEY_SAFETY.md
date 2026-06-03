# CYBER CASH Money Safety

Real balances must stay attached to the exact user, agent, and admin accounts
during technical updates.

The app loads `runtime_money_guard.py` automatically through `sitecustomize.py`.
It blocks destructive SQL that can clear protected money data, including:

- `DROP SCHEMA` or `DROP DATABASE`
- `DROP TABLE` or `TRUNCATE` on account, wallet, ledger, transaction, fund, or payment tables
- `DELETE FROM` protected account or money tables
- dropping money columns from protected tables
- mass balance updates without an account filter
- literal resets of protected money fields to `0` or `NULL`

Safety is enabled by default:

```env
CYBERCASH_REAL_MONEY_SAFETY=1
```

Only use this override for one audited maintenance command, never as a permanent
`.env` setting:

```env
CYBERCASH_ALLOW_DESTRUCTIVE_MONEY_UPDATE=I_UNDERSTAND_THIS_CAN_LOSE_REAL_MONEY
```

`runtime_database_guard.py` is also loaded automatically. It keeps local async
and sync database paths on the same PostgreSQL target:

```env
CYBERCASH_DATABASE_GUARD=1
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/cybercash
SYNC_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/cybercash
```

This avoids old SQLite/local duplicate databases for wallets, users, agents,
admin accounts, balances, and ledgers.

Before starting a fresh local backend, create the exact PostgreSQL database if
it is missing:

```powershell
powershell -ExecutionPolicy Bypass -File .\ensure_postgres_database.ps1
```

The bootstrap only creates the `cybercash` database when missing. It refuses
SQLite, mismatched async/sync targets, or another local database name so old
wallet data cannot split away from the live PostgreSQL source of truth.

To inspect old local duplicate PostgreSQL databases:

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup_duplicate_postgres_databases.ps1
```

To delete a verified old duplicate, pass the exact duplicate database name and
the required confirmation phrase:

```powershell
powershell -ExecutionPolicy Bypass -File .\cleanup_duplicate_postgres_databases.ps1 --drop OLD_DB_NAME --confirm DELETE_OLD_DUPLICATE_DATABASE
```

The cleanup script protects `cybercash`, `postgres`, and template databases. It
backs up the duplicate with `pg_dump` before deletion when PostgreSQL client
tools are available, and refuses unclear database names so real funds are not
removed by accident.

To verify the live fintech database target and audit duplicate account, wallet,
and ledger inputs:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_fintech_database_safety.ps1
```

The verifier confirms async/sync URLs target the same PostgreSQL database, then
checks common account, wallet, transaction, ledger, transfer, deposit, and
withdrawal tables for duplicate business keys and invalid money values. It does
not delete live records automatically; duplicate money-bearing rows must be
merged or removed through an audited maintenance task.
