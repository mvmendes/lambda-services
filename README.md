# Lambda Services Repository 🚀

Repository for serverless microservices on AWS Lambda. Currently contains:

## 🕷️ Web Scraping Microservice (`/scrape-service`)

### Key Features
- ✅ HTTP requests with redirect handling
- ✅ HTML parsing with BeautifulSoup
- ✅ Markdown conversion with link preservation
- ✅ Image extraction with absolute URLs
- ✅ Recursive link processing with depth control
- ✅ PDF, DOCX and XLSX file processing
- ✅ Link filtering via regex patterns
- ✅ Docker/ZIP deployment
- ✅ Function URL support
- ✅ Cross-platform deployment scripts (PowerShell/Bash)

### Quick Start
```bash
# Clone repository
git clone https://github.com/mvmendes/lambda-services.git
cd lambda-services/scrape-service

# Configure AWS credentials (if not already done)
aws configure

# Set environment variables (optional)
export AWS_PROFILE="your-profile"    # Default: "default"
export AWS_REGION="sa-east-1"        # Default: "us-east-1"
export LAMBDA_FUNCTION="ScrapeService"

# Deploy (Linux/MacOS)
chmod +x build_and_deploy.sh
./build_and_deploy.sh

# OR Deploy (Windows PowerShell)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\build_and_deploy.ps1
```

### Project Structure
```
scrape-service/
├── src/                    # Core source code
│   └── scrape_lambda.py    # Lambda handler
├── test/                   # Automated tests
├── Dockerfile              # Container config
├── build_and_deploy.sh     # Linux/MacOS deployment
├── build_and_deploy.ps1     # Windows deployment
├── requirements.txt        # Python dependencies
└── README.md              # Service documentation
```

[Detailed Service Guide](./scrape-service/README.md)

## 🔧 Core Technologies
- **AWS Lambda** - Serverless execution
- **Python 3.12** - Core logic
- **Docker** - Container packaging
- **BeautifulSoup** - HTML parsing
- **Pytest** - Automated testing
- **PowerShell/Bash** - Cross-platform deployment

## 📦 Repository Structure
Each service directory contains:
- Source code
- Cross-platform deployment scripts
- Dockerfile for container deployment
- Service-specific documentation
- Unit tests
- Requirements file

## 🔐 Required AWS Permissions
The deployment user needs these permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:GetFunction",
                "lambda:CreateFunctionUrlConfig",
                "lambda:AddPermission",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": [
                "arn:aws:lambda:*:*:function:ScrapeService*",
                "arn:aws:logs:*:*:log-group:/aws/lambda/ScrapeService*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:PassRole",
                "iam:CreateRole",
                "iam:GetRole",
                "iam:AttachRolePolicy"
            ],
            "Resource": "arn:aws:iam::*:role/lambda-scrape-service-role"
        }
    ]
}
```

## 🤝 Contribution
1. Fork repository
2. Create feature branch (`git checkout -b feature/fooBar`)
3. Commit changes (`git commit -am 'Add fooBar'`)
4. Push branch (`git push origin feature/fooBar`)
5. Open Pull Request

## 📄 License
MIT License - See [LICENSE](./LICENSE)

---

**Next Steps:** Ready to add new microservices following the same structure.
