# PropPulse Phase 4: Risk-Scoring Layer Testing Guide

This document provides instructions for testing the newly implemented Risk-Scoring layer in PropPulse.

## Overview

The Risk-Scoring layer adds automated risk assessment capabilities to PropPulse, allowing the platform to stress-test each deal and flag investments as red, amber, or green grade based on Monte Carlo simulations and developer risk scores.

## Prerequisites

- Access to PropPulse development environment
- API keys for STR Global and DXB Rentals (stored in Azure Key Vault)
- Sample property data in the database
- Zoho CRM access for testing alerts

## Testing Components

### 1. RiskDataIngestor

The RiskDataIngestor pulls daily market data from multiple sources:

```bash
# Run daily data ingestion manually
curl -X POST http://localhost:8000/api/admin/risk/ingest-daily-data

# Run historical backfill (use with caution - resource intensive)
curl -X POST http://localhost:8000/api/admin/risk/historical-backfill?days=30
```

Verify that market metrics are stored in the database:

```sql
SELECT * FROM market_metrics ORDER BY timestamp DESC LIMIT 10;
```

### 2. MonteCarloIRRAgent

The MonteCarloIRRAgent runs 5,000 simulations over 10 years for each property:

```bash
# Run simulation for a specific property
curl -X POST http://localhost:8000/api/risk/UNO-611/run-simulation

# Check simulation results
curl -X GET http://localhost:8000/api/risk/UNO-611
```

Expected output includes:
- Mean IRR
- 5th percentile IRR (VaR)
- Probability of negative IRR
- Risk grade (RED, AMBER, GREEN)

### 3. RiskScoreComposer

The RiskScoreComposer applies risk grading rules:
- GREEN = P(IRR<0) ≤ 10% & developer risk_score ≤ 2
- AMBER = otherwise if P(IRR<0) ≤ 25%
- RED = everything else

Verify risk grades in the database:

```sql
SELECT id, risk_grade, mean_irr, var_5, prob_negative FROM properties;
```

### 4. AlertAgent

The AlertAgent sends notifications when risk grades change:

1. Manually change a property's risk grade:
```sql
UPDATE properties SET risk_grade = 'AMBER' WHERE id = 'UNO-611' AND risk_grade = 'GREEN';
```

2. Trigger the alert agent:
```bash
curl -X POST http://localhost:8000/api/admin/risk/check-alerts
```

3. Verify:
   - Zoho CRM task is created
   - WhatsApp alert is sent to investors
   - Secondary market listing price is adjusted

### 5. Underwriter Dashboard

Access the underwriter dashboard at:
```
http://localhost:3000/risk
```

Test the following features:
- Tornado diagram for IRR distribution
- Heat map of risk grades by tower & floor
- Filtering by tower, floor, unit type, and risk grade
- CSV export of Monte Carlo simulation results

### 6. API Extensions

Test the risk API endpoints:

```bash
# Get risk data for a property
curl -X GET http://localhost:8000/api/risk/UNO-611

# Export risk data as CSV
curl -X GET http://localhost:8000/api/risk/UNO-611/export -o simulation_results.csv

# Get properties by risk grade
curl -X GET http://localhost:8000/api/risk/grade/green
```

### 7. Proposal PDF Integration

Generate a new proposal and verify that it includes:
- Risk grade badge next to property ID
- Risk metrics section with Mean IRR, VaR, etc.

```bash
# Generate proposal
curl -X POST http://localhost:8000/api/propose -d '{"property_id": "UNO-611", "language": "en"}'
```

## Celery Worker Configuration

The risk engine uses Celery for background processing:

```bash
# Start Celery worker for risk tasks
celery -A backend.celery_app worker -Q risk -c 2 -l info

# Start Celery beat for scheduled tasks
celery -A backend.celery_app beat -l info
```

Scheduled tasks:
- `risk_ingest_daily` at 02:00 GST
- `mc_sim_runner` at 03:00 GST
- `price_adjuster` at 04:30 GST

## Troubleshooting

If you encounter issues:

1. Check Celery logs for task failures
2. Verify Azure Key Vault access for API keys
3. Check database connectivity
4. Ensure Pinecone API is accessible for metadata updates

For detailed error logs:
```bash
tail -f logs/risk_engine.log
```

## Performance Considerations

- Monte Carlo simulations are resource-intensive; avoid running multiple simulations simultaneously
- CSV exports of large datasets (>10,000 rows) are automatically zipped
- Dashboard visualizations may be slow to render with large datasets
