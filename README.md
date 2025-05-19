# PropPulse

![Build Status](https://github.com/actions/workflows/ci.yml/badge.svg)
![Test Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/gist_user/gist_id/raw/proppulse-coverage.json)
![Deploy Status](https://github.com/actions/workflows/cd.yml/badge.svg)
![Risk Engine Green Rate](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/gist_user/gist_id/raw/proppulse-risk-engine.json)
![Tasks Done](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/gist_user/gist_id/raw/proppulse-completion.json)

PropPulse is an end-to-end platform that generates personalized real estate investment proposals based on property brochures and developer price sheets. The platform uses an Agentic RAG pipeline to analyze documents and generate investment proposals with detailed ROI calculations.

## Features

- **Data Ingestion**: Processes real estate brochures (PDF, XLS, images) and developer price sheets
- **Agentic RAG Pipeline**: Returns personalized investment proposals (max 2 pages) with IRR/Yield calculations
- **API Access**: Exposes a REST API for integration with other systems
- **Zoho CRM Integration**: Provides a Connected-App widget for Zoho CRM
- **Multilingual Support**: Generates proposals in Arabic, French, Hindi, and English
- **Client Dashboard**: Delivers a React (Next.js) VIP dashboard for each client

## Architecture

The project follows a monorepo structure with the following components:

```
PropPulse/
├── backend/           # FastAPI backend services
│   ├── agents/        # Agentic components
│   ├── api/           # REST API endpoints
│   ├── core/          # Core business logic
│   ├── db/            # Database models and migrations
│   ├── integrations/  # Third-party integrations (Zoho, BitOasis)
│   └── tests/         # Unit and integration tests
├── frontend/          # Next.js React frontend
│   ├── components/    # Reusable UI components
│   ├── pages/         # Next.js pages
│   ├── public/        # Static assets
│   ├── styles/        # CSS/SCSS styles
│   └── tests/         # Frontend tests
├── infra/             # Infrastructure as Code
│   ├── terraform/     # Terraform configurations for Azure
│   ├── docker/        # Docker configurations
│   └── ci/            # CI/CD pipeline configurations
└── docs/              # Documentation
```

## Technical Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React, Next.js
- **Database**: PostgreSQL (Azure Database for PostgreSQL)
- **Vector Store**: Pinecone
- **Embeddings**: OpenAI text-embedding-3-small
- **Deployment**: Docker, Azure Container Apps
- **Infrastructure**: Terraform
- **CI/CD**: GitHub Actions
- **CRM Integration**: Zoho CRM Pro via OAuth2
- **Payment Integration**: BitOasis OTC (crypto→AED) API

## Agentic Components

1. **DataIngestor**: Scrapes, chunks (1k tokens), and stores metadata
2. **QueryPlanner**: Decomposes user queries and calls RetrievalAgent
3. **RetrievalAgent**: Performs k=8 similarity search with metadata filtering
4. **ROIcalcAgent**: Calculates ADR, SC, IRR, and returns JSON
5. **ProposalWriter**: Assembles Markdown and converts to PDF via WeasyPrint
6. **Translator**: Translates content to Arabic, French, Hindi via GPT-4o
7. **DashboardComposer**: Pushes JSON & PDF links to Supabase

## Investment Metrics

- **ADR (Average Daily Rate)**: Developer's forecast or market average × view premium factor
- **Occupancy %**: Expected occupancy rate
- **Gross Rental Income**: Calculated based on ADR and occupancy
- **Service Charge (SC)**: Per ft²
- **Net Yield %**: Net Income / Purchase Price
- **IRR**: 10-year, pre-tax calculation
- **Projected Capital Appreciation**: Compound Annual Growth Rate (CAGR)

## Zoho CRM Integration

- **Custom Modules**: "Properties" and "Proposals"
- **OAuth2 Flow**: Server-side with long-lived refresh token
- **Tenant**: Zoho EU (accounts.zoho.eu)
- **Redirect URI**: https://auth.proppulse.ai/zoho/callback

## Multilingual Support

- **Arabic**: Modern Standard (MSA)
- **French**: Parisian
- **Hindi**: Standard (Devanagari)
- **English**: Default

## Deployment

- **Runtime**: Docker
- **Cloud Provider**: Azure (Dubai data center)
- **Services**:
  - Azure Container Apps
  - Azure Database for PostgreSQL – Flexible Server
  - Azure Key Vault
  - Azure Storage Blob
  - Azure Cognitive Services (optional)
- **Security**:
  - VNet with private endpoints
  - Data encryption at rest
  - Log Analytics + Defender for Cloud
  - ISO 27001 & UAE NESA compliance

## Project Roadmap

View our [GitHub Project](https://github.com/orgs/yourusername/projects/1) for the latest development roadmap and progress.

## Getting Started

See the [Development Guide](./docs/development.md) for instructions on setting up the development environment and running the application locally.

## License

Proprietary - All rights reserved.
