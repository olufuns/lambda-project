resource "aws_dynamodb_table" "notes" {
  name         = "${var.project_name}-notes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "noteId"

  attribute {
    name = "noteId"
    type = "S"
  }
}
