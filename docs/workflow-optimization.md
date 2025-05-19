# Workflow Runtime Optimization

This document outlines strategies to optimize GitHub Actions workflow runtime for PropPulse, ensuring all jobs complete within the 15-minute constraint.

## Current Workflow Analysis

### CI Workflow
- Test job: Runs pytest with coverage and linting
- Build job: Builds Docker image for testing

### CD Workflow
- Build-and-push job: Builds and pushes Docker image to GitHub Container Registry
- Deploy job: Deploys to Azure Container Apps

### Progress Report Workflow
- Generate-report job: Generates weekly progress report and creates PR

### Project Badge Workflow
- Update-badge job: Updates project completion badge

## Optimization Strategies

### 1. Caching Improvements

#### Dependencies Caching
```yaml
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

#### Docker Layer Caching
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v2

- name: Cache Docker layers
  uses: actions/cache@v3
  with:
    path: /tmp/.buildx-cache
    key: ${{ runner.os }}-buildx-${{ github.sha }}
    restore-keys: |
      ${{ runner.os }}-buildx-
```

### 2. Parallel Job Execution

- Run tests and linting in parallel
- Split large test suites into multiple jobs

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      # Linting steps

  test-backend:
    runs-on: ubuntu-latest
    steps:
      # Backend test steps

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      # Frontend test steps
```

### 3. Conditional Job Execution

- Skip unnecessary jobs based on changed files
- Use GitHub's `paths` filter to trigger workflows only when relevant files change

```yaml
on:
  push:
    branches: [ main ]
    paths:
      - 'backend/**'
      - 'frontend/**'
      - 'Dockerfile'
```

### 4. Optimize Docker Builds

- Use multi-stage builds to reduce image size
- Leverage BuildKit's parallel processing

```dockerfile
# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
CMD ["node", "dist/main.js"]
```

### 5. Minimize GitHub API Calls

- Batch GitHub API requests in scripts
- Use GraphQL for more efficient data fetching
- Implement pagination for large result sets

### 6. Optimize Python Scripts

- Use async/await for I/O-bound operations
- Implement proper error handling to avoid retries
- Profile scripts to identify bottlenecks

```python
import asyncio
import aiohttp

async def fetch_data(session, url):
    async with session.get(url) as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_data(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
```

### 7. Workflow Consolidation

- Combine related workflows to reduce setup overhead
- Share outputs between jobs using artifacts or job outputs

### 8. Resource Optimization

- Use smaller runner images where possible
- Set appropriate timeout limits for each job
- Clean up workspace before and after jobs

```yaml
- name: Clean workspace
  run: |
    rm -rf node_modules
    rm -rf .pytest_cache
```

## Implementation Plan

1. Update CI workflow with improved caching and parallel jobs
2. Optimize Docker build process in CD workflow
3. Refactor Python scripts for better performance
4. Implement conditional execution based on changed files
5. Consolidate redundant workflows
6. Set appropriate timeout limits for all jobs

## Monitoring

- Track workflow execution times in GitHub Actions
- Set up alerts for workflows approaching the 15-minute limit
- Regularly review and optimize slow-running jobs
