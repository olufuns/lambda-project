output "api_base_url" {
  description = "Base URL of the public HTTP API"
  value       = aws_apigatewayv2_api.notes.api_endpoint
}

output "notes_url" {
  description = "CRUD endpoint; use this URL in the curl examples"
  value       = "${aws_apigatewayv2_api.notes.api_endpoint}/notes"
}

output "health_url" {
  description = "Health-check endpoint"
  value       = "${aws_apigatewayv2_api.notes.api_endpoint}/health"
}

output "lambda_function_name" {
  value = aws_lambda_function.notes.function_name
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.notes.name
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.lambda.name
}
