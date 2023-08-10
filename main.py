#!/usr/bin/env python3

'''
    This software is written as a skeleton template to run and manage a remote CHEAPRAY network.
'''
DEBUG = True


import paho.mqtt.client as mqtt
from scripts.common import essentials as ess # Essential functions common to all CHEAPRAY software
ess.debug = DEBUG


from scripts.nitb import nitbman as nib # Functions to manage the remote CHEAPRAY network
from scripts.osmobb import osmobbman as obm # Functions to manage the remote CHEAPRAY cloner
import subprocess, os
import asyncio
import json



DEFAULT_CLIENT_ID = "osmobb"
CLIENTS = ['nitb', 'osmobb']
CLIENTS.remove(DEFAULT_CLIENT_ID)

DEFAULTS = {
    #LOCAL WEBSOCKET SERVER SETTINGS
    "websocket_server": {
            'address': 'localhost',
            'port': 8888,
            'id': DEFAULT_CLIENT_ID, # Replace with your desired client_id ('nitb', 'osmobb', etc.)
        },

    # MQTT BROKER SETTINGS
    "broker" : {
            'address':'3a4f7d6b0cd1473681d6c9bdfa569318.s2.eu.hivemq.cloud',
            'mqtt_port':8883, 'ws_port':8884, 'use_websockets':False,
            'username':'onverantwoordelik', 'password':'asdf8090ABC!!',
            'subscription': DEFAULT_CLIENT_ID, 'publish_to': CLIENTS, # Replace with your desired publish ('nitb', 'osmobb', etc.)
            'timeout':3600
        },

    # DNS SETTINGS
    "access_code": "RjJlWWhsUjZPbXpNaW1CVWNLUXNJb0luOjIxNzUyMTI5",

    "message": {'type':'cmd', 'message':'', 'is_res': False, 'is_json': False, 'origin': DEFAULT_CLIENT_ID}
}


######### Define callback functions#######

# Disconnect callback function
def on_disconnect(client, userdata, rc):
    pass

# Connect callback function (subscribes and notifies connection)
def on_connect(client, userdata, flags, rc):
    ess.debugprint(source="MQTT",message=F"Connection result: {rc}",code=1)
    if rc == 0:
        ess.debugprint(source="MQTT",message="Connected to MQTT broker",code=1)
        client.subscribe(DEFAULTS['broker']['subscription'])  # Replace with the desired topic to subscribe to
        message = DEFAULTS['message']
        message['message'] = 'connected'
        for pub in DEFAULTS['broker']['publish_to']:
            client.publish(pub, json.dumps(message))
            ess.debugprint(source="MQTT",message=F"Sent {message} to {pub}",code=ess.SUCCESS)
    else:
        ess.debugprint(source="MQTT",message="Connection failed",code=ess.INFO)


def on_message(client, userdata, message):
    msg, topic = message.payload.decode(), message.topic

    ess.debugprint(source="MQTT",message=F"RX: {msg!r}\nTopic: {topic!r}\n",code=ess.INFO)

    if 'user' in msg and ess.is_json(msg) and topic == DEFAULT_CLIENT_ID:
        mst = json.loads(msg)
        if mst['type'] == 'user_cmd':
            mst['type'] = 'user_res'
            mst['is_res'] = True
            pub_to = mst['origin']
            mst['message'] =  ess.execute_command(mst['message'])
            print(mst)
            mst['origin'] = DEFAULT_CLIENT_ID
            client.publish(pub_to, json.dumps(mst))
        elif mst['type'] == 'user_res' and 'telnet' in conns:
            asyncio.run(ess.send_to_sock(conns['telnet'], mst['message']['stdout']))

    elif topic == 'osmobb':
        asyncio.run(obm.handle_message(msg, client))
    elif topic == 'nitb':
        asyncio.run(nib.handle_message(msg, client))
    else:
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=0)

async def send_cmd(data, client):
    global conns
    message = DEFAULTS['message']
    message['type'] = 'user_cmd'
    message['message'] = data
    message['is_json'] = ess.is_json(data)
    message['origin'] = DEFAULT_CLIENT_ID
    for pub in DEFAULTS['broker']['publish_to']:
        client.publish(pub, json.dumps(message))
        ess.debugprint(source="WEBSOCKET",message=F"Sent {message} to {pub}",code=5)


