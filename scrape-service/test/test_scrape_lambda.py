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

def test_lambda_handler_missing_url():
    event = {'body': '{}'}
    response = lambda_handler(event, None)
    assert response['statusCode'] == 400 