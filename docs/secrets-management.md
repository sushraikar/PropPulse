# Secrets Management and Security

This document outlines the secrets management and security practices for the PropPulse CI/CD and automation workflows.

## Required Secrets

The following secrets are required for the PropPulse CI/CD and automation workflows:

| Secret Name | Description | Used In |
|-------------|-------------|---------|
| `GITHUB_TOKEN` | Automatically provided by GitHub Actions | All workflows |
| `AZURE_CREDENTIALS` | Azure service principal credentials in JSON format | CD workflow |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | CD workflow |
| `GHCR_TOKEN` | GitHub Container Registry token | CD workflow |
| `GIST_SECRET` | GitHub token with gist write permissions | Badge workflows |
| `COVERAGE_GIST_ID` | Gist ID for coverage badge | CI workflow |
| `BUILD_STATUS_GIST_ID` | Gist ID for build status badge | CI workflow |
| `DEPLOY_STATUS_GIST_ID` | Gist ID for deployment status badge | CD workflow |
| `PROJECT_GIST_ID` | Gist ID for project completion badge | Project badge workflow |
| `PROJECT_NUMBER` | GitHub Project number | Project automation workflows |
| `REPO_ADMIN_TOKEN` | GitHub token with repo admin permissions | Setup project workflow |

## Secret Creation and Management

### Creating GitHub Secrets

1. Navigate to your repository on GitHub
2. Go to Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Enter the secret name and value
5. Click "Add secret"

### Creating Azure Service Principal

```bash
# Login to Azure
az login

# Create service principal with Contributor role
az ad sp create-for-rbac --name "PropPulseDeployment" \
                         --role Contributor \
                         --scopes /subscriptions/{subscription-id} \
                         --sdk-auth

# The output JSON should be stored as AZURE_CREDENTIALS secret
```

### Creating Gists for Badges

1. Create a new gist at https://gist.github.com/
2. Create the following files:
   - `proppulse-coverage.json`
   - `proppulse-build.json`
   - `proppulse-deploy-dev.json`
   - `proppulse-deploy-staging.json`
   - `proppulse-deploy-prod.json`
   - `proppulse-completion.json`
   - `proppulse-risk-engine.json`
3. Store the gist ID in the corresponding GitHub secret

## Security Best Practices

### Token Scopes and Permissions

- Use the principle of least privilege when creating tokens
- Limit token scopes to only what is needed:
  - `GITHUB_TOKEN`: Automatically scoped by GitHub Actions
  - `GHCR_TOKEN`: Needs `write:packages` scope
  - `GIST_SECRET`: Needs `gist` scope
  - `REPO_ADMIN_TOKEN`: Needs `repo` scope

### Secret Rotation

- Rotate secrets regularly (every 90 days recommended)
- Update GitHub secrets immediately after rotation
- Use Azure Key Vault for storing and rotating Azure credentials

### Preventing Secret Leakage

- Never log secrets or tokens in workflow outputs
- Use GitHub's built-in secret masking
- Avoid passing secrets as command-line arguments
- Use environment variables for passing secrets to scripts

```yaml
- name: Run script with secrets
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: ./script.sh
```

### Secure Script Practices

- Validate and sanitize all inputs
- Implement proper error handling
- Avoid using secrets directly in script outputs
- Use HTTPS for all API calls

## Monitoring and Auditing

- Enable audit logging in GitHub
- Monitor for unusual activity in workflow runs
- Review access to secrets regularly
- Implement alerts for failed authentication attempts

## Compliance

- Ensure all secrets management practices comply with:
  - ISO 27001
  - UAE NESA controls
  - GDPR (if applicable)

## Secret Rotation Schedule

| Secret | Rotation Frequency | Next Rotation Date |
|--------|-------------------|-------------------|
| `AZURE_CREDENTIALS` | 90 days | 2025-08-17 |
| `GHCR_TOKEN` | 180 days | 2025-11-15 |
| `GIST_SECRET` | 180 days | 2025-11-15 |
| `REPO_ADMIN_TOKEN` | 90 days | 2025-08-17 |

## Emergency Procedures

In case of suspected secret compromise:

1. Immediately rotate the affected secret
2. Update the secret in GitHub
3. Review workflow logs for unauthorized access
4. Check for unauthorized deployments or repository changes
5. Document the incident and response
