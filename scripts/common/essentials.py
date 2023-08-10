import paho.mqtt.client as mqtt
import urllib.request as request
import subprocess
import inspect
import aiohttp
import asyncio
import json

# Global variables
debug = False
ESCAPE = '\033[9'
I, S, D, W, E, C = [F"{ESCAPE}{i}m" for i in (4, 2, 5, 3, 1, 7)]
COLORS = [I, S, D, W, E, C]
INFO, SUCCESS, DEBUG, WARNING, ERROR, CRITICAL,  = list(range(0,6))
DEBUG_NAMES = ['INFO', 'SUCESS', 'DEBUG', 'WARNING', 'ERROR', 'CRITICAL']


def is_json(data):
    try:
        json.loads(data)
    except:
        return False
    return True


#prints debug messages
def debugprint(source="NONE",message="", code=0):
    if code >= 6:
        code = 5
    if debug:
        frame = inspect.stack()[1]
        filename = frame.filename.split('/')[-1]
        lineno = inspect.getframeinfo(frame[0]).lineno
        func = inspect.getframeinfo(frame[0]).function
        DATA = F"{COLORS[code]}\033[4m{DEBUG_NAMES[code]} {filename}:{lineno}\033[0m {COLORS[code]}>"
        print(F"{DATA} {source}({func!r}) : \033[1m{message!r}\033[0m")

# return the public IP address of the device
async def check_ip(debug=False):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://api.ipify.org?format=json') as response:
                data = await response.text()
                data = json.loads(data)['ip']
                debugprint(source="CHECK_IP",message=F"YOUR IP IS: {data!r}",code=INFO)
                return data
        except:
            debugprint(source="CHECK_IP",message=F"GETTING IP FAILED",code=WARNING)  
            return "failed"

# update dns regularly
async def update_dns_task(access_code='RjJlWWhsUjZPbXpNaW1CVWNLUXNJb0luOjIxNzUyMTI5',refresh=300,retry=30,debug=False):
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(F'https://freedns.afraid.org/dynamic/update.php?{access_code}') as res:
                    debugprint(source="UPDATE_DNS",message=await res.text(),code=INFO)
                    await asyncio.sleep(refresh)
            except:
                debugprint(source="UPDATE_DNS",message="Failed trying agin in 30s",code=DEBUG)
                await asyncio.sleep(retry)

# Run a single return command and return its output
def execute_command(command="") -> dict:
    res = {
        'command': '', 'returncode': '',
        'stdout': '', 'stderr': '',
        'is_run': False, 'is_failed': False
    }


    res["command"] = command
    res['is_run'] = True

    if command == 'get ip':
        res['stdout'] = asyncio.run(check_ip())
        res['returncode'] = 0
    elif command and not is_json(command):
        try:
            output = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            res['returncode'] = output.returncode
            res['stdout'] = output.stdout.strip()
            res['stderr'] = output.stderr.strip()
            res['is_failed'] = False
        except Exception as e:
            res['is_failed'] = True
            res['stderr'] = f"Error executing command: {e}"
        

    return res

# send data to a socket from anywhere
# call using asyncio.run when calling from a non async 
async def send_to_sock(sock, message, is_telnet=False):
    try:
        reader, writer = sock
        writer.write(F"{message}\n$ ".encode())
        await writer.drain()
        debugprint(source=F"WEBSOCKET/{'TELNET' if is_telnet else ''}",message=F"Sent {message} via websocket",code=INFO)
    except:
        debugprint(source=F"WEBSOCKET/{'TELNET' if is_telnet else ''}",message=F"Sent {message} via websocket",code=WARNING)

# Creates an mqtt client and connects to the broker
async def get_client(address="",mqtt_port="",ws_port="",use_websockets=False,timeout="",username="",password="",
                     subscription="",publish_to="",on_connect=None,on_message=None,on_disconnect=None):
    # Create a client instance
    client = mqtt.Client(client_id=subscription)  # Replace with your desired client_id

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
                client.connect(address, ws_port, keepalive=timeout)
                debugprint(source="MQTT",message="connected via websockets",code=1)
            else:
                # Connect to the MQTT broker using SSL/TLS
                client.tls_set()
                client.connect(address, mqtt_port, keepalive=timeout)
                debugprint(source="MQTT",message=F"connected via SSL/TLS as {subscription!r},  listening for {subscription!r} messages",code=1)
            break
        except KeyboardInterrupt:
            # Disconnect and stop the network loop when manually interrupted
            client.disconnect()
            debugprint(source="MQTT",message="Connection Failed!",code=0)
    return client

# async webserver function to start websocket server
async def run_local_sock_server(address="",port="",id="",handle_client=None, **kwargs):
    if not (address and port and handle_client):
        debugprint(source="WEBSERVER",message="NO valid addr, port or handle_client",code=ERROR)
        return False
    
    global ussd_sessions
    ussd_sessions = {}
    server = await asyncio.start_server(handle_client, address, port)
    debugprint(source="WEBSERVER",message=F"WebSocket server started and listening on {address}:{port}",code=SUCCESS)
    
    try:
        await server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        await server.wait_closed()
        debugprint(source="WEBSERVER",message="WebSocket server stopped",code=0)

