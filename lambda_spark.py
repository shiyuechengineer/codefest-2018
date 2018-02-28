from __future__ import print_function

import json
import requests
from meraki import meraki
#from tropo import Tropo, Session
import boto3
import re
import configparser
import login
import calendar
import time


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
        if client['phoneNumber'] == '0000005205':
            client['phoneNumber'] = '5551234567'
        all_clients[client['name']] = {'location': client['location'].replace(', USA', ''), 'mac': client['wifiMac'], 'ip': client['ip'], 'phone': client['phoneNumber'], 'id': client['id']}
    return all_clients

def urlize_mac(mac_address):
    mac_address.replace(':', '%253A')
    return 'https://n10.meraki.com/CodeFest-2018/n/up0Wrak/manage/usage/list#timespan=86400&q=' + mac_address

def spark_wifi_clients(event, message_detail):
    payload = {
        'roomId': event.get('data')['roomId'],
        'text': 'Searching on wireless clients...'
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    markdown = '**Clients found on local Wi-Fi**:\n'
    all_clients = meraki_wifi_clients()
    for client in all_clients:
        markdown += '- {0} w/ MAC [{1}]({4}) & IP {2}, connected @ {3}\n'.format(client, all_clients[client]['mac'], all_clients[client]['ip'], all_clients[client]['location'], urlize_mac(all_clients[client]['mac']))
    payload = {
        'roomId': event.get('data')['roomId'],
        'markdown': markdown
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_sm_clients(event, message_detail):
    all_clients = meraki_sm_clients()
    markdown = '**Clients found via MDM**:\n'
    for client in all_clients:
        markdown += '- {0} w/ MAC [{1}]({5}), IP {2}, & mobile # [{3}]({7}), geolocated @ [{4}]({6})\n'.format(client, all_clients[client]['mac'], all_clients[client]['ip'], all_clients[client]['phone'], all_clients[client]['location'], urlize_mac(all_clients[client]['mac']), 'https://www.google.com/maps/place/'+all_clients[client]['location'].replace(' ', '+'), 'https://n10.meraki.com/CodeFest-2018-sy/n/LqJWgck/manage/pcc/list#pn=' + all_clients[client]['id'])
    payload = {
        'roomId': event.get('data')['roomId'],
        'markdown': markdown
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_name(user_id):
    url = 'https://api.ciscospark.com/v1/people?id={0}'.format(user_id)
    response = requests.get(url, headers=spark_headers)
    return json.loads(response.text)['items'][0]['displayName']

def spark_get(event):
    url = '{0}{1}'.format(spark_url, event.get('data')['id'])
    response = requests.get(url, headers=spark_headers)
    return json.loads(response.text)

def spark_help(event, message_detail):
    payload = {
        'roomId': event.get('data')['roomId'],
        'markdown': '''Welcome to the Job Corps security response system. You can *mention me* & ask for:\n
- **help** - prints this menu
- **wifi** - see which clients are connected
- **mdm** - see where are MDM devices

To help students, you can do the following:\n
- **register** [your_number] - associates your cell/mobile # into database with your name
- **confirm** [student_number] [location] - responds to student that help is on the way to specified location

'''
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_post(event, message_detail):
    payload = {
        'roomId': event.get('data')['roomId'],
        'text': 'pong'
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_register_phone(event, message_detail):
    print(message_detail)
    phone_number = int(''.join(filter(str.isdigit, message_detail)))
    reg = re.compile('(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})', re.S)
    reg_results = reg.findall(str(phone_number))
    if len(reg_results) == 0 or len(reg_results[0]) != 10:
        payload = {
            'roomId': event.get('data')['roomId'],
            'text': '{0} is an invalid number and did not register successfully.'.format(message_detail)
        }
        response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
        return False
    phone_number = reg_results[0]
    dynamodb = boto3.client('dynamodb')
    name = spark_name(event['actorId'])
    dynamodb.put_item(TableName='codefest-users', Item={'Name': {'S': name}, 'Phone': {'N': phone_number}})
    number = dynamodb.get_item(TableName='codefest-users', Key={'Name': {'S': name}})['Item']['Phone']['N']
    payload = {
        'roomId': event.get('data')['roomId'],
        'text': 'Phone # ({0}) {1}-{2} registered under your name {3}!'.format(phone_number[:3], phone_number[3:6], phone_number[6:], name)
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_text_number(event, message_detail):
    message_detail.replace('confirm ', '')
    phone_number = ''
    for match in re.finditer(r"\(?\b[2-9][0-9]{2}\)?[-. ]?[2-9][0-9]{2}[-. ]?[0-9]{4}\b", message_detail):
        phone_number = match.group()
    if phone_number:
        location = message_detail.replace(phone_number, '').strip()
        phone_number = ''.join(filter(str.isdigit, phone_number))
    else:
        phone_number = message_detail.split()[0]
        location = message_detail.replace(phone_number, '').strip()
    if phone_number[0] == '+':
        pass
    elif phone_number[0] == '1':
        phone_number = '+' + phone_number
    else:
        phone_number = '+1' + phone_number
    '''
    t = Tropo()
    t.call(to=phone_number, network='SMS')
    t.say(message)
    response = requests.get(tropo_url, data=t.RenderJson())
    '''
    tropo_headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
    payload = {'token': messaging_token, 'numberToDial': phone_number, 'location': 'Help is on the way to your location @ ' + location}
    response = requests.post(tropo_url, headers=tropo_headers, data=json.dumps(payload))
    '''
    call(numberToDial, {"network":"SMS"})
    say("Help is on the way to your location @ " + location + "!")
    '''
    payload = {
        'roomId': event.get('data')['roomId'],
        'text': 'Your confirmation has been sent.'
    }
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def spark_alert_device(event, message_detail):
    config_file = 'config.ini'
    credentials = login.read_config(config_file)
    session = login.login_dashboard(credentials)[0]
    cp = configparser.ConfigParser()
    cp.read(config_file)
    url = cp.get('sm', 'url')
    # Go to the network
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko'}
    result = session.get(url, headers=headers)
    #tree = lxml.html.fromstring(result.text)
    #token = tree.xpath("//input[@name='authenticity_token']/@value")[0]
    token = login.parse(result.text, '<input name="authenticity_token" type="hidden" value="', '" />')[0]
    # Send the data to be updated
    headers['X-CSRF-Token'] = token
    headers['X-Requested-With'] = 'XMLHttpRequest'

    update_data = {
        'authenticity_token': token,
        'timeout': 60,
        '_ts': calendar.timegm(time.gmtime())*1000
    }
    result = session.post(
        url='https://n10.meraki.com/CodeFest-2018/n/LqJWgck/manage/pcc/find_device/568579452955802835',
        headers=headers,
        data=update_data
    )
    payload = {
        'roomId': event.get('data')['roomId'],
        'text': 'Alert on its way to the device. You get on your way to the victim!'
    }
    time.sleep(10)
    response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))
    return True

def register_numbers(event, context):
    for (name, phone_number) in names_numbers:
        print(name, phone_number)
        dynamodb = boto3.client('dynamodb')
        dynamodb.put_item(TableName='codefest-users', Item={'Name': {'S': name}, 'Phone': {'N': phone_number}})
        number = dynamodb.get_item(TableName='codefest-users', Key={'Name': {'S': name}})['Item']['Phone']['N']
        payload = {
            'roomId': event.get('data')['roomId'],
            'text': 'Phone # ({0}) {1}-{2} registered under name {3}!'.format(phone_number[:3], phone_number[3:6], phone_number[6:], name)
        }
        response = requests.post(spark_url, headers=spark_headers, data=json.dumps(payload))


def lambda_handler(event, context):
    print('Received event: ' + json.dumps(event, indent=2))
    message_detail = spark_get(event)
    full_command = message_detail['text'].replace(bot_name, '').strip()
    first_keyword = full_command.split()[0]
    rest_of_commands = full_command.replace(first_keyword, '').strip()
    
    bot_commands = {
        'help': lambda x, y: spark_help(x, y),
        'ping': lambda x, y: spark_post(x, y),
        'wifi': lambda x, y: spark_wifi_clients(x, y),
        'mdm': lambda x, y: spark_sm_clients(x, y),
        'register': lambda x, y: spark_register_phone(x, y),
        'confirm': lambda x, y: spark_text_number(x, y),
        'alert': lambda x, y: spark_alert_device(x, y),
        'boom!': lambda x, y: register_numbers(x, y),
    }

    if first_keyword in bot_commands:
        return bot_commands[first_keyword](event, rest_of_commands)
    else:
        return False
