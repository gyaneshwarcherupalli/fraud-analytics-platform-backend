"""Airflow DAG for Kafka transaction ingestion micro-batches."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from app.services.pipelines.ingestion_pipeline import run_ingestion_batch


DEFAULT_ARGS = {
    "owner": "fraud-platform",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
    "execution_timeout": timedelta(minutes=5),
}


with DAG(
    dag_id="transaction_ingestion_pipeline",
    description="Validate and persist transaction events from Kafka",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="*/1 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["fraud", "ingestion", "kafka"],
) as dag:
    ingest_transactions = PythonOperator(
        task_id="ingest_transaction_batch",
        python_callable=run_ingestion_batch,
        op_kwargs={"timeout_ms": 5000, "max_records": 500},
    )
