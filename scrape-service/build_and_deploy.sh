#!/bin/bash

SERVICE_NAME="scrape-service"
LAMBDA_ZIP="scrape-lambda.zip"

# Configurable variables with env fallback
AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"
LAMBDA_FUNCTION="${LAMBDA_FUNCTION:-ScrapeService}"
LAMBDA_ROLE="${LAMBDA_ROLE:-lambda-scrape-service-role}"

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Error handling function
handle_error() {
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

# Print configuration
echo -e "\n${CYAN}Current Configuration:"
echo "====================="
echo -e "${YELLOW}SERVICE_NAME: $SERVICE_NAME"
echo "LAMBDA_ZIP: $LAMBDA_ZIP"
echo "AWS_PROFILE: $AWS_PROFILE"
echo "AWS_REGION: $AWS_REGION"
echo "LAMBDA_FUNCTION: $LAMBDA_FUNCTION"
echo "LAMBDA_ROLE: $LAMBDA_ROLE"
echo -e "${CYAN}=====================${NC}\n"

echo -e "${GREEN}Starting deployment process...${NC}"

# Package
echo "Creating deployment package..."
try {
    # Ensure package directory exists and is empty
    if [ -d "package" ]; then
        rm -rf package/*
    else
        mkdir -p package
    fi

    # Install dependencies
    pip install -r requirements.txt -t ./package || handle_error "Failed to install dependencies"

    # Copy source files to package
    mkdir -p package/src
    cp -r src/* package/src/ || handle_error "Failed to copy source files"

    # Create ZIP file
    (cd package && zip -r ../${LAMBDA_ZIP} .) || handle_error "Failed to create package zip"
} catch {
    handle_error "Failed to create deployment package"
}

# Check if Lambda function exists
echo "Checking if Lambda function exists..."
if aws lambda get-function --function-name ${LAMBDA_FUNCTION} --region ${AWS_REGION} --profile ${AWS_PROFILE} >/dev/null 2>&1; then
    echo -e "${GREEN}Lambda function found.${NC}"
    
    # Update existing function
    echo "Updating existing Lambda function..."
    update_result=$(aws lambda update-function-code \
        --function-name ${LAMBDA_FUNCTION} \
        --zip-file fileb://${LAMBDA_ZIP} \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} 2>&1)
    
    if [ $? -ne 0 ]; then
        handle_error "Failed to update Lambda function: $update_result"
    else
        echo -e "${GREEN}Lambda function updated successfully!${NC}"
    fi
else
    echo -e "${YELLOW}Lambda function does not exist. Will create new function.${NC}"
    
    # Check/Create IAM role
    echo "Checking IAM role..."
    if role_arn=$(aws iam get-role --role-name ${LAMBDA_ROLE} --profile ${AWS_PROFILE} --query 'Role.Arn' --output text 2>/dev/null); then
        echo -e "${GREEN}Using existing IAM role: $role_arn${NC}"
    else
        echo -e "${YELLOW}Creating new IAM role...${NC}"
        trust_policy='{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        }'
        
        role_arn=$(aws iam create-role \
            --role-name ${LAMBDA_ROLE} \
            --assume-role-policy-document "$trust_policy" \
            --profile ${AWS_PROFILE} \
            --query 'Role.Arn' \
            --output text)
        
        if [ $? -ne 0 ]; then
            handle_error "Failed to create IAM role"
        fi
        
        echo -e "${GREEN}IAM role created successfully.${NC}"
        
        # Attach Lambda execution policy
        echo "Attaching Lambda execution policy..."
        aws iam attach-role-policy \
            --role-name ${LAMBDA_ROLE} \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
            --profile ${AWS_PROFILE}
        
        if [ $? -ne 0 ]; then
            handle_error "Failed to attach role policy"
        fi
        
        echo -e "${YELLOW}Waiting for IAM role propagation...${NC}"
        sleep 10
    fi
    
    # Create Lambda function
    echo "Creating new Lambda function..."
    create_result=$(aws lambda create-function \
        --function-name ${LAMBDA_FUNCTION} \
        --runtime python3.12 \
        --handler scrape_lambda.lambda_handler \
        --role ${role_arn} \
        --zip-file fileb://${LAMBDA_ZIP} \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} \
        --timeout 30 \
        --memory-size 512 2>&1)
    
    if [ $? -ne 0 ]; then
        handle_error "Failed to create Lambda function: $create_result"
    fi
    echo -e "${GREEN}Lambda function created successfully!${NC}"
    
    # Configure Function URL
    echo "Configuring Lambda Function URL..."
    url_config=$(aws lambda create-function-url-config \
        --function-name ${LAMBDA_FUNCTION} \
        --auth-type NONE \
        --cors '{
            "AllowOrigins": ["*"],
            "AllowMethods": ["POST"],
            "AllowHeaders": ["*"],
            "ExposeHeaders": ["*"],
            "MaxAge": 86400
        }' \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} 2>&1)
    
    if [ $? -eq 0 ]; then
        function_url=$(echo "$url_config" | grep -o '"FunctionUrl": "[^"]*' | cut -d'"' -f4)
        echo -e "${GREEN}Function URL created: $function_url${NC}"
    else
        echo -e "${YELLOW}Warning: Failed to create function URL: $url_config${NC}"
    fi
    
    # Add Function URL permissions
    echo "Adding Function URL permissions..."
    permission_result=$(aws lambda add-permission \
        --function-name ${LAMBDA_FUNCTION} \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} 2>&1)
    
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Warning: Failed to add URL permissions: $permission_result${NC}"
    fi
fi

echo -e "\n${GREEN}Deployment completed successfully!${NC}"

# Optional: For container deployment
: <<'EOF'
docker build -t ${SERVICE_NAME} .
aws ecr create-repository --repository-name ${SERVICE_NAME} --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
docker tag ${SERVICE_NAME}:latest <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest
docker push <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest
EOF 