# local websocket client handler
async def handle_client(reader, writer):
    socket = [reader, writer]
    global client
    global conns
    
    while True:
        data = await reader.readuntil(b"\n")
        if not data:
            break

        try:
            data = data.decode('ascii').strip()
        except:
            try:
                data = data.decode('ascii').strip()
            except:
                ess.debugprint(source="WEBSOCKET",message=F'Received Invalid data',code=ess.WARNING)
                break

        ess.debugprint(source="WEBSOCKET",message=F'client sent {data}',code=ess.INFO)

        if 'activate-telnet' in data:
            conns['telnet'] = socket
            ess.debugprint(source="WEBSOCKET",message=F"Telnet activated",code=ess.SUCCESS)
            continue

        if not ess.is_json(data) and 'telnet' in conns.keys():
            for pub in DEFAULTS['broker']['publish_to']:
                dat = {'type':'user_cmd', 'message':data, 'is_res': False, 'is_json': True, 'origin': DEFAULT_CLIENT_ID}
                client.publish(pub, json.dumps(dat))
                ess.debugprint(source="TELNET",message=F"Sent {dat} to {pub}",code=ess.INFO)
            continue
        elif not ess.is_json(data):
            writer.write(F"Invalid command have you activated telnet? ''activate-telnet'\n".encode())
            ess.debugprint(source="TELNET",message=F"NO TELNET IDENTIFIED",code=ess.WARNING)
            await writer.drain()
            continue

        if DEFAULT_CLIENT_ID == 'osmobb':
            await obm.handle_local_client(data=data, socket=socket, client=client)
        elif DEFAULT_CLIENT_ID == 'nitb':
            await nib.handle_local_client(data=data, socket=socket, client=client)
        else:
            ess.debugprint(source="WEBSOCKET",message=F"Unhandled\n",code=ess.DEBUG)
        

# mqtt loop
async def run_mqtt(client):
    res = await loop.run_in_executor(None, client.loop_forever)
    return res


# main application
async def main():

    #run remote system
    global client
    global conns
    global debug

    conns = {}
    debug = True

    #configure MQTT
    broker = DEFAULTS['broker']
    broker['on_disconnect'], broker['on_connect'], broker['on_message'] = on_disconnect, on_connect, on_message
    client = await ess.get_client(**broker)


    #configure local websocket server
    websocket_server = DEFAULTS['websocket_server']
    websocket_server['handle_client'] = handle_client
    
    tasks = [ess.run_local_sock_server(**websocket_server), run_mqtt(client)]

    if DEFAULT_CLIENT_ID == 'nitb':
        tasks.append(ess.update_dns_task())
        ess.debugprint(source="WEBSERVER",message=F"Starting DNS updater",code=ess.INFO)
    ##create tasks
    
    await asyncio.gather(*tasks)
    

if __name__ == '__main__':
    if not os.geteuid() == 0:
        print("Run as root!")
        exit(1)

    if DEFAULT_CLIENT_ID == 'nitb':
        freq, governor = ['1.4GHz','conservative']
        #enable rt kernel priority 
        subprocess.call("sysctl -w kernel.sched_rt_runtime_us=-1", shell=True, stdout=subprocess.DEVNULL)
        #set cpu freq max to 1.3GHz and governor to conservative.
        subprocess.call(F"cpupower frequency-set -g {governor}", shell=True, stdout=subprocess.DEVNULL)
        subprocess.call(F"cpupower frequency-set -u {freq}", shell=True, stdout=subprocess.DEVNULL)
        ess.debugprint(source="CPU SET",message=F"Frequency-max @ 1.4GHz 'conservative' cores [0-3]",code=ess.INFO)
    else:
        ess.debugprint(source="CPU SET",message=F"Skipping frequency setter",code=ess.INFO)

    
    loop = asyncio.get_event_loop()
    try:
        # Run the main function that includes the async tasks
        loop.run_until_complete(main())
    finally:
        # Close the event loop at the end
        loop.close()
    