import requests
import json, os

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.DEFAULT_SSL_CIPHER_LIST += 'HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass
requests.packages.urllib3.disable_warnings()
path = "/".join(os.path.abspath(__file__).split('/')[:-2]) + "/nitb/ussds/cgrate.json"

class CGrate:

    """
     {
        "username": "0962982697",
        "password": "26261",
        "application": "543-USSD",
    }
    """
    def __init__(self, username="0962982697", password="26261", is_web=False, db=path):
        self.username = username
        self.password = password
        self.db = path
        self.headers = {
            "content-type": "application/json",
            "accept-encoding": "gzip",
            "host": "543.cgrate.co.zm:4000"
        }
        self.is_web = is_web
        self.url = "https://543.cgrate.co.zm:4000/auth/v1/login"
        
        try:
            with open(path, 'r') as file:
                data = json.loads(file.read())
                if 'token' in data.keys():
                    self.headers["cgrateauthorization"] = F"Bearer {data['token']}"
        except:
            self.login(username, password)

        if not self.test_network():
            self.login(username, password)
                    
    def login(self, username="", password=""): 
        l = self.test_network()
        if not l:
            username = self.username or "0962982697"
            password = self.password or "26261"
            
            self.payload = {
                "username": username,
                "password": password,
                "application": "543-USSD" if not self.is_web else "543-WEB",
            }
            self.response = requests.post(self.url, json=self.payload, headers=self.headers, verify=False)
            self.headers['cgrateauthorization'] = F"Bearer {json.loads(self.response.text)['accessToken']}"
            with open(self.db, 'w') as file:
                file.write(json.dumps({'token':json.loads(self.response.text)['accessToken']}))
            l = self.response.status_code == 200
        return l

    def test_network(self):
        url = "https://543.cgrate.co.zm:4000/losino/v2/find/customer/ignoresource?msisdn=0962982697"
        response = requests.get(url, headers=self.headers, verify=False)
        return response.status_code == 200

    def get_customer(self, msisdn):
        if self.test_network():
            pass
        else:
            self.login()
        url = F'https://543.cgrate.co.zm:4000/losino/v2/find/customer/ignoresource?msisdn={msisdn}'
        response = requests.get(url, headers=self.headers, verify=False)
        data = json.loads(response.text)
        if response.status_code == 200:
            return data['payload']['customer']['fullName']
        else:
            return False
        

