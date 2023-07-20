import boto3
import json

def lambda_handler(event, context):
    bucket_name = ""
    object_key = "config.json"

    session = boto3.Session()
    s3_client = session.client('s3')

    # Retrieve the configuration file from the S3 bucket
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    config_data = json.loads(response['Body'].read().decode('utf-8'))

    # Update tags for EC2 instances
    if 'ec2' in config_data['resources']:
        ec2_resources = config_data['resources']['ec2']
        ec2_client = session.client('ec2')
        for resource in ec2_resources:
            resource_id = resource['resource_id']
            tags = resource['tags']
            tags_list = [{'Key': key, 'Value': value} for key, value in tags.items()]
            try:
                #ec2_client.create_tags(Resources=[resource_id], Tags=tags_list)
                print(f"Tags updated for EC2 instance with ID: {resource_id}, {tags_list}")
            except Exception as e:
                print(f"Error updating tags for EC2 instance with ID: {resource_id}")
                print(str(e))

    # Update tags for S3 buckets
    if 's3' in config_data['resources']:
        s3_resources = config_data['resources']['s3']
        s3_client = session.client('s3')
        for resource in s3_resources:
            resource_id = resource['resource_id']
            tags = resource['tags']
            tags_list = [{'Key': key, 'Value': value} for key, value in tags.items()]
            try:
                #s3_client.put_bucket_tagging(Bucket=resource_id, Tagging={'TagSet': tags_list})
                print(f"Tags updated for S3 bucket with ID: {resource_id} {tags_list}")
            except Exception as e:
                print(f"Error updating tags for S3 bucket with ID: {resource_id}")
                print(str(e))
