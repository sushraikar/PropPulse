# PropPulse Phase 5 Testing Instructions

This document provides instructions for testing the self-serve developer portal and related features implemented in Phase 5.

## Prerequisites

- Access to the PropPulse development environment
- Test developer account credentials
- Stripe test API keys
- Test files for upload (PDF, XLSX, CSV, IFC, GLB)

## 1. DevConsole Authentication

### Magic.Link Authentication
1. Navigate to `/dev` in the PropPulse application
2. Click "Sign In" and enter a test email address
3. Check the email for the Magic.Link authentication link
4. Click the link to authenticate and verify you're redirected to the developer dashboard

### Role-Based Access Control
1. Log in with a developer_admin account
   - Verify full access to all features
2. Log in with a staff account
   - Verify read access but limited write permissions
3. Log in with an auditor_readonly account
   - Verify read-only access to analytics and reports

## 2. Welcome Wizard

1. Complete the welcome wizard with the following information:
   - Legal Name: "Test Developer LLC"
   - VAT Registration Number: "123456789"
   - Trade License / Developer ID: "DLD-12345"
   - Primary Contact Email: "contact@testdev.com"
   - Primary Contact WhatsApp: "+971501234567"
   - Support Phone: "+97142345678"
   - IBAN: "AE123456789012345678901"
   - Escrow IBAN: "AE987654321098765432109"
2. Submit the form and verify the data is saved correctly
3. Try submitting with invalid data to verify validation works

## 3. DataUploadService

### File Upload
1. Navigate to the Data Upload page
2. Drag and drop a test PDF file (< 100MB)
3. Verify the file is uploaded and processed
4. Check for virus scanning notification

### Column Mapping
1. Upload a test XLSX file with property data
2. Verify the system automatically maps columns using GPT-4o
3. Adjust any incorrect mappings manually
4. Submit the mapping and verify data is ingested correctly

### Error Handling
1. Try uploading an invalid file (e.g., .exe file)
2. Verify appropriate error message is displayed
3. Try uploading a file > 200MB
4. Verify file size limit error is displayed

## 4. PricingPlan & Stripe

### Plan Selection
1. Navigate to the Pricing page
2. Review the available plans:
   - FREE (1 project, 10 active units)
   - PRO ($99/month, 5 projects, 500 active units)
   - UNLIMITED ($299/month, unlimited projects and units)
3. Select the PRO plan

### Stripe Checkout
1. Click "Subscribe" on the PRO plan
2. Verify redirect to Stripe Checkout
3. Use test card number: 4242 4242 4242 4242
4. Complete the checkout process
5. Verify redirect back to PropPulse with confirmation

### Webhook Testing
1. Verify the subscription is reflected in the developer account
2. Check that the `developer_plan` table is updated correctly
3. Test the 14-day trial functionality

## 5. Live Sync Webhooks

### Inventory Update
1. Use a tool like Postman to send a POST request to:
   `/webhook/dev/<developer_id>/inventory`
2. Include a JSON payload with property updates
3. Include the correct signature header
4. Verify the updates are applied to the database

### Pinecone Refresh
1. After a successful webhook update, verify that Pinecone embeddings are refreshed
2. Check the logs for confirmation of the refresh operation

## 6. AI-Collateral Generator

### Asset Generation
1. Navigate to the Marketing Assets page
2. Select a property to generate assets for
3. Click "Generate Assets"
4. Verify the system creates:
   - Hero image (1080 × 810)
   - 150-word catchy summary
   - USP bullets

### Regeneration
1. If not satisfied with the generated assets, click "Regenerate"
2. Verify you can regenerate up to 3 times
3. Verify the brand guidelines are followed:
   - Color: #1F4AFF
   - Font: "Inter"
   - Developer logo in top-left
   - Disclaimer text included

## 7. Analytics & Dashboard

### Dashboard View
1. Navigate to the Analytics page
2. Verify the following charts are displayed:
   - Views
   - Saves
   - Tokenized
   - Risk grade mix
   - Avg time on listing
   - Inquiry-to-lead conversion %
   - Tokens traded

### Report Export
1. Click "Export PDF Report"
2. Verify the PDF is generated with all selected KPIs
3. Schedule a weekly email report
4. Verify the email settings are saved correctly

## 8. GDPR Compliance

### Data Purge Request
1. Navigate to the Account Settings page
2. Click "Request Data Purge"
3. Confirm the request
4. Verify you receive a confirmation with the scheduled completion time (within 24 hours)

## 9. CRM Push

### Zoho Integration
1. Create a new property listing
2. Verify it's automatically pushed to Zoho CRM "Opportunities" pipeline
3. Check that it's assigned to the correct sales squad based on tower location
4. Update the property details and verify the changes are reflected in Zoho

## 10. End-to-End Validation

1. Create a new developer account
2. Complete the welcome wizard
3. Subscribe to a plan
4. Upload property data
5. Generate marketing assets
6. View analytics
7. Verify CRM integration
8. Test all features in combination to ensure they work together seamlessly

## Reporting Issues

If you encounter any issues during testing, please report them with the following information:
- Feature being tested
- Steps to reproduce
- Expected behavior
- Actual behavior
- Screenshots or error messages

## Test Environment

- Dev Portal URL: https://dev.proppulse.ai/dev
- API Endpoint: https://api.dev.proppulse.ai
- Stripe Dashboard: https://dashboard.stripe.com/test/dashboard
- Zoho CRM: https://crm.zoho.eu
