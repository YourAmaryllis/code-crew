---
type: CrewAI Task
title: Monitoring Setup
description: Design CloudWatch dashboards, alarms, and anomaly detection for the sprint's service
tags: [monitoring, cloudwatch, alerts, observability, terraform, phase-21]
timestamp: 2026-06-17T00:00:00Z
agent: monitoring_engineer
context_agents:
  - terraform_engineer
expected_output: >
  Terraform resource blocks for CloudWatch alarms, dashboards, log metric filters,
  and SNS topics. A dashboard JSON definition. A monitoring signal inventory table
  with metric name, alarm thresholds (warning/critical), and notification routing.
---

Design and produce Terraform-managed monitoring for the service(s) affected by this sprint.

Load SOP-10-Post-Launch-Support via the `sop_reader` tool to confirm monitoring expectations.

**Signal inventory** — for each service, identify and document:

| Signal | Metric | Warning threshold | Critical threshold | Notification |
|--------|--------|------------------|--------------------|--------------|
| Error rate | `5XXErrorRate` | >1% | >5% | Slack / PagerDuty |
| Latency p95 | `TargetResponseTime` p95 | >500ms | >2s | PagerDuty |
| Task health | ECS `RunningTaskCount` | <desired | 0 | PagerDuty |
| ... | ... | ... | ... | ... |

Also include business-critical counters specific to the feature (e.g., `DatasetRegistrations`,
`AttestationFailures`).

**Terraform resources to produce:**
- `aws_cloudwatch_metric_alarm` for each signal × severity
- `aws_cloudwatch_dashboard` with JSON widget definitions
- `aws_cloudwatch_log_metric_filter` for log-based metrics
- `aws_sns_topic` and `aws_sns_topic_subscription` for routing (if new topic needed)
- All resources tagged: `Environment`, `Project`, `ManagedBy = "terraform"`

**Anomaly detection**: for stable metrics (e.g., request rate, error rate in business hours),
use `aws_cloudwatch_metric_alarm` with `ANOMALY_DETECTION_BAND` instead of static thresholds.

**Naming conventions**:
- Alarm: `<service>-<env>-<metric>-<severity>` (e.g., `portal-staging-5xx-critical`)
- Dashboard: `<service>-<env>` (e.g., `portal-staging`)

Produce the full Terraform HCL and a dashboard JSON draft. All output is for human
review before apply.
