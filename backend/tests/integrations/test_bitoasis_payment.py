"""
Tests for the BitOasis payment integration
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio
import hashlib
import time

from integrations.bitoasis.bitoasis_payment import BitOasisPayment

class TestBitOasisPayment:
    """Test suite for BitOasis payment integration"""
    
    @pytest.fixture
    def bitoasis_payment(self, mock_env_vars):
        """Create a BitOasisPayment instance for testing"""
        config = {
            'api_key': 'test-bitoasis-key',
            'api_secret': 'test-bitoasis-secret'
        }
        return BitOasisPayment(config)
    
    def test_initialization(self, bitoasis_payment):
        """Test initialization of BitOasis payment integration"""
        assert bitoasis_payment.api_key == 'test-bitoasis-key'
        assert bitoasis_payment.api_secret == 'test-bitoasis-secret'
        assert bitoasis_payment.api_url == 'https://api.bitoasis.net/v1'
        assert 'BTC' in bitoasis_payment.supported_cryptos
        assert 'ETH' in bitoasis_payment.supported_cryptos
        assert 'USDT' in bitoasis_payment.supported_cryptos
        assert 'USDC' in bitoasis_payment.supported_cryptos
    
    def test_generate_signature(self, bitoasis_payment):
        """Test generating HMAC signature for API request"""
        # Test parameters
        endpoint = '/quote'
        params = {
            'amount': 1000,
            'crypto': 'USDT'
        }
        
        # Generate signature
        signature = bitoasis_payment._generate_signature(endpoint, params)
        
        # Verify signature format
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA-256 hex digest length
    
    @pytest.mark.asyncio
    async def test_get_exchange_rate_valid(self, bitoasis_payment):
        """Test getting exchange rate for valid cryptocurrency"""
        # Get exchange rate for USDT
        rate_info = await bitoasis_payment.get_exchange_rate('USDT')
        
        # Verify rate info
        assert rate_info['crypto'] == 'USDT'
        assert rate_info['fiat'] == 'AED'
        assert rate_info['rate'] == 3.67
        assert 'timestamp' in rate_info
    
    @pytest.mark.asyncio
    async def test_get_exchange_rate_invalid(self, bitoasis_payment):
        """Test getting exchange rate for invalid cryptocurrency"""
        # Attempt to get exchange rate for unsupported crypto
        with pytest.raises(ValueError) as excinfo:
            await bitoasis_payment.get_exchange_rate('INVALID')
        
        # Verify error
        assert 'Unsupported cryptocurrency' in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_create_payment_quote(self, bitoasis_payment):
        """Test creating a payment quote"""
        # Create payment quote
        quote = await bitoasis_payment.create_payment_quote(
            amount_aed=10000,
            crypto_currency='USDT',
            client_reference='TEST-REF-001'
        )
        
        # Verify quote
        assert 'quote_id' in quote
        assert quote['client_reference'] == 'TEST-REF-001'
        assert quote['crypto_currency'] == 'USDT'
        assert quote['fiat_currency'] == 'AED'
        assert quote['fiat_amount'] == 10000
        assert quote['crypto_amount'] == 10000 / 3.67  # Based on mock exchange rate
        assert quote['exchange_rate'] == 3.67
        assert 'expiry' in quote
        assert quote['status'] == 'PENDING'
        assert 'payment_address' in quote
        assert 'created_at' in quote
    
    @pytest.mark.asyncio
    async def test_create_payment_quote_invalid(self, bitoasis_payment):
        """Test creating a payment quote with invalid cryptocurrency"""
        # Attempt to create payment quote with unsupported crypto
        with pytest.raises(ValueError) as excinfo:
            await bitoasis_payment.create_payment_quote(
                amount_aed=10000,
                crypto_currency='INVALID'
            )
        
        # Verify error
        assert 'Unsupported cryptocurrency' in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_check_payment_status(self, bitoasis_payment):
        """Test checking payment status"""
        # Check payment status
        status = await bitoasis_payment.check_payment_status('QUOTE_12345_USDT')
        
        # Verify status
        assert status['quote_id'] == 'QUOTE_12345_USDT'
        assert status['status'] == 'PENDING'
        assert status['crypto_currency'] == 'USDT'
        assert status['confirmations'] == 0
        assert status['required_confirmations'] == 6
        assert 'updated_at' in status
    
    @pytest.mark.asyncio
    async def test_simulate_payment_completion(self, bitoasis_payment):
        """Test simulating payment completion"""
        # Simulate payment completion
        result = await bitoasis_payment.simulate_payment_completion('QUOTE_12345_USDT')
        
        # Verify result
        assert result['quote_id'] == 'QUOTE_12345_USDT'
        assert result['status'] == 'COMPLETED'
        assert result['crypto_currency'] == 'USDT'
        assert result['confirmations'] == 6
        assert result['required_confirmations'] == 6
        assert 'transaction_id' in result
        assert 'completed_at' in result
