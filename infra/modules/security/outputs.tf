output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "ec2_security_group_id" {
  description = "ID of the EC2 security group"
  value       = aws_security_group.ec2.id
}

output "lambda_security_group_id" {
  description = "ID of the Lambda security group"
  value       = aws_security_group.lambda.id
}

output "opensearch_security_group_id" {
  description = "ID of the OpenSearch security group"
  value       = aws_security_group.opensearch.id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

output "security_group_map" {
  description = "Map of all security group IDs"
  value = {
    alb        = aws_security_group.alb.id
    ec2        = aws_security_group.ec2.id
    lambda     = aws_security_group.lambda.id
    opensearch = aws_security_group.opensearch.id
    rds        = aws_security_group.rds.id
  }
}