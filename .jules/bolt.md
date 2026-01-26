## 2025-02-12 - [psycopg2 execute_values]
**Learning:** `execute_values` requires the SQL query to be a string, not a `Composed` object. If using `psycopg2.sql`, you must call `.as_string(conn)`.
**Action:** Always verify `as_string` conversion when mixing `psycopg2.sql` and `execute_values`.
