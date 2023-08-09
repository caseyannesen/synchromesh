import json


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
    
async def handle_client(reader, writer):
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

    