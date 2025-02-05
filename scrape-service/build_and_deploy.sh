#!/bin/bash

SERVICE_NAME="scrape-service"
LAMBDA_ZIP="scrape-lambda.zip"

# Configurable variables with env fallback
AWS_PROFILE="${AWS_PROFILE:-default}"            # Use env or default profile
AWS_REGION="${AWS_REGION:-us-east-1}"            # Use env or default region
LAMBDA_FUNCTION="${LAMBDA_FUNCTION:-ScrapeService}" # Use env or default name

# Install dependencies
pip install -r requirements.txt -t ./package

# Package
cd package
zip -r ../${LAMBDA_ZIP} .
cd ..
zip -g ${LAMBDA_ZIP} src/scrape_lambda.py

# Deploy
aws lambda update-function-code \
  --function-name ${LAMBDA_FUNCTION} \
  --zip-file fileb://${LAMBDA_ZIP} \
  --region ${AWS_REGION} \
  --profile ${AWS_PROFILE}

# Opcional: Para implantar via container
# docker build -t ${SERVICE_NAME} .
# aws ecr create-repository --repository-name ${SERVICE_NAME} --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
# docker tag ${SERVICE_NAME}:latest <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest
# docker push <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest 