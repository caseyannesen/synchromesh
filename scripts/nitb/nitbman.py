import subprocess, threading
import os, datetime, time
from .HLR import Database as DB
import asyncio, telnetlib, json
from ..common import essentials as ess
from .ussd import USSD

ess.debug = True

class NITB:

    #configures instance
    def __init__(self, client=None):
        self.client = client
        self.popi = None
        self.out_popi = False
        self.pub_msg = {"type":"user_res", "message":{"stdout":F"", 'for_monitor':True, 'for_tel':True}, "is_res":True, "is_json":False, "origin":"nitb"}
        self.DB_PATH = "/var/lib/osmocom/hlr.sqlite3"
        self.SERVICES = ["osmo-nitb.service", "osmo-trx-lms.service", "osmo-bts-trx.service"]

        #bsc instance
        self.BSC = None
        self.bsc_timeout = 60

    # return database or False
    def get_db(self, db_path=None):
        db_path = db_path if db_path else self.DB_PATH
        db_folder = "/".join(db_path.split("/")[:-1])
        if not os.path.exists(db_folder):
            os.makedirs(db_folder)
        return DB(db_path) if os.path.exists(db_path) else False
    
    def check_errors(self):
        resp = []
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Checking all services for errors"
            self.client.publish('osmobb', json.dumps(msg))
        for service in self.SERVICES:
            if self.check_error(service) != 0:
                resp.append(service)
        return resp
    
    def start_services(self, force=False):
        resp = []
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Starting all services"
            self.client.publish('osmobb', json.dumps(msg))
        for service in self.SERVICES:
            if self.start_service(service, force=force):
                resp.append(service)
        return resp

    def stop_services(self):
        resp = []
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Stopping all services"
            self.client.publish('osmobb', json.dumps(msg))
        for service in self.SERVICES:
            if self.stop_service(service):
                resp.append(service)
        return resp
    
    #checks service for error return 0 for no error, 1 for starting, 2 for other errors
    def check_error(self, service="") -> int:
        resp = 2
        if service:
            msg = self.pub_msg
            service = service if service.endswith(".service")  else service+".service"
            status = subprocess.Popen(["systemctl", "status", service], stdout=subprocess.PIPE).communicate()[0]
            status = status.decode().lower()
            if "active (running)" in status or "active: active" in status:
                resp = 0
            elif 'activating (auto-restart)' in status:
                resp = 1

            if self.client:
                if resp:
                    msg['message']['stdout'] = F" (!) Found Error with {service!r}"
                else:
                    msg['message']['stdout'] = F" (!) No Error Error with {service!r}"
                self.client.publish('osmobb', json.dumps(msg))
        return resp

    # stops a service if running, returns 0 for failure, 1 if stopped 
    def stop_service(self, service="", force=True):
        resp = 0
        if service:
            service = service if service.endswith(".service") else service+".service"
            err = self.check_error(service)
            if err == 0 or force:
                subprocess.call(["systemctl", "stop", service])
                resp = 1
                if self.client:
                    msg = self.pub_msg
                    msg['message']['stdout'] = F" (!) Stopped {service!r}"
                    self.client.publish('osmobb', json.dumps(msg))
        return resp

    # starts a service if not started, returns 0 for failure, 1 for success if force=True will restart the service and return 1
    def start_service(self, service="", force=False) -> int:
        resp = 0
        action = 'restart' if force else 'start'
        if service:
            service = service if service.endswith(".service") else service+".service"
            subprocess.call(F"systemctl {action} {service}", shell=True)
            time.sleep(1)
            resp = 1
            if self.client:
                msg = self.pub_msg
                msg['message']['stdout'] = F" (!) {action} {service!r} "
                self.client.publish('osmobb', json.dumps(msg))
        return resp
    
    @property
    def subscribers(self):
        return [dict(zip(('id', 'created', 'last_seen', 'imsi', 'name', 'extension', 'unk', 'tmsi', 'unk1', 'expires'), sub)) for sub in  self.check_subscribers()]
    
    # checks database for users returns list of users
    def check_subscribers(self, db_path=None):
        db = self.get_db(db_path=db_path)
        if db:
            resp = db.get_subscribers()
        else:
            resp = []
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Checking for subscribers in HLR"
            self.client.publish('osmobb', json.dumps(msg))
        return resp
    
    def _timebomb(self, function, timeout, *args, **kwargs):
        ess.debugprint(source="NITB",message=F"Starting timebomb for {timeout} seconds\n",code=ess.INFO)
        time.sleep(timeout)
        function(*args, **kwargs)
        ess.debugprint(source="NITB",message=F"Timebomb exploded for {function.__name__} with args={args!r} and kwargs={kwargs!r} after {timeout} seconds\n",code=ess.INFO)

    def timebomb(self, function, timeout, *args, **kwargs):
        threading.Thread(target=self._timebomb, args=(function, timeout, *args), kwargs=kwargs).start()

    # sends auth command to openbsc
    def send_auth_cmd(self, imsi, rand, id):
        self.timebomb(self.send_release_cmd, 30, imsi)
        return self.send_bsc_cmd(F"subscriber {id} {imsi} send-auth {rand}", is_enable=True)

    # sends release command to openbsc
    def send_release_cmd(self, imsi):
        return self.send_bsc_cmd(F"subscriber imsi {imsi} release", is_enable=True)

    # sends ussd command to openbsc
    def send_ussd_cmd(self, imsi, ussd):
        pass

    # sends sms command to openbsc
    def send_sms_cmd(self, imsi, sms):
        pass

    # sends silent call command to subscriber or lock subscriber
    def silent_call_cmd(self, imsi):
        return self.send_bsc_cmd(F"subscriber imsi {imsi} silent-call", is_enable=True)

    # ping subscriber
    def ping_subscriber(self, imsi):
        pass

    # expire subriber
    def expire_subscriber(self, imsi):
        pass

    # add subscriber
    def add_subscriber(self, imsi, msisdn, ki, opc, sres, auth_algo, comp128v1, comp128v2, comp128v3, milenage, ussd, sms, silent_call):
        pass

    # remove subscriber
    def remove_subscriber(self, imsi):
        pass

    # update subscriber
    def update_subscriber(self, imsi, msisdn, ki, opc, sres, auth_algo, comp128v1, comp128v2, comp128v3, milenage, ussd, sms, silent_call):
        pass

    # check for sdr
    def is_sdr_present(self, is_usb3=False):
        #find a way to shorten this code
        p = subprocess.Popen(['LimeUtil', '--find'], stdout=subprocess.PIPE)
        output, _ = p.communicate()
        output = output.decode().strip()
        resp =  b"LimeSDR" in output
        #implement usb3 checker
        return resp

    # configure bsc
    def configure_bsc(self, confs=[]):
        resp = False
        if not len(confs) == 5:
            confs = ['TEST', '001', '01', '102', '0982']
        app_dir = os.path.dirname(os.path.realpath(__file__))
        with open(app_dir+"/configs/openbsc_tmp.cfg", 'r') as tmp:
            tmpl = tmp.read()
            tmpl = tmpl.replace("{{NETWORK}}", confs[0])
            tmpl = tmpl.replace("{{MCC}}", confs[1])
            tmpl = tmpl.replace("{{MNC}}", confs[2])
            tmpl = tmpl.replace("{{ARFCN}}", confs[3])
            tmpl = tmpl.replace("{{LAC}}", confs[4])
            with open(app_dir+"/configs/openbsc.cfg", 'w') as cfg:
                cfg.write(tmpl)
                resp = True

        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Configuring BSC with {confs!r} {'successful' if resp else 'failed'}"
            self.client.publish('osmobb', json.dumps(msg))
        return resp 
        

    # configure osmocom, systemctl and asterisk
    def configure(self, config_path="/etc/osmocom", stop_servs=True, install_services=False):
        # stopping osmocom services, if they a running
        if stop_servs:
            self.stop_services()

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

    # send cmd to bsc
    def send_bsc_cmd(self, cmd, is_enable=False):
        resp = "".encode()
        try:
            if not self.BSC:
                conn = telnetlib.Telnet("127.0.0.1", 4242)
                conn.read_until(b"OpenBSC> ", self.bsc_timeout)
                self.BSC = conn

            if self.BSC:
                if is_enable:
                    self.BSC.write("enable\n".encode())
                    time.sleep(0.2)
                    self.BSC.read_until(b"OpenBSC# ", self.bsc_timeout)
                self.BSC.write(F"{cmd}\n".encode())
                time.sleep(0.2)
                resp = self.BSC.read_until(b"OpenBSC# ", self.bsc_timeout).decode()
        except:
            if self.client:
                msg = self.pub_msg
                msg['message']['stdout'] = F" (!) Error sending command to BSC ensure system is running"
                self.client.publish('osmobb', json.dumps(msg))
            resp = "".encode()

        return resp
    
    #convenience function to start and watch nitb for errors
    def start_nitb(self):
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Starting NITB"
            self.client.publish('osmobb', json.dumps(msg))

        resp = False
        if self.stop_services():
            if self.copy_configs():
                if self.check_errors():
                    if self.start_services():
                        self.start_watch_dog()
                        resp = True
        return resp
    
    def watchdog(self, *args, **kwargs):
        if self.client:
            self.client.publish('osmobb', json.dumps({"type":"user_res", "message":{"stdout":F" (!) started watchdog"}, "is_res":True, "is_json":False, "origin":"nitb"}))
        time.sleep(10)
        while not self.out_popi:
            errors = self.check_errors()
            if errors:
                self.stop_services()
                if self.client:
                    msg = self.pub_msg
                    msg['message']['stdout'] = F" (!) Error Detected in {' '.join(errors)!r}, Stopping services and exiting watchdog"
                    self.client.publish('osmobb', json.dumps(msg))
                break
            elif self.client:
                msg = self.pub_msg
                msg['message']['stdout'] = F" (!) No Errors Detected"
                self.client.publish('osmobb', json.dumps(msg))
            time.sleep(10)
        return self.stop_services()

    def start_watch_dog(self):
        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Starting Watchdog Thread"
            self.client.publish('osmobb', json.dumps(msg))
        self.popi = threading.Thread(target=self.watchdog, args=(self,))
        self.popi.start()

    def stop_watch_dog(self):
        if self.popi:
            self.out_popi = True
            self.popi.join()

        if self.client:
            msg = self.pub_msg
            msg['message']['stdout'] = F" (!) Stopped Watchdog Thread"
            self.client.publish('osmobb', json.dumps(msg))
        return self.popi

    def copy_configs(self):
        return True

    #handle ussd messages
    def handle_ussd(data):
        if data:
            resp = USSD()
            resp = resp.handle_req(data)
        else:
            resp = "Invalid input".encode('ascii')
        if len(resp) > 131:
            resp = resp[:131]
        return resp

