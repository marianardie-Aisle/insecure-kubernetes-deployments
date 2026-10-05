# INTENTIONAL Terraform scanner fixtures — LOW severity only
# No open security groups, public buckets, wildcard IAM, or hardcoded cloud keys.

resource "aws_s3_bucket" "low_only_nolog" {
  bucket = "low-only-scanner-fixture-nolog"

  tags = {
    Fixture  = "low-only"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "low_only_nolog" {
  bucket = aws_s3_bucket.low_only_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_cloudwatch_log_group" "low_only_logs" {
  name              = "/low-only/scanner-fixture"
  retention_in_days = 0

  tags = {
    Fixture  = "low-only"
    Severity = "low"
  }
}

resource "aws_cloudtrail" "low_only_trail" {
  name                          = "low-only-scanner-fixture-trail"
  s3_bucket_name                = aws_s3_bucket.low_only_nolog.id
  include_global_service_events = false
  is_multi_region_trail         = false
  enable_log_file_validation    = false

  tags = {
    Fixture  = "low-only"
    Severity = "low"
  }
}

resource "aws_kms_key" "low_only_kms" {
  description             = "low-only scanner fixture key"
  deletion_window_in_days = 7
  enable_key_rotation     = false

  tags = {
    Fixture  = "low-only"
    Severity = "low"
  }
}
