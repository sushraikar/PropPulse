# PropPulse CI/CD Testing Instructions

## Overview

This document provides instructions for testing the CI/CD and progress tracking implementation for PropPulse. The implementation includes GitHub Actions workflows, GitHub Projects automation, README badges, and progress reporting.

## Prerequisites

Before testing, ensure you have the following:

1. GitHub repository with the PropPulse codebase
2. GitHub Personal Access Token with the following permissions:
   - `repo` (full control of private repositories)
   - `workflow` (update GitHub Action workflows)
   - `admin:org` (if using organization projects)
   - `gist` (for badge updates)
3. Required GitHub Secrets configured in the repository:
   - `GITHUB_TOKEN`: Automatically provided by GitHub Actions
   - `AZURE_CREDENTIALS`: Azure service principal credentials
   - `GHCR_TOKEN`: GitHub Container Registry token
   - `GIST_SECRET`: Token for updating badge gists
   - `COVERAGE_GIST_ID`: Gist ID for coverage badge
   - `BUILD_STATUS_GIST_ID`: Gist ID for build status badge
   - `DEPLOY_STATUS_GIST_ID`: Gist ID for deployment status badge
   - `PROJECT_GIST_ID`: Gist ID for project completion badge
   - `PROJECT_NUMBER`: GitHub Project number (set automatically by setup_project.yml)

## Testing Steps

### 1. GitHub Project Setup

1. Run the `setup_project.yml` workflow:
   ```
   gh workflow run setup_project.yml -F project_name="PropPulse Roadmap"
   ```
2. Verify that the GitHub Project is created with the required fields:
   - Status (Todo, In-Progress, Done, Blocked)
   - ETA
   - Priority
3. Confirm that the `PROJECT_NUMBER` secret is set in the repository

### 2. CI Workflow Testing

1. Create a new branch and make a change to the codebase
2. Create a pull request to the `main` branch
3. Verify that the CI workflow runs automatically
4. Check that tests and linting are executed
5. Confirm that the coverage badge is updated
6. Verify that the Docker image is built

### 3. GitHub Projects Automation Testing

1. Create a new issue in the repository
2. Verify that the issue is automatically added to the GitHub Project with status "Todo"
3. Create a PR that references the issue (e.g., "Fixes #123")
4. Merge the PR
5. Verify that the linked issue is moved to "Done" in the GitHub Project
6. Intentionally break a test and create a PR
7. Verify that the CI workflow fails and the linked issue is marked as "Blocked"

### 4. CD Workflow Testing

1. Push a change to the `main` branch
2. Verify that the CD workflow runs automatically
3. Check that the Docker image is built and pushed to GitHub Container Registry
4. Confirm that the deployment to Azure is executed
5. Verify that the deployment status badge is updated
6. Run the CD workflow manually for a different environment:
   ```
   gh workflow run cd.yml -F deploy_env=staging
   ```
7. Verify that the deployment log is generated and uploaded as an artifact

### 5. Project Badge Testing

1. Run the `project_badge.yml` workflow manually:
   ```
   gh workflow run project_badge.yml
   ```
2. Verify that the project completion percentage is calculated correctly
3. Check that the badge is updated in the gist
4. Confirm that the badge is displayed correctly in the README

### 6. Progress Report Testing

1. Run the sample report generator:
   ```
   python scripts/generate_sample_report.py
   ```
2. Verify that the sample report is generated with the expected format
3. Run the `progress_report.yml` workflow manually:
   ```
   gh workflow run progress_report.yml
   ```
4. Verify that a PR is created with the weekly progress report
5. Check that the report includes the required metrics:
   - Issues closed
   - PRs merged
   - Deployments
   - Average lead time

## Troubleshooting

### Common Issues

1. **Workflow Permission Errors**
   - Ensure the `GITHUB_TOKEN` has the required permissions in repository settings
   - Go to Settings > Actions > General > Workflow permissions
   - Select "Read and write permissions"

2. **GraphQL API Errors**
   - Check that the personal access token has the required scopes
   - Verify that the project number is correct
   - Ensure the organization/user name is correct in the repository name

3. **Badge Update Failures**
   - Verify that the gist IDs are correct
   - Ensure the token has gist write permissions
   - Check that the gist files exist with the expected names

4. **Deployment Failures**
   - Verify that the Azure credentials are correct
   - Check that the resource group exists
   - Ensure the Bicep template is valid

## Validation Checklist

- [ ] GitHub Project created with required fields
- [ ] CI workflow runs on pull requests
- [ ] CD workflow runs on pushes to main
- [ ] New issues are automatically added to the project
- [ ] Linked issues are moved to Done when PRs are merged
- [ ] Issues are marked as Blocked on CI failure
- [ ] Coverage and build status badges are updated
- [ ] Deployment status badge is updated
- [ ] Project completion badge is updated
- [ ] Weekly progress reports are generated
