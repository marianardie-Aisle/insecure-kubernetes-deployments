# INTENTIONAL Terraform scanner fixtures (batch 5) — Low → Critical

resource "aws_security_group" "batch5_critical_open" {
  name        = "batch5-critical-open"
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
    Fixture  = "batch5"
  })
}

resource "aws_iam_role" "batch5_critical_admin" {
  name = "batch5-critical-admin"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "*" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "batch5_critical_admin" {
  name = "batch5-critical-admin-inline"
  role = aws_iam_role.batch5_critical_admin.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

resource "aws_s3_bucket" "batch5_high_public" {
  bucket = "batch5-scanner-fixture-public"
  acl    = "public-read"

  tags = {
    Fixture  = "batch5"
    Severity = "high"
  }
}

resource "aws_s3_bucket_public_access_block" "batch5_high_public" {
  bucket = aws_s3_bucket.batch5_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

locals {
  batch5_aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  batch5_aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  batch5_db_password           = "Batch5-TF-Scanner-Only-P@ss"
}

resource "aws_db_instance" "batch5_medium_rds" {
  identifier                 = "batch5-medium-rds"
  engine                     = "mariadb"
  engine_version             = "10.4"
  instance_class             = "db.t3.micro"
  allocated_storage          = 20
  username                   = "admin"
  password                   = local.batch5_db_password
  publicly_accessible        = true
  storage_encrypted          = false
  skip_final_snapshot        = true
  backup_retention_period    = 0
  deletion_protection        = false
  auto_minor_version_upgrade = false

  tags = {
    Fixture  = "batch5"
    Severity = "medium"
  }
}

resource "aws_instance" "batch5_medium_ec2" {
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "t2.micro"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.batch5_critical_open.id]
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
              export AWS_ACCESS_KEY_ID=${local.batch5_aws_access_key_id}
              export AWS_SECRET_ACCESS_KEY=${local.batch5_aws_secret_access_key}
              EOF

  tags = {
    Name     = "batch5-medium-ec2"
    Fixture  = "batch5"
    Severity = "medium"
  }
}

resource "aws_s3_bucket" "batch5_low_nolog" {
  bucket = "batch5-scanner-fixture-nolog"
  acl    = "private"

  tags = {
    Fixture  = "batch5"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "batch5_low_nolog" {
  bucket = aws_s3_bucket.batch5_low_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_kms_key" "batch5_low_kms" {
  description             = "batch5 scanner fixture key"
  deletion_window_in_days = 7
  enable_key_rotation     = false

  tags = {
    Fixture  = "batch5"
    Severity = "low"
  }
}
