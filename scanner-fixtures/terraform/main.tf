# INTENTIONAL Terraform scanner fixtures (Low → Critical).
# Do not apply in real environments.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# CRITICAL: security group open to the world on all ports
resource "aws_security_group" "scanner_critical_open" {
  name        = "scanner-fixture-critical-open"
  description = "INTENTIONAL: allow all ingress from 0.0.0.0/0"

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# HIGH: S3 bucket publicly readable + no encryption
resource "aws_s3_bucket" "scanner_high_public" {
  bucket = "scanner-fixture-batch1-public-bucket"
  acl    = "public-read"
}

resource "aws_s3_bucket_public_access_block" "scanner_high_public" {
  bucket = aws_s3_bucket.scanner_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# HIGH: IAM policy with Action/Resource wildcards
resource "aws_iam_policy" "scanner_high_admin" {
  name        = "scanner-fixture-high-admin"
  description = "INTENTIONAL overbroad IAM"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "*"
        Resource = "*"
      }
    ]
  })
}

# MEDIUM: RDS instance publicly accessible with weak storage settings
resource "aws_db_instance" "scanner_medium_rds" {
  identifier                   = "scanner-fixture-medium"
  engine                       = "mysql"
  engine_version               = "5.7"
  instance_class               = "db.t3.micro"
  allocated_storage            = 20
  username                     = "admin"
  password                     = "Batch1-Scanner-Only-P@ss"
  publicly_accessible          = true
  skip_final_snapshot          = true
  storage_encrypted            = false
  backup_retention_period      = 0
  auto_minor_version_upgrade   = false
}

# LOW: CloudTrail disabled-style omission / logging off on bucket
resource "aws_s3_bucket" "scanner_low_no_logging" {
  bucket = "scanner-fixture-batch1-no-logging"
}

resource "aws_s3_bucket_versioning" "scanner_low_no_logging" {
  bucket = aws_s3_bucket.scanner_low_no_logging.id
  versioning_configuration {
    status = "Suspended"
  }
}
