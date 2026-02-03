from airflow.sdk import dag, task, task_group
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.task.trigger_rule import TriggerRule
from airflow.providers.slack.notifications.slack import send_slack_notification
from datetime import datetime
from pathlib import Path
import os

# tasks
from include.tasks.checking_b4_extraction import is_holiday, create_today_folder, check_files_exist_in_folder
from include.tasks.extract_stock_info import extract_most_active_stocks, extract_price_top3_most_active_stocks, extract_price_top3_most_active_stocks, extract_news_top3_most_active_stocks, extract_biz_info_top3_most_active_stocks
from include.tasks.load_2_db import load_to_db, load_2_db_biz_lookup

# dbt
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig
from cosmos.profiles.postgres import PostgresUserPasswordProfileMapping
import os



@dag(
    start_date=datetime(2023, 1, 1),
    schedule="0 21 * * 1-5",
    catchup=False,
    tags=['stock', 'price','most_active'],
    max_active_runs=1,
    max_active_tasks=1,
    on_success_callback=[
        send_slack_notification(
            slack_conn_id='slack',
            text=":tada: DAG {{ dag.dag_id }} Succeeded on {{ ds }}",
            channel='general'
        )
    ],
    on_failure_callback=[
        send_slack_notification(
            slack_conn_id='slack',
            text=":red_circle: DAG {{ dag.dag_id }} Failed on {{ ds }}",
            channel='general'
        )
    ],
)
def most_active_dag():

    end_task = EmptyOperator(task_id="end_task")

    # Task to check if today is a holiday
    @task.branch(task_id="check_holiday")
    def check_holiday():
        holiday = is_holiday()
        if holiday:
            return "end_task"
        else:
            return "create_today_folder"
    
    @task(task_id="create_today_folder", pool="api_pool")
    def create_date_folder():
        return create_today_folder()

    # Task Group for Extraction from API
    @task_group(group_id='Extraction_from_API')
    def extraction_group():
        
        @task.branch(task_id="check_existing_files", pool="api_pool")
        def check_existing_files(folder_path):
            """Check which files exist and determine where to start extraction"""
            next_task = check_files_exist_in_folder()
            
            # Return full task path within the task group
            if next_task == "skip_extraction":
                return "Extraction_from_API.extraction_complete"
            else:
                return f"Extraction_from_API.{next_task}"
    
        # Use pool to limit concurrent API calls
        @task(task_id="extract_most_active_stocks", pool="api_pool")
        def most_active_stocks_task(folder_path, **context):
            return extract_most_active_stocks(folder_path, **context)
        
        @task(task_id="price_top3_most_active_stocks", pool="api_pool", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
        def price_top3_most_active_stocks_task(folder_path, **context):
            return extract_price_top3_most_active_stocks(folder_path, **context)

        @task(task_id="news_top3_most_active_stocks", pool="api_pool", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
        def news_top3_most_active_stocks_task(**context):
            return extract_news_top3_most_active_stocks(**context)
        
        @task(task_id="biz_info_top3_most_active_stocks", pool="api_pool", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
        def biz_info_top3_most_active_stocks_task(**context):
            return extract_biz_info_top3_most_active_stocks(**context)
        
        # Empty task to mark extraction complete (convergence point)
        extraction_complete = EmptyOperator(
            task_id="extraction_complete",
            trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
        )
        
        # Task instances
        check_files = check_existing_files(create_folder)
        most_active = most_active_stocks_task(create_folder)
        price_top3 = price_top3_most_active_stocks_task(create_folder)
        news_top3 = news_top3_most_active_stocks_task()
        biz_info_top3 = biz_info_top3_most_active_stocks_task()

        # Dependencies - branch to the appropriate starting point
        check_files >> [most_active, price_top3, news_top3, biz_info_top3, extraction_complete]
        
        # Sequential flow for extraction tasks
        most_active >> price_top3 >> news_top3 >> biz_info_top3 >> extraction_complete


    # Task Group for Loading to Database (Injection)
    @task_group(group_id='Loading_to_DB')
    def loading_group():
        @task(task_id="load_data_to_db")
        def load_data_2_db(**context):
            load_to_db(**context)

        @task(task_id="load_2_db_biz_lookup")
        def load_2_db_biz_lookup_task(**context):
            load_2_db_biz_lookup(**context)

        load_data_task = load_data_2_db()
        load_data_task_2 = load_2_db_biz_lookup_task()
        
        load_data_task >> load_data_task_2    

    # Task Group for dbt transformations
    CONNECTION_ID = "postgres_stock"
    DB_NAME = "stocks_db"
    SCHEMA_NAME = "public"
    MODEL_TO_QUERY = "mart_price_news__analysis"
    
    # The path to the dbt project
    current_path = Path(__file__).resolve().parent
    dbt_project_path = current_path / "include" / "dbt" / "my_project"
    
    if not dbt_project_path.exists():
        dbt_project_path = current_path.parent / "include" / "dbt" / "my_project" # Local

    DBT_PROJECT_PATH = str(dbt_project_path)

    profile_config = ProfileConfig(
        profile_name="my_project",
        target_name=os.getenv("DBT_TARGET", "dev"),
        profile_mapping=PostgresUserPasswordProfileMapping(
            conn_id=CONNECTION_ID,
            profile_args={"schema": "public"},
        ),
    )

    @task_group(group_id="dbt_run")
    def dbt_run():
        transform_data = DbtTaskGroup(
            group_id="dbt_transform_data",
            project_config=ProjectConfig(DBT_PROJECT_PATH),
            profile_config=profile_config,
            default_args={"retries": 2},
        )

        query_table = SQLExecuteQueryOperator(
            task_id="query_table_to_check",
            conn_id=CONNECTION_ID,
            sql=f"SELECT * FROM {DB_NAME}.{SCHEMA_NAME}.{MODEL_TO_QUERY} LIMIT 10;",
        )
        
        transform_data >> query_table


    # Task instances
    check_holiday_task = check_holiday()
    create_folder = create_date_folder()
    extraction = extraction_group()
    loading = loading_group()
    dbt_tasks = dbt_run()

    # --- Task Dependencies ---
    check_holiday_task >> [create_folder, end_task]
    create_folder >> extraction >> loading >> dbt_tasks >> end_task

most_active_dag()