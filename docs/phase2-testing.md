# PropPulse Phase 2 Testing Instructions

This document provides instructions for testing the new Phase 2 features of PropPulse, including Location Intelligence, Live Price Watching, WhatsApp Quick-Quote, and UI enhancements.

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- Access to required API keys:
  - Google Places API key
  - Twilio account credentials
  - Zoho CRM credentials
  - Pinecone API key
  - OpenAI API key
  - Email account credentials

## Setup Instructions

1. Clone the repository and checkout the feature branch:
   ```bash
   git clone https://github.com/your-org/proppulse.git
   cd proppulse
   git checkout feat/location-intel
   ```

2. Create a `.env` file in the root directory with the following variables:
   ```
   # Database
   DB_PASSWORD=your_secure_password

   # API Keys
   OPENAI_API_KEY=your_openai_api_key
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_ENVIRONMENT=gcp-starter
   PINECONE_INDEX=proppulse
   GOOGLE_PLACES_API_KEY=your_google_places_api_key
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key

   # Zoho CRM
   ZOHO_CLIENT_ID=your_zoho_client_id
   ZOHO_CLIENT_SECRET=your_zoho_client_secret
   ZOHO_REDIRECT_URI=https://auth.proppulse.ai/zoho/callback

   # Email (for LivePriceWatcher)
   EMAIL_ADDRESS=your_outlook_email
   EMAIL_PASSWORD=your_email_password
   IMAP_SERVER=outlook.office365.com
   MAILBOX=PriceSheets

   # Twilio (for WhatsApp)
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number

   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ```

3. Start the services using Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Testing the New Features

### 1. Location Intelligence

1. Access the admin dashboard at `http://localhost:3000/admin`
2. Navigate to a property detail page
3. The map widget should display with POI category toggles on the left
4. Click on different POI categories to show/hide them on the map
5. Click on a POI marker to see details (distance, rating)
6. Check that the property's sunset view score is displayed correctly

API Testing:
```bash
# Get location data for a property
curl -X GET http://localhost:8000/api/properties/{property_id}/location

# Trigger location analysis for a property
curl -X POST http://localhost:8000/api/properties/{property_id}/analyze-location
```

### 2. Live Price Watcher

1. Send an email to your configured email address with:
   - Sender: any address from whiteoakwealthglobal.com
   - Subject: "Sales Offer" or "Price Sheet"
   - Attachment: A PDF or Excel file with filename starting with "SO_" or "RateSheet_"

2. The system should automatically:
   - Detect the email
   - Process the attachment
   - Update property prices in Zoho CRM
   - Regenerate proposals if price changes are ≥2%

API Testing:
```bash
# Start the price watcher
curl -X POST http://localhost:8000/api/price-watcher/start

# Manually check for price updates
curl -X POST http://localhost:8000/api/price-watcher/check-now

# Stop the price watcher
curl -X POST http://localhost:8000/api/price-watcher/stop
```

### 3. WhatsApp Quick-Quote

To test the WhatsApp integration:

1. Configure a Twilio WhatsApp Sandbox or Business Account
2. Set up a webhook pointing to `http://your-public-url/whatsapp/webhook`
3. Send the following commands to your WhatsApp number:
   - `QUOTE UNO-611` - Should return full quote with PDF link
   - `ROI UNO-611` - Should return ROI statistics
   - `LIST` - Should return top 5 available units by yield
   - `SCHEDULE UNO-611` - Should return next payment milestone
   - `HELP` - Should return list of available commands

For local testing, you can use ngrok to expose your local server:
```bash
ngrok http 8001
```

### 4. Building Unit View with Sunset Score

1. Access the admin dashboard at `http://localhost:3000/admin`
2. Navigate to the building view page
3. Units should be color-coded based on sunset view score:
   - Red (#FF6B6B): 0-33
   - Yellow (#FFC65C): 34-66
   - Green (#27AE60): 67-100
4. Click on different floors to see units on each floor
5. Toggle between "Sunset View" and "Availability" tabs

## Running Tests

To run the unit tests:

```bash
# Enter the backend container
docker exec -it proppulse-backend bash

# Run all tests
pytest

# Run specific test files
pytest tests/agents/test_location_insight_agent.py
pytest tests/agents/test_live_price_watcher.py
pytest tests/api/test_whatsapp.py

# Check test coverage
pytest --cov=. --cov-report=term-missing
```

## Troubleshooting

- **Email Connection Issues**: Verify your email credentials and ensure IMAP is enabled for your account
- **WhatsApp Webhook Not Receiving Messages**: Check Twilio configuration and ensure your webhook URL is publicly accessible
- **Google Places API Not Working**: Verify your API key and check quota limits
- **Missing POI Data**: Ensure the property has valid latitude/longitude coordinates

## Contact

For any issues or questions, please contact the PropPulse development team.
