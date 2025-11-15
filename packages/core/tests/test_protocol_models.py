"""
Tests for NLWeb protocol models.
"""

from nlweb_core.protocol import AskRequest


def test_valid_minimal_request():
    """Test that a minimal valid request works."""
    request = AskRequest(query="test query")
    
    assert request.query == "test query"
