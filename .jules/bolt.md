## 2025-02-12 - [psycopg2 execute_values]
**Learning:** `execute_values` requires the SQL query to be a string, not a `Composed` object. If using `psycopg2.sql`, you must call `.as_string(conn)`.
**Action:** Always verify `as_string` conversion when mixing `psycopg2.sql` and `execute_values`.

## 2025-02-12 - [Parallel S3 Downloads in Airflow]
**Learning:** Sequential downloading of multiple small files from object storage (S3/MinIO) in Airflow tasks significantly adds up latency. `ThreadPoolExecutor` provides a clean, standard library way to parallelize this without complex async logic.
**Action:** When processing multiple files in a single task, always consider `ThreadPoolExecutor` to overlap I/O wait times.
