provider "aws" {
  region = "us-east-1"
}

locals {
  function_name = "clean_amis_and_snapshots"
}

data "aws_iam_policy_document" "lambda_execution_policy" {
  statement {
    actions = [
      "ec2:DescribeImages",
      "ec2:DescribeSnapshots",
      "ec2:DeregisterImage",
      "ec2:DeleteSnapshot",
      "autoscaling:DescribeLaunchConfigurations",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

resource "aws_lambda_function" "lambda" {
  function_name = local.function_name
  filename      = "ami_cleanup.zip"
  handler       = "ami_cleanup.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda.arn
  timeout       = 90
}

resource "aws_iam_role" "lambda" {
  name = "lambda_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
        Sid    = ""
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_execution_policy" {
  name = "lambda_execution_policy"
  role = aws_iam_role.lambda.id

  policy = data.aws_iam_policy_document.lambda_execution_policy.json
}

resource "aws_cloudwatch_event_rule" "clean_ami_snapshot_cron_rule" {
  name                = "clean-ami-snapshot-cron-rule"
  description         = "Eventbridge rule to trigger lambda function for cleaning AMIs and snapshots"
  schedule_expression = "rate(7 days)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.clean_ami_snapshot_cron_rule.name
  arn       = aws_lambda_function.lambda.arn
  target_id = "clean_amis_and_snapshots_target"
}
