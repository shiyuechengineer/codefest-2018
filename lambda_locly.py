from __future__ import print_function

import json
import requests
from meraki import meraki
from prettytable import PrettyTable
import boto3


def lambda_handler(event, context):
    '''
    print(event)
    return {
        'statusCode': 200,
        'body': json.dumps(event),
    }
    '''
    beacon = event['queryStringParameters']['beacon']
    print(beacon)
    #dynamodb = boto3.client('dynamodb')
    #number = dynamodb.get_item(TableName='codefest-users', Key={'Name': {'S':'Test Name'}})
    if beacon in beacons:
        location = beacons[beacon]
    else:
        location = 'somewhere'
    payload = {
        'roomId': spark_room,
        'markdown': 'Virtual emergency blue beacon received @ **{0}**'.format(location)
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return {
        'statusCode': 200,
        'body': 'Your emergency at {0} has been sent to the security team!'.format(location),
    }
    