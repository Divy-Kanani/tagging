import json
import boto3
import re
import logging
import pandas as pd
from io import BytesIO

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def map_vpc_id_to_customer_name(customer_dict):
    logger.info(f"Mapping VPC IDs to customer names: {customer_dict}")
    ec2_client = boto3.client('ec2')
    vpcs = ec2_client.describe_vpcs()
    vpc_customer_dict = {}
    for vpc in vpcs['Vpcs']:
        vpc_id = vpc['VpcId']
        tags = vpc['Tags']
        customer_name = ''
        for tag in tags:
            if tag['Key'] == 'Name':
                if re.match(r'^customer-', tag['Value']):
                    vpc_num = tag['Value'][-2:]
                    try:
                        customer_name = customer_dict[int(vpc_num)]
                    except KeyError:
                        pass
        if customer_name != '':
            customer_name = customer_name.replace('"', '')
            vpc_customer_dict[vpc_id] = customer_name
    return vpc_customer_dict


def map_vpc_name_to_customer_name(file_name, vpc_column_name, customer_column_name):
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket="s3storagefileholder", Key=file_name)
    excel_data = response['Body'].read()
    df = pd.read_excel(BytesIO(excel_data))
    df[vpc_column_name] = df[vpc_column_name].replace({'68(?)': 68, '69(?)': 69, '05': 5, '00': 0})
    df[vpc_column_name] = pd.to_numeric(df[vpc_column_name], errors='coerce', downcast='integer')
    df = df.dropna(subset=[vpc_column_name])
    vpc_ids = df[vpc_column_name].astype(int).tolist()
    customers = df[customer_column_name].tolist()
    data_dict = dict(zip(vpc_ids, customers))
    return map_vpc_id_to_customer_name(data_dict)


def get_standard_tags_values():
    s3_client = boto3.client('s3')
    logger.debug('Reading tags config document...')
    response = s3_client.get_object(Bucket="s3storagefileholder", Key="tag_dict")
    tags_and_values = response['Body'].read()
    tags_and_values = tags_and_values.decode('utf-8')
    tags_and_values = json.loads(tags_and_values)
    return tags_and_values


def iterate_ec2(cust_dict, customer_config):
    ec2_client = boto3.client('ec2')
    ec2_dict = ec2_client.describe_instances()
    customer_config['ec2'] = {}

    for reservation in ec2_dict['Reservations']:
        for instance in reservation['Instances']:
            try:
                instance_id = instance['InstanceId']
                vpc_id = instance['VpcId']
                customer_value = cust_dict.get(vpc_id)
                if customer_value:
                    customer_config['ec2'][instance_id] = {'CustomerName': customer_value}
                    logger.debug(
                        f"Updating ec2 CustomerName for: instance_id={instance_id}, with: customer_value={customer_value}")
            except KeyError as e:
                logger.error('VpcID key error: %s', e)


def iterate_igw(cust_dict, customer_config):
    ec2_client = boto3.client('ec2')
    igw_dict = ec2_client.describe_internet_gateways()
    customer_config['igw'] = {}
    for igw in igw_dict['InternetGateways']:
        try:
            vpcId = igw['Attachments'][0]['VpcId']
            igw_id = igw['InternetGatewayId']
            customer_value = cust_dict[vpcId]
            customer_config['igw'][igw_id] = {'CustomerName': customer_value}
            logger.debug(f"Updating igw CustomerName for: instance_id={igw_id} with: customer_value={customer_value}")
        except KeyError as e:
            logger.error('igw key error: %s', e)


def iterate_ngw(cust_dict, customer_config):
    ec2_client = boto3.client('ec2')
    nat_string = ec2_client.describe_nat_gateways()
    customer_config['ngw'] = {}
    for ngw in nat_string['NatGateways']:
        ngw_vpcId = ngw['VpcId']
        ngwId = ngw['NatGatewayId']
        try:
            customer_value = cust_dict[ngw_vpcId]
            customer_config['ngw'][ngwId] = {'CustomerName': customer_value}
            logger.debug(f"Updating ngw CustomerName for: ngwId={ngwId} with: customer_value={customer_value}")
        except KeyError as e:
            logger.error("NGW key error: %s", e)


def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    customer_config = {}
    tags_and_values = {'EnvironmentType': ['Production', 'UT', 'Sandbox', 'Development'], 'CostCenter': ['CC3600'],
                       'Platform': ['HXP', 'CPE']}

    logger.debug(f"Tags and Values: {tags_and_values}")

    customer_name_dict = map_vpc_name_to_customer_name('CustomerName.xlsx', 'VPC', 'Customer Name')
    customer_config['default_tags'] = {'EnvironmentType': tags_and_values['EnvironmentType'][0],
                                       'CostCenter': tags_and_values['CostCenter'][0],
                                       'Platform': tags_and_values['Platform'][0]}

    logger.debug(f"Customer Name Dict: {customer_name_dict}")

    iterate_ec2(customer_name_dict, customer_config)
    iterate_ngw(customer_name_dict, customer_config)
    iterate_igw(customer_name_dict, customer_config)

    json_config = json.dumps(customer_config, indent=4)
    bucket_name = "config-divy"
    s3_key = "config.json"

    # Save the JSON data to an S3 bucket
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json_config.encode('utf-8')
    )

    logger.info(f"Saved customer_config.json to S3 bucket: {bucket_name}/{s3_key}")

    return {
        'statusCode': 200,
        'body': 'Tags updated and config file saved successfully!'
    }
