#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}CodeNavigator Complete Infrastructure Deployment${NC}"
echo "=================================================="

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
echo -e "${YELLOW}Step 3: Building and pushing Docker images...${NC}"

# Get ECR repository URLs
LAMBDA_ECR_REPO_URL=$(terraform output -raw ecr_repository_url 2>/dev/null)
MCP_ECR_REPO_URL=$(terraform output -raw mcp_ecr_repository_url 2>/dev/null)

if [ -z "$LAMBDA_ECR_REPO_URL" ] || [ -z "$MCP_ECR_REPO_URL" ]; then
    echo -e "${RED}Error: Could not get ECR repository URLs from Terraform output${NC}"
    exit 1
fi

echo -e "${GREEN}Lambda ECR Repository: ${LAMBDA_ECR_REPO_URL}${NC}"
echo -e "${GREEN}MCP Server ECR Repository: ${MCP_ECR_REPO_URL}${NC}"

# Get AWS region
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-2")

# Authenticate Docker to ECR
echo -e "${YELLOW}Authenticating Docker to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${LAMBDA_ECR_REPO_URL%/*}

# Build Lambda Webhook Docker image
echo -e "${YELLOW}Building Lambda Webhook Docker image...${NC}"
if [ -f "../webhook-solution/Dockerfile" ]; then
    cd ../webhook-solution
    docker build -f Dockerfile -t webhook-lambda .
    docker tag webhook-lambda:latest $LAMBDA_ECR_REPO_URL:latest
    docker push $LAMBDA_ECR_REPO_URL:latest
    echo -e "${GREEN}✓ Lambda image built and pushed successfully${NC}"
    cd ../infra
else
    echo -e "${YELLOW}Warning: Lambda Dockerfile not found at ../webhook-solution/Dockerfile${NC}"
fi

# Build MCP Server Docker image
echo -e "${YELLOW}Building MCP Server Docker image...${NC}"
if [ -f "../mcp-server/Dockerfile" ]; then
    cd ../mcp-server
    docker build -f Dockerfile -t mcp-server .
    docker tag mcp-server:latest $MCP_ECR_REPO_URL:latest
    docker push $MCP_ECR_REPO_URL:latest
    echo -e "${GREEN}✓ MCP Server image built and pushed successfully${NC}"
    cd ../infra
else
    echo -e "${YELLOW}Warning: MCP Server Dockerfile not found, will use auto-generated placeholder${NC}"
fi

echo -e "${GREEN}✓ All Docker images processed successfully${NC}"

# Wait a moment for ECR to register the image
echo -e "${YELLOW}Waiting for ECR to register the image...${NC}"
sleep 10

echo -e "${YELLOW}Step 4: Enabling Lambda function...${NC}"
terraform apply -var-file=environments/dev.tfvars -var="auto_build_docker=true" -var="enable_lambda_creation=true" -auto-approve

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Lambda deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Lambda function enabled successfully${NC}"

echo ""
echo -e "${BLUE}🎉 CodeNavigator Deployment Summary:${NC}"
echo "============================================"
echo -e "${GREEN}Infrastructure:${NC}"
echo -e "  • VPC & Networking: ✅ Deployed"
echo -e "  • Security Groups: ✅ Configured"
echo -e "  • Application Load Balancer: ✅ Running"
echo -e "  • EC2 MCP Server: ✅ Running"
echo -e "  • OpenSearch Domain: ✅ Active"
echo -e "  • GuardDuty Security: ✅ Monitoring"
echo ""
echo -e "${GREEN}Container Services:${NC}"
echo -e "  • Lambda ECR Repository: ${LAMBDA_ECR_REPO_URL}"
echo -e "  • MCP Server ECR Repository: ${MCP_ECR_REPO_URL}"
echo -e "  • Lambda Function: $(terraform output -raw webhook_function_name 2>/dev/null || echo 'N/A')"
echo ""
echo -e "${GREEN}API Endpoints:${NC}"
echo -e "  • ALB DNS (MCP Server): $(terraform output -raw alb_dns_name 2>/dev/null || echo 'N/A')"
echo -e "  • API Gateway (Lambda): $(terraform output -raw webhook_api_gateway_url 2>/dev/null || echo 'N/A')"
echo -e "  • Webhook Endpoint: $(terraform output -raw webhook_endpoint 2>/dev/null || echo 'N/A')"
echo -e "  • OpenSearch Dashboard: $(terraform output -raw opensearch_kibana_endpoint 2>/dev/null || echo 'N/A')"
echo ""
echo -e "${GREEN}🚀 Complete CodeNavigator infrastructure deployed successfully!${NC}"