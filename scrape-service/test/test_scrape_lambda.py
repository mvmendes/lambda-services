import pytest
from src.scrape_lambda import lambda_handler
from moto import mock_aws
import json

@pytest.fixture
def valid_event():
    return {
        'body': json.dumps({
            'url': 'https://example.com'
        })
    }

def test_lambda_handler_valid_url(valid_event):
    response = lambda_handler(valid_event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'markdown' in body
    assert 'images' in body
    assert 'title' in body
    assert 'html' in body
    assert 'final_url' in body

def test_lambda_handler_missing_url():
    event = {'body': '{}'}
    response = lambda_handler(event, None)
    assert response['statusCode'] == 400

@pytest.mark.parametrize("format_type,expected_content_type", [
    ('json', 'application/json'),
    ('html', 'text/html'),
    ('text', 'text/plain'),
    ('proxy', None)  # Headers vêm da resposta original
])
def test_lambda_handler_formats(format_type, expected_content_type):
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'format': format_type
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    if expected_content_type:
        assert response['headers']['Content-Type'] == expected_content_type 