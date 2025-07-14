#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}CodeNavigator Infrastructure Deployment with Lambda${NC}"
echo "========================================================="

# Check if we're in the correct directory
if [ ! -f "main.tf" ]; then
    echo -e "${RED}Error: Please run this script from the Terraform directory${NC}"
    exit 1
fi

# Check if required tools are installed
for tool in docker aws terraform; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}Error: $tool is not installed${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}Step 1: Initializing Terraform...${NC}"
terraform init -backend-config=backend-config/dev.hcl -reconfigure

echo -e "${YELLOW}Step 2: Deploying infrastructure (without Lambda)...${NC}"
terraform apply -var-file=environments/dev.tfvars -var="auto_build_docker=true" -var="enable_lambda_creation=false" -auto-approve

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Infrastructure deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Infrastructure deployed successfully${NC}"

# Get the ECR repository URL from Terraform output
echo -e "${YELLOW}Step 3: Building and pushing Docker image...${NC}"
ECR_REPO_URL=$(terraform output -raw ecr_repository_url 2>/dev/null)

if [ -z "$ECR_REPO_URL" ]; then
    echo -e "${RED}Error: Could not get ECR repository URL from Terraform output${NC}"
    exit 1
fi

echo -e "${GREEN}ECR Repository: ${ECR_REPO_URL}${NC}"

# Get AWS region
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")

# Check if Dockerfile exists
if [ ! -f "../webhook-solution/Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found at ../webhook-solution/Dockerfile${NC}"
    exit 1
fi

# Authenticate Docker to ECR
echo -e "${YELLOW}Authenticating Docker to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
cd ../webhook-solution
docker build -f Dockerfile -t webhook-lambda .

# Tag the image for ECR
docker tag webhook-lambda:latest $ECR_REPO_URL:latest

# Push the image to ECR
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push $ECR_REPO_URL:latest

cd ../infra

echo -e "${GREEN}✓ Docker image built and pushed successfully${NC}"

# Wait a moment for ECR to register the image
echo -e "${YELLOW}Waiting for ECR to register the image...${NC}"
sleep 10

echo -e "${YELLOW}Step 4: Deploying Lambda function...${NC}"
terraform apply -var-file=environments/dev.tfvars -var="auto_build_docker=true" -var="enable_lambda_creation=true" -auto-approve

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Lambda deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Lambda function deployed successfully${NC}"

echo ""
echo -e "${BLUE}Deployment Summary:${NC}"
echo -e "ECR Repository: ${ECR_REPO_URL}"
echo -e "Lambda Function: $(terraform output -raw webhook_function_name 2>/dev/null || echo 'N/A')"
echo -e "API Gateway URL: $(terraform output -raw webhook_api_gateway_url 2>/dev/null || echo 'N/A')"
echo -e "Webhook Endpoint: $(terraform output -raw webhook_endpoint 2>/dev/null || echo 'N/A')"
echo ""
echo -e "${GREEN}🎉 Complete deployment finished successfully!${NC}"