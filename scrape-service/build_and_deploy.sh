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

# Install dependencies
echo "Installing dependencies..."
mkdir -p package
pip install -r requirements.txt -t ./package || handle_error "Failed to install dependencies"

# Package
echo "Creating deployment package..."
(cd package && zip -r ../${LAMBDA_ZIP} .) || handle_error "Failed to create package zip"
zip -g ${LAMBDA_ZIP} src/scrape_lambda.py || handle_error "Failed to add lambda handler to zip"

# Check if Lambda function exists
echo "Checking if Lambda function exists..."
function_exists=false
if aws lambda get-function --function-name ${LAMBDA_FUNCTION} --region ${AWS_REGION} --profile ${AWS_PROFILE} >/dev/null 2>&1; then
    function_exists=true
    echo -e "${GREEN}Lambda function found.${NC}"
else
    echo -e "${YELLOW}Lambda function does not exist. Will create new function.${NC}"
fi

if [ "$function_exists" = true ]; then
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
    # Create IAM role if it doesn't exist
    echo "Checking IAM role..."
    role_arn=""
    if role_response=$(aws iam get-role --role-name ${LAMBDA_ROLE} --profile ${AWS_PROFILE} --query 'Role.Arn' --output text 2>&1); then
        role_arn=$role_response
        echo -e "${GREEN}Using existing IAM role: $role_arn${NC}"
    else
        echo -e "${YELLOW}Creating new IAM role...${NC}"
        trust_policy=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
)
        
        role_result=$(aws iam create-role \
            --role-name ${LAMBDA_ROLE} \
            --assume-role-policy-document "$trust_policy" \
            --profile ${AWS_PROFILE} \
            --query 'Role.Arn' \
            --output text 2>&1)
        
        if [ $? -ne 0 ]; then
            handle_error "Failed to create IAM role: $role_result"
        fi
        role_arn=$role_result

        attach_result=$(aws iam attach-role-policy \
            --role-name ${LAMBDA_ROLE} \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
            --profile ${AWS_PROFILE} 2>&1)
        
        if [ $? -ne 0 ]; then
            handle_error "Failed to attach role policy: $attach_result"
        fi

        echo -e "${GREEN}IAM role created successfully. Waiting for propagation...${NC}"
        sleep 10
    fi

    # Create new Lambda function
    echo "Creating new Lambda function..."
    create_result=$(aws lambda create-function \
        --function-name ${LAMBDA_FUNCTION} \
        --runtime python3.12 \
        --handler src.scrape_lambda.lambda_handler \
        --role ${role_arn} \
        --zip-file fileb://${LAMBDA_ZIP} \
        --region ${AWS_REGION} \
        --profile ${AWS_PROFILE} \
        --timeout 30 \
        --memory-size 512 2>&1)
    
    if [ $? -ne 0 ]; then
        handle_error "Failed to create Lambda function: $create_result"
    else
        echo -e "${GREEN}Lambda function created successfully!${NC}"
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