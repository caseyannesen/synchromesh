import json
import random
import telnetlib
DEBUG = True

from ..common import essentials as ess
ess.debug = DEBUG

osmobb_cfg_dir="osmocom-bb/src/host/layer23/src/mobile/"

def configure_ms(data):
    ms_temp = open(F'{osmobb_cfg_dir}default_tmp_ms.cfg').read()
    base_temp = open(F'{osmobb_cfg_dir}default_tmp_ms.cfg').read()
    if 'imsi' in data.keys():
        ms_temp.replace('{{imsi}}', data['imsi'])
        ms_temp.replace('{{imei}}', random.sample('0123456789' * 100, 4))
        ms_temp.replace('{{mcc}}', data['imsi'][:3])
        ms_temp.replace('{{mnc}}', data['imsi'][3:5])
        base_temp.replace('{{mobile_0}}', ms_temp)
        out = open(F'{osmobb_cfg_dir}default.cfg', 'w')
        out.write(base_temp)

#send sres cmd to osmobb
def send_sres_cmd(message, client):
    conn = telnetlib.Telnet("127.0.0.1", 4247)
    conn.read_until(b"OsmocomBB(mobile)>")

    command = json.loads(message)
    if command['sres']:
        conn.write(F"sres 1 {command['sres']}\n".encode())
        res = conn.read_until(b"OsmocomBB(mobile)>")
        print(res.decode())
        ess.debugprint(source="OSMOBB",message=F"TX: {res.decode()}",code=3)
        conn.close()

# command executer
def execute_message_command(command):
    pass

# handle messages from clients
async def handle_message(message, client):
    msg, topic = message.payload.decode(), message.topic
    msgg = json.loads(msg)

    if msgg['type'] == 'user':
        ess.debugprint(source="MQTT",message=F"RX: {msg!r}\nTopic: {topic!r}\n",code=3)
    elif msgg['type'] == 'cmd':
        ess.debugprint(source="MQTT",message=F"RX: {msg!r}\nTopic: {topic!r}\n",code=3)
    else:
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=0)
    ess.debugprint(source="MQTT",message=F"RX: {msg!r}\nTopic: {topic!r}\n",code=3)

# handle local websocker messages
async def handle_local_client(data=None, socket=[], client=None):
    reader, writer = socket
    try:
        if ess.is_json(data):
            data = json.loads(data)

            # code to run osmobb requests

            # code to run nitb requests

    except:
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        ess.debugprint(source="WEBSOCKET",message=F"Client disconnected.\n",code=0)

    