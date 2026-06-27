---
name: SDLC-DevOps-ReleaseProcess
description: Release lifecycle from staging promotion to production deploy, release notes, rollback, and post-deploy validation
metadata:
  type: process
  role: devops
  phase: "20, 21"
---

# Release Process

Production deployment is **human-triggered only**. No automation promotes to production without explicit Release Manager action.

---

## Release Lifecycle

```
1. Sprint complete → all stories DoD-checked
2. Staging promotion (DevOps Lead)
3. Staging acceptance testing (QA Lead)
4. Staging acceptance sign-off
5. Release Manager review
6. Production promotion (Release Manager via workflow_dispatch)
7. Post-deploy validation
8. GitHub Release created
```

---

## Step 2: Staging Promotion

```bash
# Via GitHub Actions UI or gh CLI
gh workflow run promote-and-release.yml \
  -f env=staging \
  -f service=portal,auth-svc,curation-svc
```

What happens:
- Latest `dev` image tagged as `0.N-rc1` (or `0.N-rcN+1` if RC exists)
- ECS task definition updated with new image tag
- ECS service updated (rolling deployment)
- Health checks verified
- Slack notification sent

---

## Step 3–4: Staging Acceptance

QA Lead runs the E2E and smoke test suites against staging:

```bash
PLAYWRIGHT_BASE_URL=https://staging.your-org.com \
  npx playwright test --grep @smoke
```

Sign-off comment on the release Jira ticket:
```
Staging acceptance: ✅ PASSED
Smoke tests: [GitHub Actions run URL]
E2E tests: [GitHub Actions run URL]
Date: YYYY-MM-DD
QA Lead: [name]
```

Production is blocked until this comment exists.

---

## Step 6: Production Promotion

Release Manager triggers via GitHub Actions `workflow_dispatch`:

```bash
gh workflow run promote-and-release.yml \
  -f env=prod \
  -f release_version=0.N
```

What happens:
- RC image retagged as `0.N` (immutable production tag)
- ECS task definition updated
- Blue/green deployment: new tasks started, traffic cut over on health check
- Old tasks drained
- GitHub Release created with auto-generated release notes
- Deployment metadata logged (version, timestamp, deployer identity)

---

## Release Notes

GitHub Release notes are auto-generated from merged PRs since the last release:

```bash
gh release create v0.N \
  --generate-notes \
  --title "Release 0.N"
```

The Release Manager reviews and edits before publishing. Customer-facing changes are written in plain English (not commit messages).

---

## Post-Deploy Validation

After production deploy:

1. Verify ECS tasks healthy (desired = running count)
2. Run smoke test suite against production: `@smoke` tagged scenarios
3. Check CloudWatch: no spike in 5xx errors in first 10 minutes
4. Check key business metrics: no anomalies (login success rate, API latency)
5. Update Jira release version on completed stories

---

## Rollback

**Immediate rollback (< 10 min after deploy):**
```bash
# Redeploy previous task definition
aws ecs update-service \
  --cluster your-app-prod \
  --service auth-svc \
  --task-definition auth-svc:PREVIOUS_REVISION
```

**Planned rollback:**
1. Identify the last stable image tag (e.g. `0.N-1`)
2. Run promote-and-release with `release_version=0.N-1`
3. Document rollback in change control log
4. Post-mortem required if customer impact occurred

---

## Deployment Metadata

Every production deploy records:
```json
{
  "service": "auth-svc",
  "version": "0.5",
  "image_tag": "0.5",
  "deployed_by": "release-manager@your-org.com",
  "deployed_at": "2026-06-18T14:32:00Z",
  "github_run_id": "XXXXXXX",
  "commit_sha": "abc1234"
}
```

Stored in SSM Parameter Store and/or deployment log S3 bucket for audit purposes.

---

## Hotfix Release

For critical production bugs:

1. Branch from `main`: `hotfix/PROJ-NNN-slug`
2. Fix + tests
3. PR to `main` — expedited review (no phase skipping, same DoD)
4. After merge, promote directly: dev → prod (skipping normal staging acceptance if P0)
5. Post-mortem within 48 hours if customer impact
6. Document exception in change control log
