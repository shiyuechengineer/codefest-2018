from __future__ import print_function

import json
import requests
from meraki import meraki
from tropo import Tropo, Session
import boto3
from boto3.dynamodb.conditions import Key, Attr


def meraki_wifi_clients():
    all_clients = {}
    for ten_minutes in range(1, 7):
        for ap_name in aps:
            ap_clients = meraki.getclients(api_key, aps[ap_name], timestamp=ten_minutes*10*60)
            for client in ap_clients:
                name = client['description']
                if name not in all_clients:
                    all_clients[name] = {'location': ap_name, 'mac': client['mac'], 'ip': client['ip'], 'last_seen': ten_minutes*10}
    return all_clients

def meraki_sm_clients():
    all_clients = {}
    for client in meraki.getsmdevices(api_key, net_id, fields=['ip', 'location', 'phoneNumber'])['devices']:
        all_clients[client['name']] = {'location': client['location'].replace(', USA', ''), 'mac': client['wifiMac'], 'ip': client['ip'], 'phone': client['phoneNumber']}
    return all_clients


def lambda_handler(event, context):
    print(event)
    if 'initialText' in event['session'] and 'help' in event['session']['initialText'].lower():
        phone_number = event['session']['from']['id'][1:]
        payload = {
            'roomId': spark_room,
            'markdown': 'Help requested by **({0}) {1}-{2}**'.format(phone_number[:3], phone_number[3:6], phone_number[6:])
        }
        response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))

        dynamodb = boto3.client('dynamodb')
        name = dynamodb.get_item(TableName='codefest-students', Key={'Phone': {'N': phone_number}})['Item']['Name']['S']
        payload = {
            'roomId': spark_room,
            'markdown': 'Phone number matched to **{0}**'.format(name)
        }
        response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))

        clients = meraki_wifi_clients()
        if name.replace(' ', '.') in clients:
            client = clients[name.replace(' ', '.')]
            payload = {
                'roomId': spark_room,
                'markdown': '_{0}_ was connected within last **{1} minutes** on Wi-Fi @ **{2}**'.format(name, client['last_seen'], client['location'])
            }
            response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))

        clients = meraki_sm_clients()
        if name.replace(' ', '.') in clients:
            client = clients[name.replace(' ', '.')]
            payload = {
                'roomId': spark_room,
                'markdown': '_GPS data_ currently located for this device @ **{0}**'.format(client['location'])
            }
            response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('codefest-users')

        response = table.scan()
        #FilterExpression=Attr('Phone').gt(29)
        items = response['Items']
        for item in items:
            outbound_number = str(item['Phone'])
            tropo_headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
            payload = {'token': messaging_token2, 'numberToDial': outbound_number, 'location': 'Help requested by {0}, phone number {1}, in location {2}'.format(name, phone_number, client['location'])}
            response = requests.post(tropo_url2, headers=tropo_headers, data=json.dumps(payload))

    return True
