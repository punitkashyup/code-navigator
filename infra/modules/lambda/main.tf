# ECR Repository for Lambda Container
resource "aws_ecr_repository" "lambda_webhook" {
  name                 = "${var.name_prefix}-webhook-lambda"
  image_tag_mutability = "MUTABLE"
  force_delete         = true  # Allow deletion even with images

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-webhook-lambda-ecr"
  })
}

# ECR Repository Policy
resource "aws_ecr_repository_policy" "lambda_webhook" {
  repository = aws_ecr_repository.lambda_webhook.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
      }
    ]
  })
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "lambda_webhook" {
  repository = aws_ecr_repository.lambda_webhook.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Delete untagged images older than 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPost",
          "es:ESHttpPut",
          "es:ESHttpDelete"
        ]
        Resource = "arn:aws:es:*:*:domain/*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:*:*:function:${var.name_prefix}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach AWS managed policy for VPC access
resource "aws_iam_role_policy_attachment" "lambda_vpc_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Data source to get current region and account
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local to control Lambda function creation
locals {
  # Simple count based on enable_lambda_creation flag
  lambda_count = var.enable_lambda_creation ? 1 : 0
}

# Null resource to automatically build and push Docker image
resource "null_resource" "docker_build_push" {
  count = var.auto_build_docker ? 1 : 0
  
  triggers = {
    # Rebuild when Dockerfile or source code changes
    dockerfile_hash = fileexists("../webhook-solution/Dockerfile") ? filemd5("../webhook-solution/Dockerfile") : "no-dockerfile"
    ecr_repo_url    = aws_ecr_repository.lambda_webhook.repository_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Building and pushing Docker image..."
      cd ../webhook-solution
      
      # Check if Dockerfile exists
      if [ ! -f "Dockerfile" ]; then
        echo "Warning: Dockerfile not found in webhook-solution directory"
        exit 0
      fi
      
      # Authenticate Docker to ECR
      aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin ${aws_ecr_repository.lambda_webhook.repository_url}
      
      # Build and push the image
      docker build -t webhook-lambda .
      docker tag webhook-lambda:latest ${aws_ecr_repository.lambda_webhook.repository_url}:latest
      docker push ${aws_ecr_repository.lambda_webhook.repository_url}:latest
      
      echo "Docker image built and pushed successfully!"
    EOT
  }

  depends_on = [aws_ecr_repository.lambda_webhook]
}

# Note: Lambda function creation is controlled by enable_lambda_creation variable
# This allows for two-stage deployment: first build Docker image, then create Lambda

# Lambda Function with container image
# Note: This requires the Docker image to be built and pushed to ECR first
# Run the build-and-deploy-lambda.sh script after initial deployment
resource "aws_lambda_function" "webhook" {
  count = local.lambda_count  # Automatically enable when auto_build_docker is true
  
  function_name = "${var.name_prefix}-webhook-handler"
  role         = aws_iam_role.lambda_role.arn
  package_type = "Image"
  image_uri    = "${aws_ecr_repository.lambda_webhook.repository_url}:latest"
  timeout      = 300
  memory_size  = 512

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  environment {
    variables = {
      OPENSEARCH_URL           = "https://${var.opensearch_endpoint}"
      OPENSEARCH_ADMIN_PW      = var.opensearch_password
      OPENSEARCH_USER          = var.opensearch_user
      OPENSEARCH_INDEX         = "code_index"
      OPENSEARCH_TEXT_FIELD    = "text"
      OPENSEARCH_VECTOR_FIELD  = "vector_field"
      OPENSEARCH_BULK_SIZE     = "500"
      BEDROCK_MODEL_ID         = "amazon.titan-embed-text-v2:0"
      GITHUB_WEBHOOK_SECRET    = var.github_webhook_secret
      GITHUB_TOKEN             = var.github_token
      OPENAI_API_KEY           = var.openai_api_key
      CHUNKER_MAX_CHARS        = "1500"
      CHUNKER_COALESCE         = "200"
      GENERATE_AI_DESCRIPTIONS = "true"
      CHUNK_DESC_PROVIDER      = "openai"
    }
  }

  # Ignore changes to image_uri to allow for CI/CD updates
  lifecycle {
    ignore_changes = [image_uri]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-webhook-handler"
  })

  # Wait for the ECR repository and Docker image to be created
  depends_on = [
    aws_ecr_repository.lambda_webhook,
    null_resource.docker_build_push
  ]
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.name_prefix}-webhook-handler"
  retention_in_days = 7

  tags = var.tags
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "webhook" {
  name        = "${var.name_prefix}-webhook-api"
  description = "API Gateway for GitHub webhook integration"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

# API Gateway Resource
resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  parent_id   = aws_api_gateway_rest_api.webhook.root_resource_id
  path_part   = "webhook"
}

