# INTENTIONAL Terraform fixtures — mostly Low, plus one Critical and one High.

# CRITICAL (2): security group open to the world
resource "aws_security_group" "mostly_low_critical_open" {
  name        = "mostly-low-critical-open"
  description = "INTENTIONAL: all inbound from anywhere"
  vpc_id      = module.vpc.vpc_id

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

  tags = merge(local.common_tags, {
    Severity = "critical"
    Fixture  = "mostly-low"
  })
}

# HIGH (2): publicly readable S3 (no wildcard IAM / no live provider tokens)
resource "aws_s3_bucket" "mostly_low_high_public" {
  bucket = "mostly-low-scanner-fixture-public"
  acl    = "public-read"

  tags = {
    Fixture  = "mostly-low"
    Severity = "high"
  }
}

resource "aws_s3_bucket_public_access_block" "mostly_low_high_public" {
  bucket = aws_s3_bucket.mostly_low_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# LOW (4): S3 versioning disabled
resource "aws_s3_bucket" "mostly_low_nolog" {
  bucket = "mostly-low-scanner-fixture-nolog"

  tags = {
    Fixture  = "mostly-low"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "mostly_low_nolog" {
  bucket = aws_s3_bucket.mostly_low_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}

# LOW (5): CloudWatch log retention unset / 0
resource "aws_cloudwatch_log_group" "mostly_low_logs" {
  name              = "/mostly-low/scanner-fixture"
  retention_in_days = 0

  tags = {
    Fixture  = "mostly-low"
    Severity = "low"
  }
}

# LOW (6): KMS without key rotation
resource "aws_kms_key" "mostly_low_kms" {
  description             = "mostly-low scanner fixture key"
  deletion_window_in_days = 7
  enable_key_rotation     = false

  tags = {
    Fixture  = "mostly-low"
    Severity = "low"
  }
}
