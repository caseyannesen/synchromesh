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
        conn.close()


async def handle_message(message, client):
    msg, topic = message.payload.decode(), message.topic
    try:
        msgg = json.loads(msg)
        if msgg['type'] == 'usr':
            if not msgg['is_res']:
                msgg['msg'] = execute_command(msgg['msg'])
                msgg['is_res'] = True
                client.publish(pub, json.dumps(msgg))
            elif msgg['is_res'] :
                if conns:
                    if 'telnet' in conns.keys():
                        #conns['telnet'][1].write(message['msg'])
                        #conns['telnet'][1].drain()
                        pass
                if type(msgg['msg']) == list:
                    print("\x1b[2J")
                    for item in msgg['msg']:
                        print(F"{item} \n")
                else:
                    print(F"{msgg['msg']}")

        elif msgg['type'] == 'cmd' and msgg['is_json']:
            handle_cmd(msgg['msg'], client)
        else:
            print(F'Unhandled: {msgg}')
    except:
        print(f"RX: {msg!r}\nTopic: {topic!r}\n")
    
async def handle_local_client(data=None, socket=[], client=None):
    reader, writer = socket
    try:
        while True:
            data = await reader.read(240)
            if not data:
                break
            
            data = data.decode().strip()
            print(F'client sent {data}')
            if 'name-me' in data:
                conns['telnet'] = [reader, writer]
            else:
                message = MESSAGE
                if 'nitb' in data or 'osmobb' in data:
                    message['type'] = 'cmd'
                    message['is_json'] = True
                else:
                    message['type'] = 'usr'
                message['msg'] = data
                client.publish(pub, json.dumps(message))
    except asyncio.CancelledError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        print("Client disconnected.")

    