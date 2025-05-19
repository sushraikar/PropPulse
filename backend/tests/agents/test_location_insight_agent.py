"""
Tests for the LocationInsightAgent
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import json

from agents.location_insight_agent.location_insight_agent import LocationInsightAgent
from integrations.google.google_places import GooglePlacesAPI
from integrations.osm.osm_api import OpenStreetMapAPI
from integrations.zoho.zoho_crm import ZohoCRM

# Sample property data
SAMPLE_PROPERTY = {
    'id': 'test_property_id',
    'Unit_No': 'UNO-611',
    'Project_Name': 'Uno Luxe',
    'Tower_Phase': 'Tower A',
    'floor': '6',
    'latitude': 25.7356,
    'longitude': 55.8320,
    'view_orientation': 'West'
}

# Sample POI data
SAMPLE_POIS = {
    'casino': [
        {
            'name': 'Wynn Resort',
            'latitude': 25.7406,
            'longitude': 55.8350,
            'distance': 0.5,
            'rating': 4.8
        }
    ],
    'hotel': [
        {
            'name': 'Luxury Resort',
            'latitude': 25.7356,
            'longitude': 55.8400,
            'distance': 0.8,
            'rating': 4.5
        }
    ],
    'beach': [
        {
            'name': 'Al Marjan Beach',
            'latitude': 25.7300,
            'longitude': 55.8300,
            'distance': 0.6,
            'rating': 4.7
        }
    ]
}

@pytest.fixture
def location_insight_agent():
    """Create a LocationInsightAgent instance with mocked dependencies"""
    with patch('agents.location_insight_agent.location_insight_agent.GooglePlacesAPI') as mock_google:
        with patch('agents.location_insight_agent.location_insight_agent.OpenStreetMapAPI') as mock_osm:
            with patch('agents.location_insight_agent.location_insight_agent.ZohoCRM') as mock_zoho:
                # Configure mocks
                mock_zoho_instance = MagicMock()
                mock_zoho_instance.get_property.return_value = SAMPLE_PROPERTY
                mock_zoho.return_value = mock_zoho_instance
                
                mock_google_instance = MagicMock()
                mock_google_instance.search_nearby.return_value = [
                    {'name': 'Test POI', 'geometry': {'location': {'lat': 25.74, 'lng': 55.83}}}
                ]
                mock_google.return_value = mock_google_instance
                
                mock_osm_instance = MagicMock()
                mock_osm.return_value = mock_osm_instance
                
                # Create agent
                agent = LocationInsightAgent({
                    'google_places_config': {},
                    'osm_config': {},
                    'zoho_config': {}
                })
                
                yield agent

@pytest.mark.asyncio
async def test_process_with_property_id(location_insight_agent):
    """Test processing a property by ID"""
    # Mock the internal methods
    location_insight_agent._fetch_property_data = MagicMock(return_value=SAMPLE_PROPERTY)
    location_insight_agent._fetch_poi_data = MagicMock(return_value=SAMPLE_POIS)
    location_insight_agent._calculate_sunset_view_score = MagicMock(return_value=85)
    location_insight_agent._calculate_wynn_casino_distance = MagicMock(return_value=0.5)
    location_insight_agent._generate_location_summary = MagicMock(return_value="Sample summary")
    location_insight_agent._translate_summary = MagicMock(return_value={
        'ar': 'Arabic summary',
        'fr': 'French summary',
        'hi': 'Hindi summary'
    })
    location_insight_agent._update_property_in_zoho = MagicMock(return_value=True)
    
    # Call the process method
    result = await location_insight_agent.process({
        'property_id': 'test_property_id'
    })
    
    # Verify the result
    assert result['status'] == 'success'
    assert 'property_data' in result
    assert 'poi_data' in result
    assert 'sunset_view_score' in result
    assert 'wynn_casino_distance' in result
    assert 'summary' in result
    assert 'translations' in result
    
    # Verify method calls
    location_insight_agent._fetch_property_data.assert_called_once_with('test_property_id')
    location_insight_agent._fetch_poi_data.assert_called_once()
    location_insight_agent._calculate_sunset_view_score.assert_called_once()
    location_insight_agent._calculate_wynn_casino_distance.assert_called_once()
    location_insight_agent._generate_location_summary.assert_called_once()
    location_insight_agent._translate_summary.assert_called_once()
    location_insight_agent._update_property_in_zoho.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_property_data(location_insight_agent):
    """Test fetching property data from Zoho CRM"""
    # Call the method
    property_data = await location_insight_agent._fetch_property_data('test_property_id')
    
    # Verify the result
    assert property_data == SAMPLE_PROPERTY
    
    # Verify Zoho CRM call
    location_insight_agent.zoho_crm.get_property.assert_called_once_with('test_property_id')

@pytest.mark.asyncio
async def test_calculate_sunset_view_score(location_insight_agent):
    """Test calculating sunset view score"""
    # Test west-facing unit on high floor (optimal)
    property_data = {
        'view_orientation': 'West',
        'floor': '12'
    }
    score = location_insight_agent._calculate_sunset_view_score(property_data)
    assert score >= 90  # Should be high score
    
    # Test southwest-facing unit on middle floor
    property_data = {
        'view_orientation': 'Southwest',
        'floor': '6'
    }
    score = location_insight_agent._calculate_sunset_view_score(property_data)
    assert 60 <= score < 90  # Should be medium-high score
    
    # Test east-facing unit (opposite of sunset)
    property_data = {
        'view_orientation': 'East',
        'floor': '10'
    }
    score = location_insight_agent._calculate_sunset_view_score(property_data)
    assert score < 50  # Should be low score despite high floor

@pytest.mark.asyncio
async def test_calculate_wynn_casino_distance(location_insight_agent):
    """Test calculating distance to Wynn Casino site"""
    property_data = {
        'latitude': 25.7356,
        'longitude': 55.8320
    }
    
    # Call the method
    distance = location_insight_agent._calculate_wynn_casino_distance(property_data)
    
    # Verify the result is a float and reasonable
    assert isinstance(distance, float)
    assert 0 < distance < 10  # Should be within 10km

@pytest.mark.asyncio
async def test_generate_location_summary(location_insight_agent):
    """Test generating location summary"""
    property_data = SAMPLE_PROPERTY
    poi_data = SAMPLE_POIS
    sunset_view_score = 85
    wynn_casino_distance = 0.5
    
    # Mock OpenAI call
    with patch('agents.location_insight_agent.location_insight_agent.openai') as mock_openai:
        mock_openai.ChatCompletion.create.return_value = {
            'choices': [{'message': {'content': 'Sample summary'}}]
        }
        
        # Call the method
        summary = location_insight_agent._generate_location_summary(
            property_data, poi_data, sunset_view_score, wynn_casino_distance
        )
        
        # Verify the result
        assert isinstance(summary, str)
        assert len(summary) > 0

@pytest.mark.asyncio
async def test_translate_summary(location_insight_agent):
    """Test translating summary to multiple languages"""
    summary = "This is a test summary for translation."
    
    # Mock OpenAI call
    with patch('agents.location_insight_agent.location_insight_agent.openai') as mock_openai:
        mock_openai.ChatCompletion.create.return_value = {
            'choices': [{'message': {'content': 'Translated text'}}]
        }
        
        # Call the method
        translations = await location_insight_agent._translate_summary(summary)
        
        # Verify the result
        assert isinstance(translations, dict)
        assert 'ar' in translations
        assert 'fr' in translations
        assert 'hi' in translations
        assert all(isinstance(v, str) for v in translations.values())

@pytest.mark.asyncio
async def test_update_property_in_zoho(location_insight_agent):
    """Test updating property in Zoho CRM"""
    property_id = 'test_property_id'
    property_data = SAMPLE_PROPERTY
    poi_data = SAMPLE_POIS
    sunset_view_score = 85
    wynn_casino_distance = 0.5
    summary = "Sample summary"
    translations = {
        'ar': 'Arabic summary',
        'fr': 'French summary',
        'hi': 'Hindi summary'
    }
    
    # Call the method
    result = await location_insight_agent._update_property_in_zoho(
        property_id, property_data, poi_data, sunset_view_score, 
        wynn_casino_distance, summary, translations
    )
    
    # Verify the result
    assert result is True
    
    # Verify Zoho CRM call
    location_insight_agent.zoho_crm.update_property.assert_called_once()
    
    # Verify the update data
    call_args = location_insight_agent.zoho_crm.update_property.call_args[0]
    assert call_args[0] == property_id
    update_data = call_args[1]
    assert 'sunset_view_score' in update_data
    assert 'wynn_casino_distance' in update_data
    assert 'poi_json' in update_data
    assert isinstance(json.loads(update_data['poi_json']), dict)
