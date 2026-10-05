# INTENTIONAL Terraform scanner fixtures (batch 3) — Low → Critical

resource "aws_security_group" "batch3_critical_open" {
  name        = "batch3-critical-open"
  description = "INTENTIONAL: all traffic from anywhere"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Severity = "critical"
    Fixture  = "batch3"
  })
}

resource "aws_iam_role" "batch3_critical_admin" {
  name = "batch3-critical-admin"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "*" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "batch3_critical_admin" {
  name = "batch3-critical-admin-inline"
  role = aws_iam_role.batch3_critical_admin.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

resource "aws_s3_bucket" "batch3_high_public" {
  bucket = "batch3-scanner-fixture-public"
  acl    = "public-read"

  tags = {
    Fixture  = "batch3"
    Severity = "high"
  }
}

resource "aws_s3_bucket_public_access_block" "batch3_high_public" {
  bucket = aws_s3_bucket.batch3_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

locals {
  batch3_aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  batch3_aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  batch3_db_password           = "Batch3-TF-Scanner-Only-P@ss"
}

resource "aws_db_instance" "batch3_medium_rds" {
  identifier                 = "batch3-medium-rds"
  engine                     = "postgres"
  engine_version             = "11.22"
  instance_class             = "db.t3.micro"
  allocated_storage          = 20
  username                   = "postgres"
  password                   = local.batch3_db_password
  publicly_accessible        = true
  storage_encrypted          = false
  skip_final_snapshot        = true
  backup_retention_period    = 0
  deletion_protection        = false
  auto_minor_version_upgrade = false

  tags = {
    Fixture  = "batch3"
    Severity = "medium"
  }
}

resource "aws_instance" "batch3_medium_ec2" {
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "t2.micro"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.batch3_critical_open.id]
  monitoring                  = false

  root_block_device {
    encrypted = false
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "optional"
  }

  user_data = <<-EOF
              #!/bin/bash
              export AWS_ACCESS_KEY_ID=${local.batch3_aws_access_key_id}
              export AWS_SECRET_ACCESS_KEY=${local.batch3_aws_secret_access_key}
              EOF

  tags = {
    Name     = "batch3-medium-ec2"
    Fixture  = "batch3"
    Severity = "medium"
  }
}

resource "aws_s3_bucket" "batch3_low_nolog" {
  bucket = "batch3-scanner-fixture-nolog"
  acl    = "private"

  tags = {
    Fixture  = "batch3"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "batch3_low_nolog" {
  bucket = aws_s3_bucket.batch3_low_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_cloudwatch_log_group" "batch3_low_logs" {
  name              = "/batch3/scanner-fixture"
  retention_in_days = 0

  tags = {
    Fixture  = "batch3"
    Severity = "low"
  }
}
