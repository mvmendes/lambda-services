import json
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import html2text

def process_html(html_content, final_url):
    """Processa o HTML e retorna título, resumo HTML e imagens"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extração do título
    title = soup.title.string.strip() if soup.title and soup.title.string else "Sem Título"
    
    # Extração de parágrafos
    paragraphs = soup.find_all('p')
    resumo_html = ""
    for p in paragraphs:
        text = p.get_text().strip()
        if text:
            resumo_html += f"<p>{text}</p>\n"
        if len(resumo_html) > 200000:
            break
    if not resumo_html:
        resumo_html = "<p>Não foram encontrados textos significativos na página.</p>"

    # Extração de imagens
    images = []
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            full_src = urljoin(final_url, src)
            if full_src not in images:
                images.append(full_src)
        if len(images) >= 5:
            break
            
    return title, resumo_html, images

def format_response(format_type, title, html_content, markdown_text, images, final_url, response_headers=None):
    """Formata a resposta de acordo com o tipo solicitado"""
    
    if format_type == 'proxy':
        return {
            'statusCode': 200,
            'headers': response_headers,
            'body': html_content
        }
    
    if format_type == 'html':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html',
                'Access-Control-Allow-Origin': '*'
            },
            'body': f"""
                <html>
                <head><title>{title}</title></head>
                <body>
                    <h1>{title}</h1>
                    <p>Final URL: <a href="{final_url}">{final_url}</a></p>
                    {html_content}
                    <h2>Images:</h2>
                    <div>{''.join(f'<img src="{img}" style="max-width:300px;margin:10px;" />' for img in images)}</div>
                </body>
                </html>
            """
        }
    
    if format_type == 'text':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/plain',
                'Access-Control-Allow-Origin': '*'
            },
            'body': markdown_text
        }
    
    # Default: JSON
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            "title": title,
            "markdown": markdown_text,
            "html": html_content,
            "images": images,
            "final_url": final_url
        })
    }

def lambda_handler(event, context):
    try:
        # Parse do corpo da requisição
        body = json.loads(event.get('body', '{}'))
        original_url = body.get('url')
        format_type = body.get('format', 'html').lower()  # Formato padrão: html
        
        # Validação da URL
        if not original_url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': "Parâmetro 'url' não informado"})
            }
            
        # Adiciona protocolo se necessário
        if not original_url.startswith(('http://', 'https://')):
            original_url = f'https://{original_url}'

        # Requisição HTTP
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(original_url, timeout=10.0)
            final_url = str(response.url)
            html_content = response.text

        # Se a resposta for JSON (content-type application/json), processa de forma diferenciada
        ctype = response.headers.get("content-type", "").lower()
        if "application/json" in ctype:
            try:
                data = response.json()
                if format_type == 'json':
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps(data)
                    }
                else:
                    pretty_json = json.dumps(data, indent=2, ensure_ascii=False)
                    if format_type == 'html':
                        html_body = f"<pre>{pretty_json}</pre>"
                        return {
                            'statusCode': 200,
                            'headers': {
                                'Content-Type': 'text/html',
                                'Access-Control-Allow-Origin': '*'
                            },
                            'body': html_body
                        }
                    else:  # text
                        return {
                            'statusCode': 200,
                            'headers': {
                                'Content-Type': 'text/plain',
                                'Access-Control-Allow-Origin': '*'
                            },
                            'body': pretty_json
                        }
            except Exception as json_err:
                # Caso haja erro na conversão, prossegue com processamento normal
                pass

        # Se for proxy, retorna o conteúdo original com headers
        if format_type == 'proxy':
            return format_response('proxy', None, html_content, None, None, final_url, dict(response.headers))

        # Processamento do conteúdo
        title, resumo_html, images = process_html(html_content, final_url)

        # Conversão para Markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        markdown_text = converter.handle(resumo_html)
        markdown_full = f"# {title}\n\nFinal URL: [Link]({final_url})\n\n{markdown_text}"

        # Retorna resposta formatada
        return format_response(format_type, title, resumo_html, markdown_full, images, final_url)
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 