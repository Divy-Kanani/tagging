import boto3
import json


def lambda_handler(event, context):
    bucket_name = "config-divy"
    file_key = "config.json"

    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    json_data = response['Body'].read().decode('utf-8')
    data = json.loads(json_data)

    default_tags = data.get('default_tags', {})
    ec2_data = data.get('ec2', {})
    update_tags('ec2', ec2_data, default_tags)
    igw_data = data.get('igw', {})
    update_tags('igw', igw_data, default_tags)

    ngw_data = data.get('ngw', {})
    update_tags('ngw', ngw_data, default_tags)

    return {
        'statusCode': 200,
        'body': 'Tags updated successfully!'
    }


def update_tags(resource_type, resource_data, default_tags):
    ec2_client = boto3.client('ec2')
    for resource_id, resource_tags in resource_data.items():
        all_tags = {**default_tags, **resource_tags}
        response = ec2_client.create_tags(Resources=[resource_id],
                                          Tags=[{'Key': key, 'Value': value} for key, value in all_tags.items()])
        print(f"Updated {resource_type} {resource_id} with tags: {all_tags}")
