import json
import httpx
import time  # Importado para implementar o rate limit
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import html2text
import re
from jsonpath_ng import parse
import io
import PyPDF2
import docx2txt
from openpyxl import load_workbook
import csv
from io import StringIO

def process_html(html_content, final_url, maxsize=2000, level=0, max_level=0, processed_urls=None,
                 max_recursion_links=None, link_exp_filter=None, current_recursion_count=None, format_type='html'):
    """
    Processa o HTML de forma recursiva até max_level
    processed_urls: conjunto de URLs já processadas para evitar loops
    max_recursion_links: número máximo de links para processar recursivamente
    link_exp_filter: expressão regular para filtrar links
    current_recursion_count: contador de links processados no nível atual
    """
    if processed_urls is None:
        processed_urls = set()
    if current_recursion_count is None:
        current_recursion_count = {'count': 0}

    if final_url in processed_urls:
        return None, None, None, None

    processed_urls.add(final_url)

    soup = BeautifulSoup(html_content, 'html.parser')

    # Extração do título
    title = soup.title.string.strip() if soup.title and soup.title.string else "Sem Título"

    # Extração de parágrafos
    elementos = soup.find_all([
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'span', 'a'
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
    links = {} if max_level > 0 else []
    for a in soup.find_all('a'):
        href = a.get('href')
        if href:
            full_link = urljoin(final_url, href)
            # Se não houver filtro ou o link passar pelo filtro
            if not link_exp_filter or re.search(link_exp_filter, full_link):
                if max_level > 0:
                    if level < max_level and full_link not in processed_urls:
                        if max_recursion_links is None or current_recursion_count['count'] < max_recursion_links:
                            current_recursion_count['count'] += 1
                            try:
                                # Aguarda conforme o rate limit antes de executar a requisição
                                time.sleep(RATE_LIMIT_SECONDS)
                                with httpx.Client(follow_redirects=True) as client:
                                    response = client.get(full_link, timeout=10.0)
                                    ctype = response.headers.get("content-type", "").lower()

                                    # Processa documentos especiais
                                    if any(doc_type in ctype for doc_type in ["pdf", "word", "excel", "spreadsheet"]):
                                        content = process_document(response.content, ctype, format_type)
                                        if content:
                                            links[full_link] = {"content": content, "type": ctype}
                                    # Processa HTML recursivamente
                                    elif "html" in ctype:
                                        sub_title, sub_html, sub_images, sub_links = process_html(
                                            response.text, full_link, maxsize,
                                            level + 1, max_level, processed_urls,
                                            max_recursion_links, link_exp_filter, current_recursion_count, format_type
                                        )
                                        if sub_title:  # se processamento foi bem sucedido
                                            links[full_link] = {
                                                "title": sub_title,
                                                "content": sub_html,
                                                "images": sub_images,
                                                "links": sub_links
                                            }
                            except Exception as e:
                                links[full_link] = {"error": str(e)}
                        else:
                            links[full_link] = {"status": "max_recursion_links_reached"}
                    else:
                        links[full_link] = {"status": "max_level_reached"}
                elif max_level == 0:
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

def get_cors_headers():
    """Retorna os headers padrão para CORS"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST'
    }

def process_document(content, content_type, format_type='html'):
    """Processa documentos PDF, DOCX e XLSX retornando texto/html"""
    try:
        if "application/pdf" in content_type:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = "\n\n".join(page.extract_text() for page in pdf_reader.pages)
            return f"<pre>{text}</pre>" if "html" in format_type else text

        elif "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type:
            docx_file = io.BytesIO(content)
            text = docx2txt.process(docx_file)
            return f"<pre>{text}</pre>" if "html" in format_type else text

        elif "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type:
            xlsx_file = io.BytesIO(content)
            wb = load_workbook(xlsx_file, read_only=True)
            output = []
            for sheet in wb:
                rows = sheet.values
                header = next(rows)
                for row in rows:
                    output.append(dict(zip(header, row)))
            if "html" in format_type:
                html = ['<table border="1"><tr>']
                if output:
                    # Headers
                    html.extend(f'<th>{k}</th>' for k in output[0].keys())
                    html.append('</tr>')
                    # Rows
                    for row in output:
                        html.append('<tr>')
                        html.extend(f'<td>{v}</td>' for v in row.values())
                        html.append('</tr>')
                html.append('</table>')
                return ''.join(html)
            # Markdown table
            if not output:
                return "Empty spreadsheet"
            md = []
            headers = list(output[0].keys())
            md.append('| ' + ' | '.join(headers) + ' |')
            md.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
            for row in output:
                md.append('| ' + ' | '.join(str(row[h]) for h in headers) + ' |')
            return '\n'.join(md)

    except Exception as e:
        return f"Error processing document: {str(e)}"

    return None

def lambda_handler(event, context):
    try:
        # Se for uma requisição OPTIONS (preflight), retorna os headers CORS
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': ''
            }

        # Parse do corpo da requisição
        body = json.loads(event.get('body', '{}'))
        # Se 'rate_limit' for informado nos parâmetros, atualiza o tempo de espera (em segundos)
        if body.get("rate_limit") is not None:
            try:
                rate = float(body.get("rate_limit"))
                global RATE_LIMIT_SECONDS
                RATE_LIMIT_SECONDS = rate
            except Exception as e:
                pass
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
                        'headers': {**get_cors_headers(), 'Content-Type': 'application/json'},
                        'body': json.dumps(data)
                    }
                else:
                    pretty_json = json.dumps(data, indent=2, ensure_ascii=False)
                    if format_type == 'html':
                        html_body = f"<pre>{pretty_json}</pre>"
                        return {
                            'statusCode': 200,
                            'headers': {**get_cors_headers(), 'Content-Type': 'text/html'},
                            'body': html_body
                        }
                    else:  # text
                        return {
                            'statusCode': 200,
                            'headers': {**get_cors_headers(), 'Content-Type': 'text/plain'},
                            'body': pretty_json
                        }
            except Exception as json_err:
                # Caso haja erro na conversão, prossegue com processamento normal
                pass

        # Processamento do conteúdo
        maxsize_param = int(body.get('maxsize', 300))
        max_level = int(body.get('max_level', 0))  # Níveis de recursão (default: 0)
        max_recursion_links = body.get('max_recursion_links')  # Limite de links recursivos (default: None = sem limite)
        link_exp_filter = body.get('link_exp_filter')  # Regex para filtrar links (default: None = sem filtro)

        # Converte max_recursion_links para int se for string
        if isinstance(max_recursion_links, str):
            max_recursion_links = int(max_recursion_links)

        title, resumo_html, images, links = process_html(
            html_content, final_url, maxsize_param,
            level=0, max_level=max_level,
            max_recursion_links=max_recursion_links,
            link_exp_filter=link_exp_filter,
            format_type=format_type
        )
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
            "headers": dict(response.headers) if return_headers else None
        }

        return {
            'statusCode': 200,
            'headers': {**get_cors_headers(), 'Content-Type': 'application/json'},
            'body': json.dumps(data)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': str(e)})
        }

# Define o tempo de espera (em segundos) entre as requisições da recursão para evitar bloqueios
RATE_LIMIT_SECONDS = 0.5