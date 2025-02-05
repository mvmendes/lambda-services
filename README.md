# Lambda Services Repository 🚀

Repository for serverless microservices on AWS Lambda. Currently contains:

## 🕷️ Web Scraping Microservice (`/scrape-service`)

### Key Features
- ✅ HTTP requests with redirect handling
- ✅ HTML parsing with BeautifulSoup
- ✅ Markdown conversion with link preservation
- ✅ Image extraction with absolute URLs
- ✅ Docker/ZIP deployment
- ✅ API Gateway integration

### Quick Start
```bash
git clone https://github.com/mvmendes/lambda-services.git
cd lambda-services/scrape-service

# Configure (optional)
export AWS_PROFILE="your-profile"
export AWS_REGION="us-east-2"

# Deploy
./build_and_deploy.sh
```

### Project Structure
```
scrape-service/
├── src/              # Core source code
│   └── scrape_lambda.py  # Lambda handler
├── test/             # Automated tests
├── Dockerfile        # Container config
├── build_and_deploy.sh # Deployment script
└── requirements.txt  # Dependencies
```

[Detailed Guide](./scrape-service/README.md)

## 🔧 Core Technologies
- **AWS Lambda** - Serverless execution
- **Python 3.12** - Core logic
- **Docker** - Container packaging
- **BeautifulSoup** - HTML parsing
- **Pytest** - Automated testing

## 📦 Repository Structure
Independent service directories each containing:
- Source code
- Dockerfile
- Deployment scripts
- Service-specific docs
- Unit tests

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
