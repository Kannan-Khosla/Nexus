"""Unit tests for helper functions."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from app.helpers import sanitize_output, is_rate_limited, generate_ai_reply


class TestSanitizeOutput:
    """Tests for sanitize_output function."""

    def test_sanitize_profanity(self):
        """Test profanity detection and redaction."""
        text = "This is a fucking test"
        redacted, flags = sanitize_output(text)
        assert flags["profanity"] is True
        assert "***" in redacted
        assert "fucking" not in redacted

    def test_sanitize_email(self):
        """Test email detection and redaction."""
        text = "Contact me at test@example.com"
        redacted, flags = sanitize_output(text)
        assert flags["email"] is True
        assert "test@example.com" not in redacted
        assert "***@***.***" in redacted

    def test_sanitize_phone(self):
        """Test phone number detection and redaction."""
        text = "Call me at 555-123-4567"
        redacted, flags = sanitize_output(text)
        assert flags["phone"] is True
        assert "555-123-4567" not in redacted
        assert "***-***-****" in redacted

    def test_sanitize_credit_card(self):
        """Test credit card detection and redaction."""
        # Use a format that the regex will match (13-19 digits with optional separators)
        text = "My card is 4532123456789012"
        redacted, flags = sanitize_output(text)
        assert flags["cc"] is True
        assert "4532" not in redacted or "****" in redacted

    def test_sanitize_multiple(self):
        """Test multiple PII types in one text."""
        text = "Email me at test@example.com or call 555-123-4567. This is fucking great!"
        redacted, flags = sanitize_output(text)
        assert flags["email"] is True
        assert flags["phone"] is True
        assert flags["profanity"] is True

    def test_sanitize_clean_text(self):
        """Test clean text with no PII."""
        text = "This is a clean message with no sensitive information."
        redacted, flags = sanitize_output(text)
        assert flags["profanity"] is False
        assert flags["email"] is False
        assert flags["phone"] is False
        assert flags["cc"] is False
        assert redacted == text

    def test_sanitize_empty_string(self):
        """Test empty string input."""
        redacted, flags = sanitize_output("")
        assert redacted == ""
        assert all(not v for v in flags.values())

    def test_sanitize_none(self):
        """Test None input."""
        redacted, flags = sanitize_output(None)
        assert redacted == ""


class TestIsRateLimited:
    """Tests for is_rate_limited function."""

    @patch("app.helpers.supabase")
    def test_not_rate_limited(self, mock_supabase):
        """Test when ticket is not rate limited."""
        mock_response = Mock()
        mock_response.count = 1
        mock_chain = MagicMock()
        mock_chain.execute.return_value = mock_response
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value = mock_chain
        
        limited, meta = is_rate_limited("test-ticket-id")
        assert limited is False
        assert meta["ai_replies_in_window"] == 1

    @patch("app.helpers.supabase")
    def test_rate_limited(self, mock_supabase):
        """Test when ticket is rate limited."""
        mock_response = Mock()
        mock_response.count = 5
        mock_chain = MagicMock()
        mock_chain.execute.return_value = mock_response
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value = mock_chain
        
        limited, meta = is_rate_limited("test-ticket-id")
        assert limited is True
        assert meta["ai_replies_in_window"] == 5

    @patch("app.helpers.supabase")
    def test_rate_limit_error_handling(self, mock_supabase):
        """Test error handling in rate limit check."""
        mock_supabase.table.side_effect = Exception("Database error")
        limited, meta = is_rate_limited("test-ticket-id")
        assert limited is False
        assert meta == {}


class TestGenerateAIReply:
    """Tests for generate_ai_reply function."""

    @patch("app.helpers.client")
    def test_successful_reply(self, mock_client):
        """Test successful AI reply generation."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_ai_reply("Test prompt")
        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once()

    @patch("app.helpers.client")
    @patch("time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_client):
        """Test retry logic on API failure."""
        from config import settings
        
        # First call fails, second succeeds
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Retry success"))]),
        ]
        
        result = generate_ai_reply("Test prompt")
        assert result == "Retry success"
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("app.helpers.client")
    @patch("time.sleep")
    def test_all_retries_fail(self, mock_sleep, mock_client):
        """Test when all retry attempts fail."""
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            generate_ai_reply("Test prompt")
        
        # Should retry based on max_retries setting (default 3)
        # Total attempts = max_retries + 1 = 4
        assert mock_client.chat.completions.create.call_count >= 3

