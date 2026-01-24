## 2025-02-23 - Robust Parallelization in Airflow
**Learning:** When parallelizing sequential tasks in Airflow that share data, strictly using XComs creates a fragility: if an upstream task is skipped (e.g. due to `BranchPythonOperator`), downstream tasks cannot pull its XCom.
**Action:** Implement fallback logic in data retrieval helpers (e.g. `get_top3_stocks`) to check persistent storage (MinIO/S3) if XCom is missing, enabling tasks to run independently or in parallel during restart/catchup scenarios.
