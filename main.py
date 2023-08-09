#!/usr/bin/env python3

'''
    This software is written as a skeleton template to run and manage a remote CHEAPRAY network.
'''
DEBUG = True


import paho.mqtt.client as mqtt
import scripts.common.essentials as ess # Essential functions common to all CHEAPRAY software
ess.debug = DEBUG


import scripts.nitb.nitbman as nib # Functions to manage the remote CHEAPRAY network
import scripts.osmobb.osmobbman as obm # Functions to manage the remote CHEAPRAY cloner
import subprocess, os
import asyncio
import json


DEFAULT_CLIENT_ID = "nitb"
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
def on_disconnect(client, userdata, flags, rc):
    pass

# Connect callback function (subscribes and notifies connection)
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        ess.debugprint(source="MQTT",message="Connected to MQTT broker",code=1)
        client.subscribe(DEFAULTS['broker']['subscription'])  # Replace with the desired topic to subscribe to
        message = DEFAULTS['message']
        message['message'] = 'connected'
        for pub in DEFAULTS['broker']['publish_to']:
            client.publish(pub, json.dumps(message))
    else:
        ess.debugprint(source="MQTT",message="Connection failed",code=0)

def on_message(client, userdata, message):
    msg, topic = message.payload.decode(), message.topic
    
    if topic == 'osmobb':
        asyncio.run(obm.handle_message(msg, client))
    elif topic == 'nitb':
        asyncio.run(nib.handle_message(msg, client))
    else:
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=0)

    '''
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
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=0)
    '''
    
    ess.debugprint(source="MQTT",message=F"RX: {msg!r}\nTopic: {topic!r}\n",code=3)


# local websocket client handler
async def handle_client(reader, writer):
    socket = [reader, writer]
    global client
    try:
        while True:
            data = await reader.read(240)
            if not data:
                break

            try:
                data = data.decode('ascii').strip()
            except:
                try:
                    data = data.decode('ascii').strip()
                except:
                    ess.debugprint(source="WEBSOCKET",message=F'Received Invalid data',code=0)
                    break

            ess.debugprint(source="WEBSOCKET",message=F'client sent {data}',code=2)

            if 'activate-telnet' in data:
                conns['telnet'] = socket
                
            if DEFAULT_CLIENT_ID == 'osmobb':
                await obm.handle_local_client(data=data, socket=socket, client=client)
            elif DEFAULT_CLIENT_ID == 'nitb':
                await nib.handle_local_client(data=data, socket=socket, client=client)
            else:
                ess.debugprint(source="WEBSOCKET",message=F"Unhandled\n",code=0)
    except asyncio.CancelledError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()
        ess.debugprint(source="WEBSOCKET",message=F"Client disconnected.\n",code=0)

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

    debug = True

    #configure MQTT
    broker = DEFAULTS['broker']
    broker['on_connect'], broker['on_disconnect'], broker['on_message'] = on_disconnect, on_connect, on_message
    client = await ess.get_client(**broker)


    #configure local websocket server
    websocket_server = DEFAULTS['websocket_server']
    websocket_server['handle_client'] = handle_client
    

    ##create tasks
    tasks = [ess.run_local_sock_server(**websocket_server), run_mqtt(client)]
    await asyncio.gather(*tasks)
    

if __name__ == '__main__':
    if not os.geteuid() == 0:
        print("Run as root!")
        exit(1)
    freq, governor = ['1.4GHz','conservative']
    #enable rt kernel priority 
    subprocess.call("sysctl -w kernel.sched_rt_runtime_us=-1", shell=True, stdout=subprocess.DEVNULL)

    #set cpu freq max to 1.3GHz and governor to conservative.
    subprocess.call(F"cpupower frequency-set -g {governor}", shell=True, stdout=subprocess.DEVNULL)
    subprocess.call(F"cpupower frequency-set -u {freq}", shell=True, stdout=subprocess.DEVNULL)
    ess.debugprint(source="CPU SET",message=F"Frequency-max @ 1.4GHz 'conservative' cores [0-3]",code=1)

    
    loop = asyncio.get_event_loop()
    try:
        # Run the main function that includes the async tasks
        loop.run_until_complete(main())
    finally:
        # Close the event loop at the end
        loop.close()
    