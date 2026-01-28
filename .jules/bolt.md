## 2025-02-12 - [psycopg2 execute_values]
**Learning:** `execute_values` requires the SQL query to be a string, not a `Composed` object. If using `psycopg2.sql`, you must call `.as_string(conn)`.
**Action:** Always verify `as_string` conversion when mixing `psycopg2.sql` and `execute_values`.

## 2025-05-20 - [dbt Verification in Sandbox]
**Learning:** `dbt compile` requires a successful database connection, even for syntax checks. `dbt ls` is a better tool for verifying project parsing and DAG integrity when a database is not available.
**Action:** Use `dbt ls` for dry-run verification in connection-less environments.
