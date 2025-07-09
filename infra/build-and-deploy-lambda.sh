#!/bin/bash

# Build and deploy Lambda container to ECR
# This script builds the webhook Docker image and pushes it to ECR

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Building and Deploying Lambda Container${NC}"
echo "========================================"

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

# Get the ECR repository URL from Terraform output
echo -e "${YELLOW}Getting ECR repository URL from Terraform...${NC}"
ECR_REPO_URL=$(terraform output -raw ecr_repository_url 2>/dev/null)

if [ -z "$ECR_REPO_URL" ]; then
    echo -e "${RED}Error: Could not get ECR repository URL from Terraform output${NC}"
    echo "Make sure you have deployed the infrastructure first with: terraform apply"
    exit 1
fi

echo -e "${GREEN}ECR Repository: ${ECR_REPO_URL}${NC}"

# Get AWS region and account ID
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${GREEN}AWS Account: ${AWS_ACCOUNT_ID}${NC}"
echo -e "${GREEN}AWS Region: ${AWS_REGION}${NC}"

# Authenticate Docker to ECR
echo -e "${YELLOW}Authenticating Docker to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
cd ../webhook-solution

# Build the image
docker build -f Dockerfile -t webhook-lambda .

# Tag the image for ECR
docker tag webhook-lambda:latest $ECR_REPO_URL:latest

# Push the image to ECR
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push $ECR_REPO_URL:latest

# Update Lambda function to use the new image
echo -e "${YELLOW}Updating Lambda function...${NC}"
cd ../infra

# Get the Lambda function name
FUNCTION_NAME=$(terraform output -raw webhook_function_name)

# Update the Lambda function code
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $ECR_REPO_URL:latest \
    --region $AWS_REGION

# Wait for the update to complete
echo -e "${YELLOW}Waiting for Lambda function update to complete...${NC}"
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $AWS_REGION

echo -e "${GREEN}✓ Lambda function updated successfully!${NC}"
echo ""
echo -e "${BLUE}Deployment Summary:${NC}"
echo -e "ECR Repository: ${ECR_REPO_URL}"
echo -e "Lambda Function: ${FUNCTION_NAME}"
echo -e "API Gateway URL: $(terraform output -raw webhook_api_gateway_url)"
echo -e "Webhook Endpoint: $(terraform output -raw webhook_endpoint)"
echo ""
echo -e "${GREEN}Lambda container deployment completed successfully!${NC}"