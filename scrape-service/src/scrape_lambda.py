import json
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import html2text
import re
from jsonpath_ng import parse

def process_html(html_content, final_url, maxsize=2000):
    """Processa o HTML e retorna título, resumo HTML, imagens e links"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extração do título
    title = soup.title.string.strip() if soup.title and soup.title.string else "Sem Título"
    
    # Extração de parágrafos
    elementos = soup.find_all([
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
        'strong', 'span','a'
    ])
    paragraphs = []
    ultimo_texto = None
    for elemento in elementos:
        texto_atual = elemento.get_text(strip=True)
        if elemento.name == 'a':
            texto_atual = f"[{elemento.get_text(strip=True)}]({elemento.get('href')})"
        if texto_atual and texto_atual != ultimo_texto:
            paragraphs.append(elemento)
            ultimo_texto = texto_atual
    resumo_html = ""
    for p in paragraphs:
        text = p.get_text().strip()
        if text:
            resumo_html += f"<p>{text}</p>\n"
        if len(resumo_html) > maxsize:
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
            
    # Extração de links contidos nas tags <a>
    links = []
    for a in soup.find_all('a'):
        href = a.get('href')
        if href:
            full_link = urljoin(final_url, href)
            if full_link not in links:
                links.append(full_link)

    return title, resumo_html, images, links



def extract_metadata(html_content):
    """
    Extrai os metadados do schema.org e dados do Next.js a partir do HTML.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    schema_data = {}
    next_data = {}

    # Extração dos dados do schema.org (JSON-LD)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            # Use get_text() para obter o conteúdo mesmo se não for um nó de string simples
            content = script.get_text(strip=True)
            if content:
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type", "").lower() == "product":
                            schema_data = item
                        elif item.get("@type", "").lower() == "breadcrumblist":
                            schema_data["breadcrumb"] = item.get("itemListElement", [])
                elif isinstance(data, dict):
                    type_value = data.get("@type", "").lower()
                    if type_value == "product":
                        schema_data = data
                    elif type_value == "breadcrumblist":
                        schema_data["breadcrumb"] = data.get("itemListElement", [])
        except Exception:
            continue

    # Extração dos dados do Next.js a partir da tag <script id="__NEXT_DATA__" type="application/json">
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if tag and tag.string:
        try:
            next_data = json.loads(tag.string)
        except Exception:
            next_data = {}
    else:
        next_data = {}

    return {
        "schema": schema_data,
        "nextData": next_data
    }

def filter_next_data(next_data):
    """
    Filtra o nextData para retornar somente {"props": {"pageProps": ...}}
    """
    props = next_data.get("props", {})
    return {"props": {"pageProps": props.get("pageProps", {})}}

def apply_metadata_filters(next_data, filters):
    """
    Aplica filtros JSONPath ao next_data.
    `filters` deve ser um array de expressões JSONPath.
    Retorna um dicionário com cada query como chave e os dados extraídos como valor.
    """
    filtered = {}
    for query in filters:
        try:
            jsonpath_expr = parse(query)
            matches = [match.value for match in jsonpath_expr.find(next_data)]
            filtered[query] = matches
        except Exception as e:
            filtered[query] = f"Error: {str(e)}"
    return filtered

def lambda_handler(event, context):
    try:
        # Parse do corpo da requisição
        body = json.loads(event.get('body', '{}'))
        return_headers = body.get('output_headers', False)
        original_url = body.get('url')
        format_type = body.get('format', 'metadata').lower()  # Formato padrão: metadata
        method = body.get('method', 'GET').upper()  # Método padrão: GET
        
        # Validação da URL
        if not original_url:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': "Parâmetro 'url' não informado"})
            }
            
        # Adiciona protocolo se necessário
        if not original_url.startswith(('http://', 'https://')):
            original_url = f'https://{original_url}'

        # Processamento dos headers customizados
        custom_headers = {}
        if 'headers' in body:
            try:
                for header in body['headers']:
                    custom_headers.update(header)
            except Exception as header_err:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f"Formato inválido para headers: {str(header_err)}"})
                }

        # Requisição HTTP
        with httpx.Client(follow_redirects=True) as client:
            response = client.request(method, original_url, headers=custom_headers, timeout=10.0)
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

 

        # Processamento do conteúdo
        maxsize_param = int(body.get('maxsize', 300))  # Tamanho máximo do resumo (default: 300)
        title, resumo_html, images, links = process_html(html_content, final_url, maxsize_param)
        # Controle da extração de imagens a partir do parâmetro "images" na requisição (default: true)
        respond_images = body.get('images', True)
        if not respond_images:
            images = []

        # Conversão para Markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        markdown_text = converter.handle(resumo_html)
        markdown_full = f"# {title}\n\nFinal URL: [Link]({final_url})\n\n{markdown_text}"

        # Extrai os metadados (schema e nextData)
        metadata_data = extract_metadata(html_content)

        # Verifica se foram passados filtros para os metadados; se não houver, não retorna nextData
        filters = body.get('metadata_filters', None)
        if filters and isinstance(filters, list):
            next_data_value = apply_metadata_filters(metadata_data.get("nextData", {}), filters)
        else:
            next_data_value = None

        # Estrutura a resposta combinada
        data = {
            "title": title, 
            "images": images if (format_type == 'markdown' or format_type == 'html') and respond_images else None,
            "resumo_html": resumo_html if format_type == 'html' else None, 
            "final_url": final_url,
            "metadata": metadata_data.get("schema", {}) if format_type == 'metadata' else None,
            "nextData": next_data_value if format_type == 'metadata' else None,            
            "markdown": markdown_full if format_type == 'markdown' else None,
            "links": links if format_type == 'markdown' or format_type == 'html' else None,
            "headers":   dict(response.headers) if return_headers else None
        }


        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            # Retorna todos os dados, incluindo metadata e nextData
            'body': json.dumps(data)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 