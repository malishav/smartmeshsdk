from bottle import route, run, request
from random import randint
import json
import lakers
import requests

MANAGER_SERIAL = '/dev/tty.usbserial-142303'

R = bytes.fromhex("72cc4761dbd4c78f758931aa589d348d1ef874a7e303ede2f140dcf3e6aa4aac")
CRED_I = bytes.fromhex("A2027734322D35302D33312D46462D45462D33372D33322D333908A101A5010202412B2001215820AC75E9ECE3E50BFC8ED60399889522405C47BF16DF96660A41298CB4307F7EB62258206E5DE611388A4B8A8211334AC7D37ECB52A387D257E6DB3C2A93DF21FF3AFFC8")
CRED_R = bytes.fromhex("A2026008A101A5010202410A2001215820BBC34960526EA4D32E940CAD2A234148DDC21791A12AFBCBAC93622046DD44F02258204519E257236B2A0CE2023F0931F1F386CA7AFDA64FCDE0108C224C51EABF6072")

# dictionary that holds the different responders multiplexed according to the connection identifier C_R
sessions = {}

#============================ receive from manager ============================

@route('<path:path>', method='ANY')
def all(path):
    global responder
    message = json.loads(request.body.getvalue())
    print(message)

    if message['name']=='notifData':
        mac = message['fields']['macAddress']
        data = message['fields']['data']

        if data[0] == 0xf5:
            try:
                # create new responder
                responder = lakers.EdhocResponder(R, CRED_R)
                c_r = randint(0, 24)
                ead_1 = responder.process_message_1(data[1:])
                message_2 = responder.prepare_message_2(lakers.CredentialTransfer.ByReference, c_r, None)
                print("Message_2: {}".format(bytes(message_2).hex()))

                # save the responder into existing sessions
                sessions[c_r] = responder

                requests.post(
                    'http://127.0.0.1:8080/api/v2/raw/sendData',
                    json={'payload': message_2,
                          'manager': MANAGER_SERIAL,
                        'mac': mac },
                )
            except Exception as e:
                print(e)
        else:
            # EDHOC message 3, retrieve the responder
            try:
                c_r = data[0]
                responder = sessions[c_r]

                id_cred_i, ead_3 = responder.parse_message_3(message_3)
                valid_cred_i = lakers.credential_check_or_fetch(id_cred_i, CRED_I)
                r_prk_out = responder.verify_message_3(valid_cred_i)
                print("Handshake completed!")
                print("PRK_OUT: {}".format(r_prk_out))
            except Exception as e:
                print(e)

    else:
        # periodic health reports sent by the device, ignore
        pass

run(host='localhost', port=1880, quiet=True)
