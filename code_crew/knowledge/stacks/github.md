---
name: github-actions-cicd
description: GitHub Actions CI/CD conventions — image promotion, OIDC auth, workflow_dispatch, and environment gates
metadata:
  type: stack
  tags: [github, gha, cicd, oidc, ecr, ecs, promotion]
---

# GitHub Actions CI/CD Stack

## Authentication

All workflows authenticate to AWS via OIDC — no long-lived secrets stored in GitHub.

Terraform creates the CICD role (`cicd_role_arn`). GitHub Actions assumes it via:

```yaml
permissions:
  id-token: write
  contents: read

- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ vars.CICD_ROLE_ARN }}
    aws-region: ${{ vars.AWS_REGION }}
```

## Image Tagging Convention

| Tag | When | Trigger |
|-----|------|---------|
| `sha-<git-sha>` | Every merge to main | push to main |
| `latest` | Every merge to main | push to main |
| `rc-<sha>` | Staging promotion | `promote-staging.yml` workflow |
| `release-<version>` | Production promotion | `promote-and-release.yml` workflow (human) |

## Workflow Files

### `build-and-push.yml` — Build on merge to main

```yaml
on:
  push:
    branches: [main]

jobs:
  build:
    steps:
      - uses: aws-actions/amazon-ecr-login@v2
      - name: Build and push
        run: |
          SHA_TAG=${{ vars.ECR_REPO }}:sha-${{ github.sha }}
          docker build -t $SHA_TAG .
          docker push $SHA_TAG
          docker tag $SHA_TAG ${{ vars.ECR_REPO }}:latest
          docker push ${{ vars.ECR_REPO }}:latest
```

### `promote-staging.yml` — Promote sha image to staging

Triggered by DevOps (or automated after DoD check passes):

```yaml
on:
  workflow_dispatch:
    inputs:
      image_sha:
        description: 'Git SHA of the image to promote'
        required: true
      service:
        description: 'ECS service name'
        required: true

jobs:
  promote:
    steps:
      - name: Tag as rc
        run: |
          MANIFEST=$(aws ecr batch-get-image \
            --repository-name ${{ vars.ECR_REPO_NAME }} \
            --image-ids imageTag=sha-${{ inputs.image_sha }} \
            --query 'images[0].imageManifest' --output text)
          aws ecr put-image \
            --repository-name ${{ vars.ECR_REPO_NAME }} \
            --image-tag rc-${{ inputs.image_sha }} \
            --image-manifest "$MANIFEST"

      - name: Force ECS redeploy (staging)
        run: |
          aws ecs update-service \
            --cluster staging \
            --service ${{ inputs.service }} \
            --force-new-deployment
          aws ecs wait services-stable \
            --cluster staging \
            --services ${{ inputs.service }}
```

### `promote-and-release.yml` — Human-triggered production promotion

**Never triggered by agents. Human only.**

```yaml
on:
  workflow_dispatch:
    inputs:
      image_sha:
        description: 'Git SHA to promote to production'
        required: true
      version:
        description: 'Semantic version (e.g. 0.6.0)'
        required: true
      service:
        description: 'ECS service name'
        required: true

jobs:
  promote-prod:
    environment: production    # requires GitHub environment approval
    steps:
      - name: Tag as release
        run: |
          MANIFEST=$(aws ecr batch-get-image \
            --repository-name ${{ vars.ECR_REPO_NAME }} \
            --image-ids imageTag=sha-${{ inputs.image_sha }} \
            --query 'images[0].imageManifest' --output text)
          aws ecr put-image \
            --repository-name ${{ vars.ECR_REPO_NAME }} \
            --image-tag release-${{ inputs.version }} \
            --image-manifest "$MANIFEST"

      - name: Force ECS redeploy (production)
        run: |
          aws ecs update-service \
            --cluster production \
            --service ${{ inputs.service }} \
            --force-new-deployment
          aws ecs wait services-stable \
            --cluster production \
            --services ${{ inputs.service }}

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{ inputs.version }}
          name: Release ${{ inputs.version }}
          body_path: RELEASE_DRAFT.md
          draft: false
```

## Triggering a Staging Promotion (Agent Instructions)

DevOps agent uses `platform_shell` to trigger via GitHub CLI:

```bash
gh workflow run promote-staging.yml \
  --field image_sha=<sha> \
  --field service=<ecs-service-name>

# Wait for completion
gh run watch $(gh run list --workflow=promote-staging.yml --limit=1 --json databaseId -q '.[0].databaseId')
```

## Environment Variables Required

| Variable | Where | Value |
|----------|-------|-------|
| `CICD_ROLE_ARN` | GitHub env vars | Created by Terraform |
| `ECR_REPO` | GitHub env vars | `<account>.dkr.ecr.<region>.amazonaws.com/<name>` |
| `ECR_REPO_NAME` | GitHub env vars | Short repo name (without registry prefix) |
| `AWS_REGION` | GitHub env vars | e.g. `ap-southeast-2` |

## Security Constraints

- Agents may trigger `promote-staging.yml` (dev → staging)
- Agents MUST NOT trigger `promote-and-release.yml` (staging → production)
- Production promotion requires a human to manually run `workflow_dispatch` via GitHub UI or CLI
- The `production` GitHub environment should have required reviewers configured
