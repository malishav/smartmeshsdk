from bottle import route, run, request
from random import randint
import paho.mqtt.client as mqtt
import json
import lakers
import requests
import sys

if len(sys.argv) == 2:
    MANAGER_SERIAL = sys.argv[1]
else:
    MANAGER_SERIAL = '/dev/tty.usbserial-144303'

TOPIC = "aiotacademy"

R = bytes.fromhex("72cc4761dbd4c78f758931aa589d348d1ef874a7e303ede2f140dcf3e6aa4aac")
CRED_I = bytes.fromhex("A2027734322D35302D33312D46462D45462D33372D33322D333908A101A5010202412B2001215820AC75E9ECE3E50BFC8ED60399889522405C47BF16DF96660A41298CB4307F7EB62258206E5DE611388A4B8A8211334AC7D37ECB52A387D257E6DB3C2A93DF21FF3AFFC8")
CRED_R = bytes.fromhex("A2026008A101A5010202410A2001215820BBC34960526EA4D32E940CAD2A234148DDC21791A12AFBCBAC93622046DD44F02258204519E257236B2A0CE2023F0931F1F386CA7AFDA64FCDE0108C224C51EABF6072")

# dictionary that holds the different responders multiplexed according to the connection identifier C_R
ongoing_sessions = {}
authorized_motes = {}

#============================ receive from manager ============================

@route('<path:path>', method='ANY')
def all(path):
    global mqtt_client
    message = json.loads(request.body.getvalue())

    if message['name']=='notifData':
        mac = message['fields']['macAddress']
        data = message['fields']['data']
        if is_edhoc_message_1(data):
            handle_edhoc_message_1(mac, data)
        elif is_edhoc_message_3(data):
            handle_edhoc_message_3(mac, data)
        else: # check if mote is authorized, if so publish on MQTT
            if mac in authorized_motes.keys():
                try:
                    print("Mote {} published: {}".format(mac, ''.join(chr(x) for x in data)))
                except:
                    print("Mote {} published: {}".format(mac, data))
                mqtt_client.publish(TOPIC, payload=json.dumps(data))
            else:
                print("Unauthorized message from {}".format(mac))
    else:
        # periodic health reports sent by the device, ignore
        pass

def handle_edhoc_message_1(mac, message_1):
    try:
        print("Message 1 from {} received".format(mac))
        # create new responder
        responder = lakers.EdhocResponder(R, CRED_R)
        c_r = bytes([randint(0, 24)])
        ead_1 = responder.process_message_1(message_1[1:])
        message_2 = responder.prepare_message_2(lakers.CredentialTransfer.ByReference, c_r, None)
        # save the responder into existing sessions
        ongoing_sessions[c_r] = responder

        requests.post(
            'http://127.0.0.1:8080/api/v2/raw/sendData',
            json={'payload': list(message_2),
            'manager': MANAGER_SERIAL,
            'mac': mac },
        )
    except Exception as e:
        print("Exception in message_1 handling from {}. Exception: {}".format(mac, e))

def handle_edhoc_message_3(mac, message_3):
    # EDHOC message 3, retrieve the responder
    try:
        print("Message 3 from {} received".format(mac))
        c_r = bytes([message_3[0]])
        responder = ongoing_sessions[c_r]

        id_cred_i, ead_3 = responder.parse_message_3(message_3[1:])
        valid_cred_i = lakers.credential_check_or_fetch(id_cred_i, CRED_I)
        r_prk_out = responder.verify_message_3(valid_cred_i)
        print("Handshake with {} completed. PRK_OUT: {}".format(mac, ' '.join(hex(x) for x in r_prk_out)))
        ongoing_sessions.pop(c_r)
        authorized_motes[mac] = r_prk_out
    except Exception as e:
        print("Exception in message_3 handling from {}. Exception {}".format(mac, e))

# Check whether a message is an EDHOC messsage based on first byte
def is_edhoc_message(data):
    if is_edhoc_message_1(data) or is_edhoc_message_3(data):
        return True
    else:
        return False

def is_edhoc_message_1(data):
    if data[0] == 0xf5:
        return True

def is_edhoc_message_3(data):
    if bytes([data[0]]) in ongoing_sessions.keys():
        return True

#============================ connect MQTT ====================================
def mqtt_on_message(client, userdata, msg):
    pass

def mqtt_on_connect(client, userdata, flags, rc):
    print("MQTT connected")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = mqtt_on_connect
mqtt_client.on_message = mqtt_on_message
mqtt_client.connect("broker.mqttdashboard.com", 1883, 60)
mqtt_client.loop_start()

#============================ start web server =================================

run(host='localhost', port=1880, quiet=True)
