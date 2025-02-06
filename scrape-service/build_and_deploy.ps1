$SERVICE_NAME = "scrape-service"
$LAMBDA_ZIP = "scrape-lambda.zip"

# Configurable variables with env fallback
$AWS_PROFILE = if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { "default" }
$AWS_REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }
$LAMBDA_FUNCTION = if ($env:LAMBDA_FUNCTION) { $env:LAMBDA_FUNCTION } else { "ScrapeService" }
$LAMBDA_ROLE = if ($env:LAMBDA_ROLE) { $env:LAMBDA_ROLE } else { "lambda-scrape-service-role" }

# Error handling function
function Handle-Error {
    param($ErrorMessage)
    Write-Host "Error: $ErrorMessage" -ForegroundColor Red
    exit 1
}

# Print configuration
Write-Host "`nCurrent Configuration:" -ForegroundColor Cyan
Write-Host "=====================" -ForegroundColor Cyan
Write-Host "SERVICE_NAME: $SERVICE_NAME" -ForegroundColor Yellow
Write-Host "LAMBDA_ZIP: $LAMBDA_ZIP" -ForegroundColor Yellow
Write-Host "AWS_PROFILE: $AWS_PROFILE" -ForegroundColor Yellow
Write-Host "AWS_REGION: $AWS_REGION" -ForegroundColor Yellow
Write-Host "LAMBDA_FUNCTION: $LAMBDA_FUNCTION" -ForegroundColor Yellow
Write-Host "LAMBDA_ROLE: $LAMBDA_ROLE" -ForegroundColor Yellow
Write-Host "=====================`n" -ForegroundColor Cyan

Write-Host "Starting deployment process..." -ForegroundColor Green

# Package
Write-Host "Creating deployment package..."
try {
    # Ensure package directory exists and is empty
    if (Test-Path -Path "package") {
        Remove-Item -Path "package\*" -Recurse -Force
    }
    else {
        New-Item -ItemType Directory -Path "package"
    }

    # Install dependencies
    pip install -r requirements.txt -t ./package

    # Copy source files to package
    if (!(Test-Path -Path "package/src")) {
        New-Item -ItemType Directory -Path "package/src"
    }
    Copy-Item -Path "src/*" -Destination "package/src" -Recurse -Force

    # Create ZIP file
    Push-Location package
    Compress-Archive -Path * -DestinationPath "../$LAMBDA_ZIP" -Force
    Pop-Location
}
catch {
    Handle-Error "Failed to create deployment package: $_"
}

