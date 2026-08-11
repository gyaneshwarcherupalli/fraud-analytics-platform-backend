"""Airflow DAG for enrichment, fraud scoring, and alert generation."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from app.services.pipelines.fraud_scoring_pipeline import run_fraud_scoring_batch


DEFAULT_ARGS = {
    "owner": "fraud-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=10),
}


with DAG(
    dag_id="fraud_scoring_pipeline",
    description="Enrich unscored transactions, score fraud risk, and generate alerts",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="*/2 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["fraud", "ml", "scoring", "alerts"],
) as dag:
    score_transactions = PythonOperator(
        task_id="score_transaction_batch",
        python_callable=run_fraud_scoring_batch,
        op_kwargs={"batch_size": 250},
    )
