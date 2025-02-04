# Web Scraping Microservice - AWS Lambda

## Project Structure
```
lambda-services/scrape-service/
├── src/
│   └── scrape_lambda.py
├── requirements.txt
├── Dockerfile
├── build_and_deploy.sh
├── test/
│   └── test_scrape_lambda.py
└── README.md
```

## Prerequisites
- AWS CLI configured with proper credentials
- Python 3.12
- Docker (optional for container deployment)
- Node.js (for optional monitoring setup)

## Configuration
### Environment Variables
```bash
# Required
export AWS_PROFILE=your_profile
export AWS_REGION=us-east-1

# Optional
export LOG_LEVEL=INFO
export MAX_RESPONSE_SIZE=500KB
```

## Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure
```

## Deployment
### ZIP Deployment
```bash
chmod +x build_and_deploy.sh
./build_and_deploy.sh
```

### Container Deployment
```bash
# Build image
docker build -t scrape-service .

# Authenticate with ECR
aws ecr get-login-password --region $AWS_REGION | \
docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Push image
docker tag scrape-service:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/scrape-service:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/scrape-service:latest
```

## Testing
### Unit Tests
```bash
pytest test/ -v
```

### Integration Tests
```bash
# Test with sample URL
python -m pytest test/integration/test_scrape_integration.py
```

## API Usage
**Endpoint:**  
`POST https://{api-id}.execute-api.{region}.amazonaws.com/scrape`

**Request:**
```bash
curl -X POST https://api.example.com/scrape \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"url": "https://example.com"}'
```

**Response:**
```json
{
  "markdown": "# Example Domain...",
  "images": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
  ],
  "metadata": {
    "processing_time": "1.23s",
    "content_size": "45KB"
  }
}
```

## Monitoring & Logging
```bash
# Create CloudWatch log group
aws logs create-log-group --log-group-name /aws/lambda/ScrapeService

# View real-time logs
aws logs tail /aws/lambda/ScrapeService --follow
```

## Security
- **HTTPS Enforcement:** Enabled at API Gateway
- **Rate Limiting:** 100 requests/second
- **Authentication:** API Key required
- **IAM Policies:** Least privilege access
- **Secret Rotation:** Quarterly key rotation

## Cost Optimization
- Enable Lambda Provisioned Concurrency for steady traffic
- Use CloudFront caching for frequent requests
- Set appropriate memory size (512MB recommended)
- Enable API Gateway caching

## Troubleshooting
**Common Issues:**
1. **Timeout Errors**  
   Increase Lambda timeout (max 15 minutes)

2. **Missing Dependencies**  
   Run `pip install -r requirements.txt --upgrade`

3. **Permission Denied**  
   Verify IAM roles have:
   - AWSLambdaBasicExecutionRole
   - AmazonAPIGatewayInvokeFullAccess

4. **Invalid URL Format**  
   Ensure URLs include protocol (http:// or https://)

## CI/CD Pipeline
Example GitHub Actions workflow (`.github/workflows/deploy.yml`):
```yaml
name: Deploy
on:
  push:
    branches: [ main ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: chmod +x build_and_deploy.sh
      - run: ./build_and_deploy.sh
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: 'us-east-1'
```

## Maintenance
**Dependency Updates:**
```bash
# Update all packages
pip list --outdated
pip freeze > requirements.txt
```

**Scheduled Cleanup:**
```bash
# Remove old Lambda versions
aws lambda list-versions-by-function --function-name ScrapeService
aws lambda delete-function --function-name ScrapeService --qualifier <version>
```
