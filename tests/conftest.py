"""Pytest fixtures for testing."""
import pytest
from unittest.mock import MagicMock, Mock
from fastapi.testclient import TestClient
from openai import OpenAI
from supabase import Client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock(spec=OpenAI)
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test AI response"))]
    )
    return client


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = MagicMock(spec=Client)
    
    # Store table mocks so they can be configured in tests
    table_mocks = {}
    
    def create_table_mock(table_name):
        """Create a new table mock for each table() call."""
        if table_name not in table_mocks:
            table_mock = MagicMock()
            
            # Create a chainable mock that can be configured
            def create_chainable():
                chain = MagicMock()
                result = Mock()
                result.data = []
                result.count = 0
                chain.execute = Mock(return_value=result)
                chain.select = Mock(return_value=chain)
                chain.insert = Mock(return_value=chain)
                chain.update = Mock(return_value=chain)
                chain.eq = Mock(return_value=chain)
                chain.gte = Mock(return_value=chain)
                chain.limit = Mock(return_value=chain)
                chain.order = Mock(return_value=chain)
                return chain
            
            chain = create_chainable()
            table_mock.select = Mock(return_value=chain)
            table_mock.insert = Mock(return_value=create_chainable())
            table_mock.update = Mock(return_value=create_chainable())
            table_mock.eq = Mock(return_value=chain)
            table_mock.gte = Mock(return_value=chain)
            table_mock.limit = Mock(return_value=chain)
            table_mock.order = Mock(return_value=chain)
            
            table_mocks[table_name] = table_mock
        
        return table_mocks[table_name]
    
    # Set up table to return configured mocks
    client.table = MagicMock(side_effect=create_table_mock)
    # Expose table_mocks for test configuration
    client._table_mocks = table_mocks
    
    return client


@pytest.fixture
def app_client(mock_supabase_client, mock_openai_client, monkeypatch):
    """Create FastAPI test client with mocked dependencies."""
    from app.main import app
    
    # Patch the OpenAI client (now lives in helpers module)
    monkeypatch.setattr("app.helpers.client", mock_openai_client)
    
    # Patch the Supabase client
    monkeypatch.setattr("app.supabase_config.supabase", mock_supabase_client)
    
    return TestClient(app)


@pytest.fixture
def sample_ticket_request():
    """Sample ticket request data."""
    return {
        "context": "test-context",
        "subject": "Test Subject",
        "message": "Test message",
    }


@pytest.fixture
def sample_message_request():
    """Sample message request data."""
    return {"message": "Test follow-up message"}
