import json
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import html2text

def lambda_handler(event, context):
    try:
        # Parse do corpo da requisição
        body = json.loads(event.get('body', '{}'))
        original_url = body.get('url')
        
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

        # Processamento do HTML
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

        # Conversão para Markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        markdown_text = converter.handle(resumo_html)
        markdown_full = f"# {title}\n\nFinal URL: [Link]({final_url})\n\n{markdown_text}"

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

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                "markdown": markdown_full,
                "images": images
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 