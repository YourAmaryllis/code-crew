---
name: SDLC-DevOps-MonitoringObservability
description: Observability standards, alerting thresholds, log management, and post-launch operations
metadata:
  type: process
  role: devops
  phase: "12, 22"
---

# Monitoring & Observability

---

## Observability Pillars

| Pillar | Tool | What we measure |
|--------|------|----------------|
| Metrics | CloudWatch, custom dashboards | Latency, error rates, throughput, saturation |
| Logs | CloudWatch Logs, structured JSON | Application events, errors, access logs |
| Traces | AWS X-Ray | Request traces across service boundaries |
| Alerts | CloudWatch Alarms → PagerDuty / Slack | Threshold breaches |

---

## Structured Logging

All services emit structured JSON logs:

```json
{
  "level": "error",
  "service": "auth-svc",
  "trace_id": "abc123",
  "user_id": "usr_xyz",
  "message": "email verification failed",
  "error": "token expired",
  "timestamp": "2026-06-18T14:32:00Z"
}
```

Rules:
- No PII in logs (email, full name, PHI) — use opaque IDs
- Every log line includes `service`, `trace_id`, and `timestamp`
- Error logs include the full error message (but not stack traces in prod — use trace)
- Log levels: `debug` (dev only), `info`, `warn`, `error`

---

## Alert Thresholds

### ECS Services

| Metric | Warning | Critical |
|--------|---------|---------|
| Task healthy count | < desired | = 0 |
| CPU utilization | > 70% | > 90% |
| Memory utilization | > 75% | > 90% |

### ALB (API Gateway)

| Metric | Warning | Critical |
|--------|---------|---------|
| 5xx error rate | > 1% | > 5% |
| 4xx error rate | > 10% | > 25% |
| P99 latency | > 2s | > 5s |
| P50 latency | > 500ms | > 1s |

### RDS

| Metric | Warning | Critical |
|--------|---------|---------|
| Connection count | > 70% max | > 90% max |
| CPU utilization | > 70% | > 90% |
| Storage free | < 20% | < 10% |
| Read/write latency | > 100ms | > 500ms |

---

## Alert Routing

| Severity | Notification | Response time |
|----------|-------------|---------------|
| Critical | PagerDuty (on-call) | 15 min |
| Warning | Slack `#ops-alerts` | 2 hours |
| Info | Slack `#ops-info` | Best effort |

On-call rotation covers all Critical alerts 24/7.

---

## Runbooks

Every Critical alert has a runbook:
- Location: `designs/PLAN/runbooks/<alert-name>.md`
- Contains: what the alert means, diagnostic steps, resolution steps, escalation path
- Runbooks reviewed quarterly and after each incident

---

## Post-Launch Care (Phase 22)

After production deployment:

1. **24-hour watch**: DevOps Lead monitors error rates and latency for 24 hours
2. **72-hour check**: review metrics for anomalies introduced by the release
3. **Customer feedback**: monitor support tickets and Slack for issues
4. **Incident response**: any P1/P2 incident triggers the incident response process

---

## Incident Response

**Incident severity:**
| Level | Definition | Response |
|-------|-----------|---------|
| P0 | Total service outage | All hands; 15-min war room |
| P1 | Major feature unavailable | On-call + tech lead; 30-min response |
| P2 | Degraded service, workaround exists | On-call; 2-hour response |
| P3 | Minor bug, no service impact | Normal sprint process |

**Incident process:**
1. Detect (alert or user report)
2. Acknowledge in PagerDuty
3. Open incident Slack channel `#incident-YYYY-MM-DD`
4. Mitigate (rollback or hotfix)
5. Resolve and verify
6. Post-mortem within 48 hours (P0/P1) or 1 week (P2)

---

## Security Monitoring

- **AWS GuardDuty**: threat detection, anomaly detection on API calls
- **CloudTrail**: all API calls logged; production access fully auditable
- **Access log review**: Security Lead reviews access logs weekly
- **Anomaly alerts**: unusual access patterns (off-hours, new IP, bulk operations) trigger Slack alert
