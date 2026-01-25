## 2026-01-25 - [Batch Database Inserts with execute_values]
**Learning:** `execute_values` is much faster than looping inserts, but it requires the SQL query to be a string. When using `psycopg2.sql`, explicit `.as_string(conn)` conversion is required because `execute_values` might not handle `Composed` objects correctly or safely in all contexts.
**Action:** Always use `execute_values` for bulk inserts and ensure `Composed` SQL objects are converted to strings before passing them.