COMMANDS = ['start bts', 'stop bts', 'restart bts', 'test bts', 'get_users', 'cfg **', 'list']

# handle messages from clients
async def handle_message(message, client):
    ess.debugprint(source="MQTT",message=F"Handling {message!r} \n",code=ess.INFO)
    msgg = json.loads(message)
    nitb = NITB(client=client)
    if msgg['type'] == 'user_act':
        
        if msgg['message'] == 'start bts':
            ess.debugprint(source="MQTT",message=F"Starting bts {'successful' if nitb.start_nitb() else 'failed'}\n",code=ess.INFO)
        elif msgg['message'] == 'stop bts':
            ess.debugprint(source="MQTT",message=F"Stopping bts {'successful' if nitb.stop_services() else 'failed'}\n",code=ess.INFO)
        elif msgg['message'] == 'restart bts':
            ess.debugprint(source="MQTT",message=F"Restarting bts {'successful' if nitb.start_services(force=True) else 'failed'}\n",code=ess.INFO)
        elif msgg['message'] == 'test bts':
            ess.debugprint(source="MQTT",message=F"Testing bts {'successful' if nitb.check_errors() else 'failed'}\n",code=ess.INFO)
        elif msgg['message'] == 'get_users':
            subs = nitb.subscribers()
            ess.debugprint(source="MQTT",message=F"Getting subscribers {'successful' if  subs else 'failed'}\n",code=ess.INFO)
            client.publish('osmobb', json.dumps({"type":"user_res", "message":{"stdout":F"{subs!r}"}, "is_res":True, "is_json":False, "origin":"nitb"}))
        elif msgg['message'] == 'list':
            ess.debugprint(source="MQTT",message=F"Availlable command {' ,'.join(COMMANDS)}\n",code=ess.INFO)
            client.publish('osmobb', json.dumps({"type":"user_res", "message":{"stdout":F"AVAILLABLE COMMANDS: cmd {' ,'.join(COMMANDS)!r}\n"}, "is_res":True, "is_json":False, "origin":"nitb"}))
        elif msgg['message'].startswith('auth '):
            if not len(msgg['message'].split(' ')) == 4:
                client.publish('osmobb', json.dumps({"type":"user_res", "message":{"stdout":F"Invalid input command is 'auth id ID RAND\n"}, "is_res":True, "is_json":False, "origin":"nitb"}))
            else:
                iid, imsi, rand = msgg['message'].split(' ')[1:]
                ess.debugprint(source="MQTT",message=F"Sending auth rand={rand!r}for {imsi!r}\n",code=ess.INFO)
                nitb.send_auth_cmd(imsi, rand, iid)
                client.publish('osmobb', json.dumps({"type":"user_res", "message":{"stdout":F"Send auth command\n"}, "is_res":True, "is_json":False, "origin":"nitb"}))
        elif msgg['message'].startswith('cfg '):
            ess.debugprint(source="MQTT",message=F"Configuring bts {'successful' if nitb.configure_bsc(confs=msgg['message'].split(' ')[1:]) else 'failed'}\n",code=ess.INFO)
        else:
            ess.debugprint(source="MQTT",message=F"Unhandled {msgg['message']}\n",code=ess.WARNING)
    elif msgg['type'] == 'cmd':
        if 'cmd' in msgg.keys() and msgg['cmd'] == 'auth':
            nitb.send_auth_cmd(msgg['imsi'], msgg['rand'], 'imsi')
            ess.debugprint(source="NITB",message=F"Sending auth rand={msgg['rand']!r}for {msgg['imsi']!r}\n",code=ess.INFO)
    else:
        ess.debugprint(source="MQTT",message=F"Unhandled\n",code=ess.WARNING)

    return True


async def handle_local_client(data=None, socket=[], client=None):
    reader, writer = socket
    if ess.is_json(data):
        data = json.loads(data)
        # code to run nitb requests
        
        if data['type'] == 'cmd' and 'sres' in data.keys():
            client.publish('osmobb', json.dumps(data))
            ess.debugprint(source="WEBSOCKET",message=F"Sent {data} to osmobb",code=ess.INFO)
        elif data['type'] == 'ussd':
            res = NITB.handle_ussd(data)
            writer.write(res)
            await writer.drain()
        else:
            pass
        # code to run osmobb requests
       