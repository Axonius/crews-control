# Terraform Security Review: Relevant Search Keywords

To conduct a thorough security review of Terraform code, you should focus on specific keywords and patterns that are commonly associated with security configurations and best practices. Below is a list of relevant search keywords and their descriptions to help you identify potential security vulnerabilities and misconfigurations in Terraform files.

## General Security Keywords
- `resource "aws_iam_policy"`
- `resource "aws_iam_role"`
- `resource "aws_iam_user"`
- `resource "aws_iam_group"`
- `resource "aws_iam_policy_attachment"`
- `resource "aws_iam_role_policy_attachment"`
- `resource "aws_iam_user_policy_attachment"`
- `resource "aws_security_group"`
- `resource "aws_security_group_rule"`
- `resource "aws_s3_bucket_policy"`
- `resource "aws_s3_bucket_acl"`
- `resource "aws_kms_key"`
- `resource "aws_kms_alias"`
- `resource "aws_secretsmanager_secret"`
- `resource "aws_secretsmanager_secret_version"`
- `resource "aws_vpc"`
- `resource "aws_subnet"`
- `resource "aws_route_table"`
- `resource "aws_network_acl"`
- `resource "aws_network_acl_rule"`
- `resource "aws_db_instance"`

## IAM (Identity and Access Management)
- `iam`
- `policy`
- `role`
- `user`
- `group`
- `permissions`
- `policy_attachment`
- `role_policy_attachment`
- `user_policy_attachment`

## Network Security
- `security_group`
- `security_group_rule`
- `network_acl`
- `network_acl_rule`
- `vpc`
- `subnet`
- `route_table`
- `internet_gateway`
- `nat_gateway`
- `vpn`

## Data Protection
- `kms`
- `kms_key`
- `kms_alias`
- `encryption`
- `secretsmanager`
- `secret`
- `s3`
- `s3_bucket`
- `s3_bucket_policy`
- `s3_bucket_acl`
- `s3_bucket_public_access_block`

## Other Relevant Keywords
- `logging`
- `cloudtrail`
- `cloudwatch`
- `config`
- `monitoring`
- `inspector`
- `guardduty`
- `shield`
- `waf`
- `firewall`

## Example Search Queries
You can use the following example queries:

- Search for IAM policies:
    ```
    resource "aws_iam_policy"
    ```

- Search for security groups:
    ```
    resource "aws_security_group"
    ```

- Search for S3 bucket policies:
    ```
    resource "aws_s3_bucket_policy"
    ```

- Search for KMS keys:
    ```
    resource "aws_kms_key"
    ```
    

