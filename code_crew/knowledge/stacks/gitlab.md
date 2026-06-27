---
name: gitlab-cicd
description: GitLab CI/CD conventions — image promotion, OIDC auth, pipeline triggers, and environment gates
metadata:
  type: stack
  tags: [gitlab, gitlab-ci, cicd, oidc, ecr, ecs, promotion]
---

# GitLab CI/CD Stack

## Authentication

All pipelines authenticate to AWS via OIDC — no long-lived credentials stored in GitLab.

```yaml
# .gitlab-ci.yml snippet
assume-role: &assume-role
  - >
    export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s"
    $(aws sts assume-role-with-web-identity
    --role-arn $CICD_ROLE_ARN
    --role-session-name "gitlab-$CI_JOB_ID"
    --web-identity-token $CI_JOB_JWT_V2
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]'
    --output text))
```

GitLab project variables (`Settings → CI/CD → Variables`):
- `CICD_ROLE_ARN` — Terraform-created role (masked, not protected)
- `AWS_REGION` — e.g. `ap-southeast-2`
- `ECR_REPO` — full registry URI
- `ECR_REPO_NAME` — short name

## Image Tagging Convention

Same as GitHub stack:

| Tag | When | Trigger |
|-----|------|---------|
| `sha-<CI_COMMIT_SHA>` | Every merge to main | push to main |
| `latest` | Every merge to main | push to main |
| `rc-<sha>` | Staging promotion | `promote-staging` pipeline (agent) |
| `release-<version>` | Production promotion | `promote-and-release` pipeline (human) |

## Pipeline Files

### Build and push on merge to main

```yaml
# .gitlab-ci.yml
build:
  stage: build
  image: docker:24
  only:
    - main
  script:
    - *assume-role
    - aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
    - docker build -t $ECR_REPO:sha-$CI_COMMIT_SHORT_SHA .
    - docker push $ECR_REPO:sha-$CI_COMMIT_SHORT_SHA
    - docker tag $ECR_REPO:sha-$CI_COMMIT_SHORT_SHA $ECR_REPO:latest
    - docker push $ECR_REPO:latest
```

### `promote-staging.yml` — agent-triggered pipeline

```yaml
# .gitlab/pipelines/promote-staging.yml
promote-staging:
  stage: deploy
  environment:
    name: staging
  variables:
    IMAGE_SHA: ""      # passed by trigger
    SERVICE_NAME: ""   # passed by trigger
  script:
    - *assume-role
    - |
      MANIFEST=$(aws ecr batch-get-image \
        --repository-name $ECR_REPO_NAME \
        --image-ids imageTag=sha-$IMAGE_SHA \
        --query 'images[0].imageManifest' --output text)
      aws ecr put-image \
        --repository-name $ECR_REPO_NAME \
        --image-tag rc-$IMAGE_SHA \
        --image-manifest "$MANIFEST"
    - |
      aws ecs update-service --cluster staging --service $SERVICE_NAME --force-new-deployment
      aws ecs wait services-stable --cluster staging --services $SERVICE_NAME
```

### `promote-and-release.yml` — human-triggered only

**Agents must NOT trigger this pipeline.**

```yaml
# .gitlab/pipelines/promote-and-release.yml
promote-production:
  stage: deploy
  environment:
    name: production
    # GitLab protected environment — requires manual approval in UI
  when: manual
  variables:
    IMAGE_SHA: ""
    VERSION: ""
    SERVICE_NAME: ""
  script:
    - *assume-role
    - |
      MANIFEST=$(aws ecr batch-get-image \
        --repository-name $ECR_REPO_NAME \
        --image-ids imageTag=sha-$IMAGE_SHA \
        --query 'images[0].imageManifest' --output text)
      aws ecr put-image \
        --repository-name $ECR_REPO_NAME \
        --image-tag release-$VERSION \
        --image-manifest "$MANIFEST"
    - |
      aws ecs update-service --cluster production --service $SERVICE_NAME --force-new-deployment
      aws ecs wait services-stable --cluster production --services $SERVICE_NAME
    - |
      # Create GitLab Release
      curl --header "PRIVATE-TOKEN: $GL_TOKEN" \
        --data "name=Release $VERSION&tag_name=v$VERSION&description=$(cat RELEASE_DRAFT.md)" \
        "https://gitlab.com/api/v4/projects/$CI_PROJECT_ID/releases"
```

## Triggering a Staging Promotion (Agent Instructions)

DevOps agent uses `platform_shell` with `curl` to trigger via GitLab API:

```bash
# Trigger pipeline with variables
curl --request POST \
  --form "token=$GL_TRIGGER_TOKEN" \
  --form "ref=main" \
  --form "variables[IMAGE_SHA]=<sha>" \
  --form "variables[SERVICE_NAME]=<ecs-service>" \
  "https://gitlab.com/api/v4/projects/<project-id>/trigger/pipeline"

# Or use glab CLI
glab pipeline trigger --branch main \
  --variables "IMAGE_SHA=<sha>,SERVICE_NAME=<service>"
```

## Security Constraints

- Agents may trigger `promote-staging` pipeline (dev → staging)
- Agents MUST NOT trigger `promote-and-release` pipeline (staging → production)
- Production environment must be a GitLab protected environment with required approvers
- Production promotion requires a human to click "Run" on the manual job in the GitLab UI
