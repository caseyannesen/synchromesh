import subprocess
import os
import datetime
from . import HLR
import asyncio
import telnetlib
import json
from ..common import essentials as ess
from .ussd import USSD

ess.debug = True

DB_PATH="/var/lib/osmocom/hlr.sqlite3"
SERVICES = ["osmo-nitb.service", "osmo-trx-lms.service", "osmo-bts-trx.service"]


#handle ussd messages
async def handle_ussd(data):
    if data:
        dat_len = len(data['text'])
        resp = USSD()
        resp = resp.handle_req(data)
        ess.debugprint(source="WEBSOCKET",message=F"local client {resp!r}\n",code=6)
    else:
        resp = "Invalid input".encode('ascii')
    if dat_len > 131:
        resp = data['text'][:131]
    return resp

# check for subscribers in hlr database
async def check_users(db_path=DB_PATH,db=None):
    db_folder = "/".join(db_path.split("/")[:-1])
    resp = ""
    if os.path.exists(db_folder):
        if os.path.exists(db_path):
            db = HLR.Database(db_path)
            resp = db.get_subscribers()
    else:
        os.makedirs(db_folder)
    
    return resp

#check if sdr is connected
async def sdr_check():
    p = subprocess.Popen(['LimeUtil', '--find'], stdout=subprocess.PIPE)
    output, _ = p.communicate()
    if b"LimeSDR" in output:
        return F"[+] Found device: {output.decode()}"
    else:
        return False

#checks for any errors and returns services with errors as a list
async def check_errors(service=""):
    services = [service,] if service else SERVICES
    date = datetime.datetime.now()
    resp = []

    for service in services:
        status = subprocess.Popen(["systemctl", "status", service], stdout=subprocess.PIPE).communicate()[0]
        if not b"active (running)" in status:
            print(f"Somethigs wrong with {service}, see journalctl -b -S {date.hour}:{date.minute}:{date.second} -u {service}")
            resp.append(service)
    return resp


#checks if service is running or starting and stops it.
async def stop_services(log=False,service=""):
    services = [service,] if service else SERVICES
    resp = []
    
    for service in services:
        p = subprocess.Popen(["systemctl", "status", service], stdout=subprocess.PIPE)
        output, err = p.communicate()
        if b"Active: active" in output or b"activating (auto-restart)" in output:
            if log:
                print("[*] Stopping {service} ...")
            subprocess.call(["systemctl", "stop", service])
            resp.append(service)
    return resp

#restarts services/service and returns list of failed services
async def run(service=""):
    services = [service,] if service else SERVICES

    subprocess.call(F"systemctl restart {''.join(services, ' ')}", shell=True)
    await asyncio.sleep(10)

    return check_errors(service=service)

#configure osmocom, systemctl and asterisk
async def configure(config_path="/etc/osmocom", stop_services=True, install_services=False):
    # stopping osmocom services, if they a running
    if stop_services:
        stop_services()

    if not os.path.exists(config_path):
        os.makedirs(config_path)

    ##update configs
    app_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.call(F"cp -f {app_dir}/configs/openbsc.cfg {config_path}/osmo-nitb.cfg", shell=True)
    subprocess.call(F"cp -f {app_dir}/configs/osmo-bts.cfg {config_path}/osmo-bts-trx.cfg", shell=True)
    subprocess.call(F"cp -f {app_dir}/configs/osmo-trx.cfg {config_path}/osmo-trx-lms.cfg", shell=True)

    ##update or install services
    if install_services:
        subprocess.call(F"cp -f {app_dir}services/osmo-nitb.service /lib/systemd/system/osmo-nitb.service", shell=True)
        subprocess.call(F"cp -f {app_dir}services/osmo-trx-lms.service /lib/systemd/system/osmo-trx-lms.service", shell=True)
        subprocess.call(F"cp -f {app_dir}services/osmo-bts-trx.service /lib/systemd/system/osmo-bts-trx.service", shell=True)

    subprocess.call("sysctl -w kernel.sched_rt_runtime_us=-1", shell=True)
    subprocess.call("systemctl daemon-reload", shell=True)
    return True

#send auth command to openbsc
def send_auth_cmd(message, client):
    try:
        conn = telnetlib.Telnet("127.0.0.1", 4242)
        conn.read_until(b"OpenBSC> ")

        command = json.loads(message)
        if command['rand']:
            conn.write(F"subscriber imsi {command['imsi']} send-auth {command['rand']}\n".encode())
            res = conn.read_until(b"OpenBSC> ").decode()
            ess.debugprint(source="MQTT",message=F"TX: {res!r}\n",code=6)
            conn.close()
            return "sent auth request to subcriber" in res 
    except:
        ess.debugprint(source="MQTT",message=F"Auth Command Failed\n",code=0)
        return False
    
async def start_nib():
    #stop all services wait 5 seconds
    await stop_services()
    await asyncio.sleep(5)
    #configure, check for sdr and start all services
    await configure()
    for _ in range(3):
        sdr_checked = await sdr_check()
        if sdr_checked:
            await run()
            break
        else:
            await asyncio.sleep(4)
    await asyncio.sleep(10)
    errors = await check_errors()
    return errors

# handle messages from clients
async def handle_message(message, client):
    msgg = json.loads(message)

    if msgg['type'] == 'user':
        pass
    elif msgg['type'] == 'cmd':
        if 'rand' in msgg.keys() and msgg['rand']:
            send_auth_cmd(message, client)
    else:
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=0)


async def handle_local_client(data=None, socket=[], client=None):
    reader, writer = socket
    if ess.is_json(data):
        data = json.loads(data)
        # code to run nitb requests
        
        if data['type'] == 'cmd' and 'sres' in data.keys():
            client.publish('osmobb', json.dumps(data))
            ess.debugprint(source="WEBSOCKET",message=F"Sent {data} to osmobb",code=5)
        elif data['type'] == 'ussd':
            res = await handle_ussd(data)
            await asyncio.sleep(3)
            writer.write(res)
            await writer.drain()
        else:
            pass
        # code to run osmobb requests
       