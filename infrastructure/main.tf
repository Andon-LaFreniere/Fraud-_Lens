terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

# ─── DynamoDB Tables ───────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "transactions" {
  name           = "fraudlens-transactions"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "transactionId"
  range_key      = "accountId"

  attribute {
    name = "transactionId"
    type = "S"
  }
  attribute {
    name = "accountId"
    type = "S"
  }

  global_secondary_index {
    name            = "accountId-index"
    hash_key        = "accountId"
    projection_type = "ALL"
  }

  tags = { Project = "fraudlens" }
}

resource "aws_dynamodb_table" "alerts" {
  name           = "fraudlens-alerts"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "alertId"
  range_key      = "transactionId"

  attribute {
    name = "alertId"
    type = "S"
  }
  attribute {
    name = "transactionId"
    type = "S"
  }

  tags = { Project = "fraudlens" }
}

# ─── Lambda for Fraud Scoring Service ──────────────────────────────────────────

resource "aws_lambda_function" "fraud_scorer" {
  function_name = "fraudlens-scorer"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.fraud_scorer.repository_url}:latest"
  timeout       = 30
  memory_size   = 512

  environment {
    variables = {
      TRANSACTION_SERVICE_URL = "http://${aws_elastic_beanstalk_environment.transaction_service.cname}"
      AWS_REGION_NAME         = var.aws_region
      KAFKA_BOOTSTRAP_SERVERS = var.kafka_bootstrap_servers
    }
  }
}

resource "aws_api_gateway_rest_api" "fraud_scorer_api" {
  name = "fraudlens-scoring-api"
}

# ─── ECR for Docker image ──────────────────────────────────────────────────────

resource "aws_ecr_repository" "fraud_scorer" {
  name = "fraudlens-scorer"
}

# ─── IAM Role for Lambda ───────────────────────────────────────────────────────

resource "aws_iam_role" "lambda_exec" {
  name = "fraudlens-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ─── Elastic Beanstalk for Spring Boot ─────────────────────────────────────────

resource "aws_elastic_beanstalk_application" "transaction_service" {
  name = "fraudlens-transaction-service"
}

resource "aws_elastic_beanstalk_environment" "transaction_service" {
  name                = "fraudlens-tx-env"
  application         = aws_elastic_beanstalk_application.transaction_service.name
  solution_stack_name = "64bit Amazon Linux 2023 v4.1.0 running Corretto 17"

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "InstanceType"
    value     = "t3.small"
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "KAFKA_BOOTSTRAP_SERVERS"
    value     = var.kafka_bootstrap_servers
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "AWS_REGION"
    value     = var.aws_region
  }
}

variable "kafka_bootstrap_servers" {
  description = "MSK or self-managed Kafka bootstrap servers"
  type        = string
}

# ─── Outputs ───────────────────────────────────────────────────────────────────

output "transaction_service_url" {
  value = aws_elastic_beanstalk_environment.transaction_service.cname
}

output "fraud_scorer_api_id" {
  value = aws_api_gateway_rest_api.fraud_scorer_api.id
}

output "transactions_table_name" {
  value = aws_dynamodb_table.transactions.name
}

output "alerts_table_name" {
  value = aws_dynamodb_table.alerts.name
}
