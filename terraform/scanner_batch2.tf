# INTENTIONAL Terraform scanner fixtures (batch 2) — Low → Critical
# Lives under terraform/ so Checkov/tfsec/KICS-style scanners see it.

# CRITICAL: security group wide open
resource "aws_security_group" "batch2_critical_open_world" {
  name        = "batch2-critical-open-world"
  description = "INTENTIONAL: all traffic from anywhere"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "all inbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
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
    Fixture  = "batch2"
  })
}

# CRITICAL: IAM user access key material pattern + admin policy
resource "aws_iam_user" "batch2_critical_admin" {
  name = "batch2-critical-admin"
  path = "/"
  tags = {
    Fixture = "batch2"
  }
}

resource "aws_iam_user_policy" "batch2_critical_admin" {
  name = "batch2-critical-admin-inline"
  user = aws_iam_user.batch2_critical_admin.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# HIGH: public S3 + ACL + no encryption block
resource "aws_s3_bucket" "batch2_high_public" {
  bucket = "batch2-scanner-fixture-public"
  acl    = "public-read"

  tags = {
    Fixture  = "batch2"
    Severity = "high"
  }
}

resource "aws_s3_bucket_public_access_block" "batch2_high_public" {
  bucket = aws_s3_bucket.batch2_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# HIGH: hardcoded secrets in terraform (AWS example credentials)
locals {
  batch2_aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  batch2_aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  batch2_db_password           = "Batch2-TF-Scanner-Only-P@ss"
}

# MEDIUM: publicly accessible RDS, unencrypted, no backups
resource "aws_db_instance" "batch2_medium_rds" {
  identifier                   = "batch2-medium-rds"
  engine                       = "mysql"
  engine_version               = "5.7"
  instance_class               = "db.t3.micro"
  allocated_storage            = 20
  username                     = "root"
  password                     = local.batch2_db_password
  publicly_accessible          = true
  storage_encrypted            = false
  skip_final_snapshot          = true
  backup_retention_period      = 0
  deletion_protection          = false
  auto_minor_version_upgrade   = false
  multi_az                     = false

  tags = {
    Fixture  = "batch2"
    Severity = "medium"
  }
}

# MEDIUM: EC2 with public IP and open SSH
resource "aws_instance" "batch2_medium_ec2" {
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "t2.micro"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.batch2_critical_open_world.id]
  monitoring                  = false

  root_block_device {
    encrypted   = false
    volume_type = "gp2"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "optional"
    http_put_response_hop_limit = 2
  }

  user_data = <<-EOF
              #!/bin/bash
              export AWS_ACCESS_KEY_ID=${local.batch2_aws_access_key_id}
              export AWS_SECRET_ACCESS_KEY=${local.batch2_aws_secret_access_key}
              EOF

  tags = {
    Name     = "batch2-medium-ec2"
    Fixture  = "batch2"
    Severity = "medium"
  }
}

# LOW: CloudWatch log group with no retention / insecure defaults
resource "aws_cloudwatch_log_group" "batch2_low_logs" {
  name              = "/batch2/scanner-fixture"
  retention_in_days = 0

  tags = {
    Fixture  = "batch2"
    Severity = "low"
  }
}

# LOW: S3 without versioning / logging
resource "aws_s3_bucket" "batch2_low_nolog" {
  bucket = "batch2-scanner-fixture-nolog"
  acl    = "private"

  tags = {
    Fixture  = "batch2"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "batch2_low_nolog" {
  bucket = aws_s3_bucket.batch2_low_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}
