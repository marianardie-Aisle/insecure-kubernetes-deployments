# INTENTIONAL Terraform scanner fixtures (batch 4) — Low → Critical

resource "aws_security_group" "batch4_critical_open" {
  name        = "batch4-critical-open"
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
    Fixture  = "batch4"
  })
}

resource "aws_iam_user" "batch4_critical_admin" {
  name = "batch4-critical-admin"
}

resource "aws_iam_user_policy" "batch4_critical_admin" {
  name = "batch4-critical-admin-inline"
  user = aws_iam_user.batch4_critical_admin.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

resource "aws_s3_bucket" "batch4_high_public" {
  bucket = "batch4-scanner-fixture-public"
  acl    = "public-read"

  tags = {
    Fixture  = "batch4"
    Severity = "high"
  }
}

resource "aws_s3_bucket_public_access_block" "batch4_high_public" {
  bucket = aws_s3_bucket.batch4_high_public.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

locals {
  batch4_aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  batch4_aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  batch4_db_password           = "Batch4-TF-Scanner-Only-P@ss"
}

resource "aws_db_instance" "batch4_medium_rds" {
  identifier                 = "batch4-medium-rds"
  engine                     = "mysql"
  engine_version             = "5.7"
  instance_class             = "db.t3.micro"
  allocated_storage          = 20
  username                   = "admin"
  password                   = local.batch4_db_password
  publicly_accessible        = true
  storage_encrypted          = false
  skip_final_snapshot        = true
  backup_retention_period    = 0
  deletion_protection        = false
  auto_minor_version_upgrade = false

  tags = {
    Fixture  = "batch4"
    Severity = "medium"
  }
}

resource "aws_instance" "batch4_medium_ec2" {
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "t2.micro"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.batch4_critical_open.id]
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
              export AWS_ACCESS_KEY_ID=${local.batch4_aws_access_key_id}
              export AWS_SECRET_ACCESS_KEY=${local.batch4_aws_secret_access_key}
              EOF

  tags = {
    Name     = "batch4-medium-ec2"
    Fixture  = "batch4"
    Severity = "medium"
  }
}

resource "aws_s3_bucket" "batch4_low_nolog" {
  bucket = "batch4-scanner-fixture-nolog"
  acl    = "private"

  tags = {
    Fixture  = "batch4"
    Severity = "low"
  }
}

resource "aws_s3_bucket_versioning" "batch4_low_nolog" {
  bucket = aws_s3_bucket.batch4_low_nolog.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_ebs_volume" "batch4_low_unencrypted" {
  availability_zone = "us-east-1a"
  size              = 8
  encrypted         = false

  tags = {
    Fixture  = "batch4"
    Severity = "low"
  }
}
