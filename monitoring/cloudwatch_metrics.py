"""CloudWatch metric publishing and monitoring resource provisioning."""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from botocore.exceptions import BotoCoreError, ClientError

from app.core.aws import aws_client
from app.core.config import settings
from app.utils.exceptions import ExternalServiceException


logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cloudwatch")


class CloudWatchMetrics:
    """Publish platform metrics with consistent environment dimensions."""

    def __init__(self, client=None, namespace: Optional[str] = None) -> None:
        self.client = client or aws_client("cloudwatch")
        self.namespace = namespace or settings.cloudwatch_namespace

    def put_metric(
        self, name: str, value: float, *, unit: str = "Count",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> None:
        self.put_metrics([{"name": name, "value": value, "unit": unit,
                           "dimensions": dimensions or {}}])

    def put_metrics(self, metrics: Iterable[Dict[str, Any]]) -> None:
        """Publish metrics in CloudWatch's maximum batches of twenty."""
        if not settings.cloudwatch_enabled:
            return
        payload: List[Dict[str, Any]] = []
        for metric in metrics:
            dimensions = {"Environment": settings.cloudwatch_environment}
            dimensions.update(metric.get("dimensions") or {})
            payload.append({
                "MetricName": metric["name"],
                "Value": float(metric["value"]),
                "Unit": metric.get("unit", "Count"),
                "Timestamp": metric.get("timestamp", datetime.now(timezone.utc)),
                "Dimensions": [{"Name": key, "Value": str(value)} for key, value in dimensions.items()],
            })
        try:
            for index in range(0, len(payload), 20):
                self.client.put_metric_data(Namespace=self.namespace, MetricData=payload[index:index + 20])
        except (BotoCoreError, ClientError) as exc:
            raise ExternalServiceException(f"CloudWatch metric publishing failed: {exc}") from exc


def publish_metrics_async(metrics: Iterable[Dict[str, Any]]) -> None:
    """Publish without adding AWS network latency to API request handling."""
    if not settings.cloudwatch_enabled:
        return
    metric_list = list(metrics)

    def _publish() -> None:
        try:
            CloudWatchMetrics().put_metrics(metric_list)
        except Exception:
            logger.exception("Unable to publish CloudWatch metrics")

    _executor.submit(_publish)


def provision_monitoring(config_path: str | Path = "monitoring/alerts_config.json") -> Dict[str, int]:
    """Idempotently create configured alarms and the operations dashboard."""
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    client = aws_client("cloudwatch")
    namespace = config.get("namespace", settings.cloudwatch_namespace)
    actions = [settings.cloudwatch_alarm_topic_arn] if settings.cloudwatch_alarm_topic_arn else []
    try:
        for alarm in config.get("alarms", []):
            client.put_metric_alarm(
                AlarmName=f"{settings.cloudwatch_environment}-{alarm['name']}",
                AlarmDescription=alarm.get("description", ""),
                Namespace=namespace,
                MetricName=alarm["metric_name"],
                Dimensions=[{"Name": "Environment", "Value": settings.cloudwatch_environment}],
                Statistic=alarm.get("statistic", "Sum"),
                Period=int(alarm.get("period", 60)),
                EvaluationPeriods=int(alarm.get("evaluation_periods", 1)),
                DatapointsToAlarm=int(alarm.get("datapoints_to_alarm", 1)),
                Threshold=float(alarm["threshold"]),
                ComparisonOperator=alarm["comparison_operator"],
                TreatMissingData=alarm.get("treat_missing_data", "notBreaching"),
                AlarmActions=actions,
                OKActions=actions,
            )
        widgets = [{
            "type": "metric", "x": 0, "y": i * 6, "width": 24, "height": 6,
            "properties": {
                "title": widget["title"], "region": settings.aws_region,
                "metrics": [[namespace, metric, "Environment", settings.cloudwatch_environment]
                            for metric in widget["metrics"]],
                "period": widget.get("period", 60), "stat": widget.get("stat", "Sum"),
            },
        } for i, widget in enumerate(config.get("dashboard", []))]
        client.put_dashboard(
            DashboardName=f"{settings.cloudwatch_environment}-fraud-analytics",
            DashboardBody=json.dumps({"widgets": widgets}),
        )
        return {"alarms": len(config.get("alarms", [])), "widgets": len(widgets)}
    except (BotoCoreError, ClientError) as exc:
        raise ExternalServiceException(f"CloudWatch provisioning failed: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision CloudWatch alarms and dashboard")
    parser.add_argument("--config", default="monitoring/alerts_config.json")
    args = parser.parse_args()
    print(provision_monitoring(args.config))
