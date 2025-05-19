# PropPulse Deployment Instructions

This document provides instructions for deploying and testing the PropPulse platform.

## Prerequisites

- Azure subscription with permissions to create resources
- GitHub account with permissions to create repositories and set up GitHub Actions
- Docker installed locally for development
- Terraform CLI installed for infrastructure management
- Node.js 18+ and Python 3.11+ for local development

## Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/proppulse.git
   cd proppulse
   ```

2. Copy the `.env.sample` file to `.env` and fill in the required values:
   ```bash
   cp .env.sample .env
   # Edit .env with your specific configuration
   ```

3. Required API keys and credentials:
   - Zoho CRM Pro account with OAuth2 credentials
   - Pinecone account with API key
   - OpenAI API key for embeddings
   - Supabase project URL and key
   - Azure subscription credentials

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The backend API will be available at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:3000

## Testing

Run the backend tests with coverage:

```bash
cd backend
pytest --cov=. tests/
```

Run the frontend tests:

```bash
cd frontend
npm test
```

## Deployment

### Using GitHub Actions (Recommended)

1. Push your code to GitHub
2. Set up the following secrets in your GitHub repository:
   - `AZURE_CREDENTIALS`: Azure service principal credentials
   - `AZURE_BACKEND_RG`: Resource group for Terraform state
   - `AZURE_BACKEND_SA`: Storage account for Terraform state
   - `AZURE_BACKEND_CONTAINER`: Container for Terraform state
   - `ZOHO_CLIENT_ID`: Zoho CRM client ID
   - `ZOHO_CLIENT_SECRET`: Zoho CRM client secret
   - `PINECONE_API_KEY`: Pinecone API key
   - `OPENAI_API_KEY`: OpenAI API key
   - `SUPABASE_URL`: Supabase URL
   - `SUPABASE_KEY`: Supabase key

3. Push to the `develop` branch to trigger deployment to the development environment

### Manual Deployment with Terraform

```bash
cd infra
terraform init
terraform plan -var="environment=dev" -var="location=uaenorth" -out=tfplan
terraform apply tfplan
```

## Accessing the Deployed Application

After successful deployment, you can access:

- Frontend VIP Dashboard: https://ca-frontend-dev.azurecontainerapps.io
- Backend API: https://ca-backend-dev.azurecontainerapps.io

## Zoho CRM Integration

1. Log in to your Zoho CRM account
2. Navigate to Setup > Developer Space > Connected Apps
3. Create a new Connected App
4. Upload the `backend/integrations/zoho/manifest.json` file
5. Complete the setup and authorization

## Monitoring and Logs

- Azure Portal: Monitor the deployed resources
- Log Analytics: Query logs using Kusto Query Language (KQL)
- Application Insights: Monitor application performance

## Security Features

- VNet integration with private endpoints
- Key Vault for secret management
- Azure Defender for Cloud enabled
- All data encrypted at rest
- ISO 27001 & UAE NESA controls satisfied

## Support

For any issues or questions, please contact the PropPulse team.
