## 2025-02-12 - [psycopg2 execute_values]
**Learning:** `execute_values` requires the SQL query to be a string, not a `Composed` object. If using `psycopg2.sql`, you must call `.as_string(conn)`.
**Action:** Always verify `as_string` conversion when mixing `psycopg2.sql` and `execute_values`.

## 2025-02-12 - [ThreadPoolExecutor Memory Usage]
**Learning:** Using `list(executor.map(...))` allows parallel processing but defeats the purpose of streaming generators by loading all results into RAM at once. For memory-efficient parallel processing (e.g. bulk DB inserts), use `as_completed` inside a generator to yield results incrementally.
**Action:** When parallelizing generators, always use the `as_completed` pattern to maintain streaming behavior.