# API Gateway Method
resource "aws_api_gateway_method" "webhook_post" {
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Method for OPTIONS (CORS)
resource "aws_api_gateway_method" "webhook_options" {
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# API Gateway Integration
resource "aws_api_gateway_integration" "webhook_post" {
  count = length(aws_lambda_function.webhook) > 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook[0].invoke_arn
}

# Mock API Gateway Integration for webhook POST when Lambda doesn't exist
resource "aws_api_gateway_integration" "webhook_post_mock" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 503
    })
  }
}

# Mock Integration Response for webhook POST
resource "aws_api_gateway_integration_response" "webhook_post_mock" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method
  status_code = "503"

  depends_on = [aws_api_gateway_integration.webhook_post_mock]
}

# Method Response for webhook POST 503
resource "aws_api_gateway_method_response" "webhook_post_503" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method
  status_code = "503"
}

# API Gateway Integration for OPTIONS
resource "aws_api_gateway_integration" "webhook_options" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

# API Gateway Method Response
resource "aws_api_gateway_method_response" "webhook_post" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
}

# API Gateway Method Response for OPTIONS
resource "aws_api_gateway_method_response" "webhook_options" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Headers" = true
  }
}

# API Gateway Integration Response
resource "aws_api_gateway_integration_response" "webhook_post" {
  count = length(aws_lambda_function.webhook) > 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method
  status_code = aws_api_gateway_method_response.webhook_post.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  }

  depends_on = [
    aws_api_gateway_integration.webhook_post,
    aws_api_gateway_method_response.webhook_post
  ]
}

# API Gateway Integration Response for OPTIONS
resource "aws_api_gateway_integration_response" "webhook_options" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_options.http_method
  status_code = aws_api_gateway_method_response.webhook_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  }
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "webhook" {
  depends_on = [
    aws_api_gateway_integration.webhook_options,
    aws_api_gateway_integration.webhook_post,
    aws_api_gateway_integration.webhook_post_mock,
    aws_api_gateway_integration.health_get,
    aws_api_gateway_integration.health_get_mock,
    aws_api_gateway_method.webhook_post,
    aws_api_gateway_method.webhook_options,
    aws_api_gateway_method.health_get
  ]

  rest_api_id = aws_api_gateway_rest_api.webhook.id

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "webhook" {
  deployment_id = aws_api_gateway_deployment.webhook.id
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  stage_name    = "prod"

  tags = var.tags
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway_invoke" {
  count = length(aws_lambda_function.webhook) > 0 ? 1 : 0
  
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.webhook.execution_arn}/*/*"
}

# Health Check Resource
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  parent_id   = aws_api_gateway_rest_api.webhook.root_resource_id
  path_part   = "health"
}

# Health Check Method
resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

# Health Check Integration
resource "aws_api_gateway_integration" "health_get" {
  count = length(aws_lambda_function.webhook) > 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook[0].invoke_arn
}

# Mock Health Check Integration when Lambda doesn't exist
resource "aws_api_gateway_integration" "health_get_mock" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 503
    })
  }
}

# Mock Integration Response for health GET
resource "aws_api_gateway_integration_response" "health_get_mock" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = "503"

  depends_on = [aws_api_gateway_integration.health_get_mock]
}

# Method Response for health GET 503
resource "aws_api_gateway_method_response" "health_get_503" {
  count = length(aws_lambda_function.webhook) == 0 ? 1 : 0
  
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = "503"
}