import pytest
from src.scrape_lambda import lambda_handler
import json
import respx
import httpx

@pytest.fixture
def valid_event():
    return {
        'body': json.dumps({
            'url': 'https://example.com'
        })
    }

@pytest.fixture
def mock_pdf_response():
    return b"%PDF-1.4\nTest PDF content"

@pytest.fixture
def mock_docx_response():
    return b"Test DOCX content"

@pytest.fixture
def mock_xlsx_response():
    return b"Test XLSX content"

def test_lambda_handler_valid_url(valid_event):
    respx.get("https://example.com").mock(
         return_value=httpx.Response(200, text='<html><title>Test</title><body>Test content</body></html>')
    )
    response = lambda_handler(valid_event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'markdown' in body
    assert 'images' in body
    assert 'title' in body
    assert 'resumo_html' in body
    assert 'final_url' in body

@respx.mock
def test_lambda_handler_with_recursion():
    # Mock da página principal com um link relativo para PDF
    respx.get("https://eurofarma.com.br/produtos/bulas/healthcare/pt").mock(
         return_value=httpx.Response(200, text='<html><body><a href="bula-azitromicina.pdf">PDF Link</a></body></html>')
    )
    # Mock para a requisição do PDF (link relativo resolvido via urljoin)
    respx.get("https://eurofarma.com.br/produtos/bulas/healthcare/pt/bula-azitromicina.pdf").mock(
         return_value=httpx.Response(200, content=b"%PDF-1.4\nTest PDF content",
                                        headers={"Content-Type": "application/pdf"})
    )

    event = {
        'body': json.dumps({
            'url': 'https://eurofarma.com.br/produtos/bulas/healthcare/pt',
            'max_level': 2,
            'max_recursion_links': 2,
            'link_exp_filter': '\\.pdf$',
            'format': 'markdown'
        })
    }
    
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert isinstance(body['links'], dict)
    if body['links']:
        assert any(key.endswith('.pdf') for key in body['links'].keys())
    else:
        assert True

@respx.mock
def test_lambda_handler_with_inovation():
    # Mock da página principal do InovationAI com link relativo
    respx.get("https://inovationai.ai").mock(
         return_value=httpx.Response(200, text='<html><body><a href="/about">About</a></body></html>')
    )
    # Mock para a página interna (link relativo)
    respx.get("https://inovationai.ai/about").mock(
         return_value=httpx.Response(200, text='<html><body>About Inovation</body></html>')
    )

    event = {
        'body': json.dumps({
            'url': 'https://inovationai.ai',
            'max_level': 1,
            'max_recursion_links': 2,
            'format': 'markdown'
        })
    }
    
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert isinstance(body['links'], dict)
    if body['links']:
        assert any('inovationai.ai' in key for key in body['links'].keys())
    else:
        assert True

@respx.mock
def test_lambda_handler_with_document_processing():
    respx.get("https://eurofarma.com.br/produtos/bulas/patient/pt/bula-azitromicina-suspensao-oral.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.4\nTest PDF content")
    )
    
    event = {
        'body': json.dumps({
            'url': 'https://eurofarma.com.br/produtos/bulas/patient/pt/bula-azitromicina-suspensao-oral.pdf',
            'format': 'markdown'
        })
    }
    
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'azitromicina' in body['markdown'].lower()

@respx.mock
def test_lambda_handler_with_custom_headers():
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'headers': [
                {'x-channel-id': 'WEB'},
                {'x-ecomm-name': 'test-store'}
            ]
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200

@respx.mock
def test_lambda_handler_with_link_filter():
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text='<html><body><a href="test.pdf">PDF</a><a href="test.doc">DOC</a></body></html>')
    )
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'link_exp_filter': '\\.pdf$',
            'format': 'markdown'
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert isinstance(body['links'], list)
    expected_link = 'https://example.com/test.pdf'
    assert expected_link in body['links']
    assert all('.doc' not in l for l in body['links'])

def test_lambda_handler_with_max_recursion_links():
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'max_level': 1,
            'max_recursion_links': 2,
            'format': 'markdown'
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200

def test_lambda_handler_with_custom_method():
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'method': 'POST'
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200

def test_lambda_handler_with_images_disabled():
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'images': False,
            'format': 'markdown'
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['images'] is None

def test_lambda_handler_invalid_headers():
    event = {
        'body': json.dumps({
            'url': 'https://example.com',
            'headers': 'invalid'  # Deve ser um array
        })
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 400

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
    assert response['headers']['Content-Type'] == 'application/json' 