# Check if Lambda function exists
$functionExists = $false
Write-Host "Checking if Lambda function exists..."
try {
    $lambdaFunction = aws lambda get-function --function-name $LAMBDA_FUNCTION --region $AWS_REGION --profile $AWS_PROFILE 2>&1
    if ($LASTEXITCODE -eq 0) {
        $functionExists = $true
        Write-Host "Lambda function found." -ForegroundColor Green
    }
    else {
        Write-Host "Lambda function does not exist. Will create new function." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Lambda function does not exist. Will create new function." -ForegroundColor Yellow
}

if ($functionExists) {
    # Update existing function
    Write-Host "Updating existing Lambda function..."
    $updateResult = aws lambda update-function-code `
        --function-name $LAMBDA_FUNCTION `
        --zip-file fileb://$LAMBDA_ZIP `
        --region $AWS_REGION `
        --profile $AWS_PROFILE 2>&1

    if ($LASTEXITCODE -ne 0) {
        Handle-Error "Failed to update Lambda function: $updateResult"
    }
    else {
        Write-Host "Lambda function updated successfully!" -ForegroundColor Green
    }
}
else {
    # Create IAM role if it doesn't exist
    Write-Host "Checking IAM role..."
    $roleArn = ""
    try {
        $roleArn = (aws iam get-role --role-name $LAMBDA_ROLE --query 'Role.Arn' --output text --profile $AWS_PROFILE 2>&1)
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Using existing IAM role: $roleArn" -ForegroundColor Green
        }
        else {
            throw "Role not found"
        }
    }
    catch {
        Write-Host "Creating new IAM role..." -ForegroundColor Yellow
        $trustPolicy = @"
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
"@

        try {
            # Try to get the role again in case it exists but we couldn't get it before
            $roleArn = (aws iam get-role --role-name $LAMBDA_ROLE --query 'Role.Arn' --output text --profile $AWS_PROFILE 2>&1)
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Found existing IAM role: $roleArn" -ForegroundColor Green
            }
            else {
                # Try to create the role
                $roleArn = (aws iam create-role `
                        --role-name $LAMBDA_ROLE `
                        --assume-role-policy-document "$trustPolicy" `
                        --profile $AWS_PROFILE `
                        --query 'Role.Arn' `
                        --output text 2>&1)

                if ($LASTEXITCODE -ne 0) {
                    if ($roleArn -like "*EntityAlreadyExists*") {
                        # If role exists but we couldn't get it, try one more time
                        Start-Sleep -Seconds 5  # Wait a bit for AWS consistency
                        $roleArn = (aws iam get-role --role-name $LAMBDA_ROLE --query 'Role.Arn' --output text --profile $AWS_PROFILE 2>&1)
                        if ($LASTEXITCODE -ne 0) {
                            Handle-Error "Failed to get existing IAM role: $roleArn"
                        }
                        Write-Host "Using existing IAM role: $roleArn" -ForegroundColor Green
                    }
                    else {
                        Handle-Error "Failed to create IAM role: $roleArn"
                    }
                }
                else {
                    Write-Host "IAM role created successfully." -ForegroundColor Green
                }
            }

            # Make sure the role has the basic Lambda execution policy
            Write-Host "Ensuring Lambda execution policy is attached..." -ForegroundColor Yellow
            $attachResult = aws iam attach-role-policy `
                --role-name $LAMBDA_ROLE `
                --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole `
                --profile $AWS_PROFILE 2>&1

            if ($LASTEXITCODE -ne 0 -and -not ($attachResult -like "*ResourceConflict*")) {
                Handle-Error "Failed to attach role policy: $attachResult"
            }

            Write-Host "Waiting for IAM role propagation..." -ForegroundColor Yellow
            Start-Sleep -Seconds 10
        }
        catch {
            Handle-Error "Failed to manage IAM role: $_"
        }
    }

    # Create new Lambda function
    Write-Host "Creating new Lambda function..."
    try {
        $createResult = aws lambda create-function `
            --function-name $LAMBDA_FUNCTION `
            --runtime python3.12 `
            --handler src.scrape_lambda.lambda_handler `
            --role $roleArn `
            --zip-file fileb://$LAMBDA_ZIP `
            --region $AWS_REGION `
            --profile $AWS_PROFILE `
            --timeout 30 `
            --memory-size 512 2>&1


        if ($LASTEXITCODE -ne 0) {
            Handle-Error "Failed to create Lambda function: $createResult"
        }
        Write-Host "Lambda function created successfully!" -ForegroundColor Green

        # Configure Function URL
        Write-Host "Configuring Lambda Function URL..." -ForegroundColor Yellow
        $urlConfig = aws lambda create-function-url-config `
            --function-name $LAMBDA_FUNCTION `
            --auth-type NONE `
            --cors '{
                "AllowOrigins": ["*"],
                "AllowMethods": ["POST"],
                "AllowHeaders": ["*"],
                "ExposeHeaders": ["*"],
                "MaxAge": 86400
            }' `
            --region $AWS_REGION `
            --profile $AWS_PROFILE 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: Failed to create function URL: $urlConfig" -ForegroundColor Yellow
        }
        else {
            $functionUrl = ($urlConfig | ConvertFrom-Json).FunctionUrl
            Write-Host "Function URL created: $functionUrl" -ForegroundColor Green
        }

        # Add permission for Function URL
        Write-Host "Adding Function URL permissions..." -ForegroundColor Yellow
        $permissionResult = aws lambda add-permission `
            --function-name $LAMBDA_FUNCTION `
            --statement-id FunctionURLAllowPublicAccess `
            --action lambda:InvokeFunctionUrl `
            --principal "*" `
            --function-url-auth-type NONE `
            --region $AWS_REGION `
            --profile $AWS_PROFILE 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: Failed to add URL permissions: $permissionResult" -ForegroundColor Yellow
        }
    }
    catch {
        Handle-Error "Failed to create Lambda function: $_"
    }
}

Write-Host "`nDeployment completed successfully!" -ForegroundColor Green

# Optional: For container deployment
<# 
docker build -t $SERVICE_NAME .
aws ecr create-repository --repository-name $SERVICE_NAME --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
docker tag ${SERVICE_NAME}:latest <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest
docker push <account-id>.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest 
#>