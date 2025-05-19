# PropPulse CI/CD Coverage Analysis

## Current Workflow Coverage

### 1. CI Workflow (`ci.yml`)
- **Trigger**: Pull requests to `main` branch
- **Coverage**:
  - Runs tests with pytest and coverage reporting
  - Performs linting with ruff
  - Builds Docker image (without pushing)
  - Uploads coverage report as artifact

### 2. CD Workflow (`cd.yml`)
- **Trigger**: Push to `main` branch or manual dispatch
- **Coverage**:
  - Builds and pushes Docker image to GitHub Container Registry
  - Deploys to Azure Container Apps using Bicep
  - Generates and uploads deployment log as artifact
  - Supports multiple environments (dev, staging, prod)

### 3. Combined CI/CD Workflow (`ci-cd.yml`)
- **Trigger**: Push to `main` or `develop` branches, or pull requests to these branches
- **Coverage**:
  - More extensive linting (flake8, black, isort for Python; npm lint for frontend)
  - Runs tests with coverage for both backend and frontend
  - Builds and pushes separate backend and frontend Docker images
  - Deploys to development environment using Terraform
  - Posts deployment status as PR comment

### 4. Progress Report Workflow (`progress_report.yml`)
- **Trigger**: Weekly schedule (Monday 9:00 AM UTC) or manual dispatch
- **Coverage**:
  - Generates weekly progress report with metrics:
    - Issues closed
    - PRs merged
    - Deployments
    - Average lead time
  - Creates PR with the report
  - Uploads report as artifact

### 5. Webhook Setup Workflow (`setup_webhooks.yml`)
- **Trigger**: Manual dispatch
- **Coverage**:
  - Sets up repository webhooks for issues, pull requests, and workflow runs
  - Sets up organization webhooks for project events

## Gaps and Missing Components

### 1. GitHub Projects Automation
- No script to automatically manage GitHub Projects
- Missing functionality:
  - Adding new issues to project with status "Todo"
  - Moving linked issues to "Done" when PR is merged
  - Setting status to "Blocked" on CI failure

### 2. README Badges
- No badges for:
  - Build status
  - Test coverage
  - Deployment status
  - Risk-engine green rate
  - Project completion percentage

### 3. Workflow Redundancy
- Overlap between `ci.yml`, `cd.yml`, and `ci-cd.yml`
- Potential for consolidation or clearer separation of concerns

### 4. Other Gaps
- No explicit handling of GitHub Projects GraphQL queries
- No documentation for secrets management
- No optimization for workflow runtime

## Recommendations

1. Implement `scripts/auto_project.py` for GitHub Projects automation
2. Add badges to README.md
3. Consider consolidating workflows or clarifying their distinct purposes
4. Implement weekly progress report generation if needed
5. Ensure all workflows complete within 15 minutes
6. Document required secrets and their management
