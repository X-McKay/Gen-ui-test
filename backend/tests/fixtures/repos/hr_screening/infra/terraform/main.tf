terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

resource "aws_ecs_cluster" "hr_screening" {
  name = "hr-screening"
}

resource "aws_db_instance" "candidates" {
  identifier        = "hr-candidates"
  engine            = "postgres"
  instance_class    = "db.t4g.medium"
  allocated_storage = 50
}
