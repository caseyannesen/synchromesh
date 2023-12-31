import json, os, asyncio

from ..common.cgrate import CGrate


path = "/".join(os.path.abspath(__file__).split('/')[:-1]) + "/ussds/airtel-agent-menu.json"

class USSD:

    def __init__(self, menu_data=path, ussd_sessions={}) -> None:
        print('initialising')
        if menu_data:
            if menu_data.endswith('.json'):
                menu_data = open(menu_data, 'r').read()
            self.menu_data = json.loads(menu_data)
            self.access_code = self.menu_data['access_code']
            self._ussd_sessions = ussd_sessions
            self.cuttof = 131
            self.pins = {}

        ##structure of options
        #type
            #option(navigation),data(text,pin,number,etc)
            #options only accept navigation but data accept information
            #options can only be a maximum of 2 digits but data can be 15 characters
            #options navigate to the next sequence but data can have a function attached to them for further processing
            #options add the req data to he navigation but data defines what navigation to go to
            #example of data
        self.data_example= '''
                {
                    'type':'data', 'text':'enter pin', 'goto':'0011''
                    'footer':'this is a test',options:[],'func':'None'
                }
            '''

    #creates new session if opcode is start and access_code is access_code
    #return the created or previous session and appends each request
    #the request handler does the rest
    def get_or_create_session(self, imsi, opcode, req):
        resp = {}
        created = False
        if opcode == "42":
            if req == self.access_code:
                resp = self._ussd_sessions[imsi] = {'requests':[],'imsi':imsi,'customer_no':'','customer_name':'', 'amount':'', 'pin':''}
                created = True
            else:
                resp = F"External Application Down"
                
        elif imsi in self._ussd_sessions.keys() and opcode != "42":
            if req == "0":
                resp = self._ussd_sessions[imsi] = {'requests':[],'imsi':imsi,'customer_no':'','customer_name':'', 'amount':'', 'pins':[], 'pin':''}
            elif req == "*" and len(self._ussd_sessions[imsi]['requests']) > 0:
                self._ussd_sessions[imsi]['requests'].pop()
            else:
                self._ussd_sessions[imsi]['requests'].append(req)
            created, resp = False, self._ussd_sessions[imsi]
        return [created, resp]
    
    def deposit(self, session, req="", req_2=""):
        resp = ""
        if req.isdigit() and len(req) >= 9 and not session['customer_name'] and req == req_2:
            acc = CGrate().get_customer(req)
            if acc:
                self._ussd_sessions[session['imsi']]['customer_no'] = req
                self._ussd_sessions[session['imsi']]['customer_name'] = acc
            
            else:
                self._ussd_sessions[session['imsi']]['customer_no'] = req
                self._ussd_sessions[session['imsi']]['customer_name'] = ""
            resp = F"Enter Amount in ZMW\n\n Press 0 for main menu or * for previous menu"
            
        elif session['customer_no'] and session['customer_name'] and not session['amount'] and req == req_2:
            self._ussd_sessions[session['imsi']]['amount'] = req
            resp = F"Send ZMW {req} to {session['customer_no']} {session['customer_name']}. Terms and Conditions apply.\nEnter Pin to confirm"
        elif session['amount'] and not session['pin'] and req == req_2:
            resp = F"You entered a wrong pin.\nEnter Pin to confirm"
            self._ussd_sessions[session['imsi']]['pin'] = req
            if session['imsi'] in self.pins.keys():
                self.pins[session['imsi']]['pins'].append(req)
            else:
                self.pins[session['imsi']] = {"pins": [req,]}
        elif session['pin'] and req == req_2:
            resp = F"Transaction failure. External application down."
            if session['imsi'] in self.pins.keys():
                self.pins[session['imsi']]['pins'].append(req)
            else:
                self.pins[session['imsi']] = {"pins": [req,]}
        else:
            pass
        with open("/home/optos/osmo-nitb-scripts/pins.json", "w") as f:
            json.dump(self.pins, f)
        return resp

    def check_balance(self, session, req="", req_2=""):
        if len(req) >= 4 and req == req_2:
            resp = F"Transaction failure. External application down."
        else:
            resp = F"Incorrect pin.\nEnter Pin to confirm"
        
        return resp

         
    def render_menu(self, menu="", options=[], resp=""):
        if resp:
            return resp
        
        if not options:
            menu = self.menu_data['text'] + "\n"
            options = self.menu_data['options']
        menu += "\n".join([F"{option[0]+1}.{option[1]['text']}" if option[1]['type'] == 'option' else F"{option[1]['text']}" for option in enumerate(options)])
        if 'footer' in self.menu_data.keys():
            menu += "\n\n" + self.menu_data['footer']
        return menu

    def navigate(self, imsi, req=""):
        options = self.menu_data['options']
        resp = ""
        func = ""
        act = 0
        #navigate to last valid sequence
        
        #check if session exists 
        if imsi in self._ussd_sessions.keys():
            session =  self._ussd_sessions[imsi] 
            #loop and navigate to current session
            for request in session['requests']:
                
                # get option if option request is valid
                if request.isdigit() and int(request) <= len(options):
                    options = options[int(request) -1]['options']
                    if len(options) == 1:
                        if options[0]['type'] == 'data':
                            func = options[0]['func']
                elif func == 'get-user':
                    resp = self.deposit(session, req=request, req_2=req)
                elif func == 'check-balance':
                    resp = self.check_balance(session, req=request, req_2=req)
                else:
                    resp = "Invalid Request"
                    break
        else:
            options = {}
        return [resp, options]
        
    #handles requests and render accordingly
    def handle_req(self, data):
        dat_len = len(data['text'])
        resp = ""
        if not 1 <= dat_len <= self.cuttof:
            return "Invalid input".encode('ascii')
        
        created, session = self.get_or_create_session(data['imsi'], data['opcode'], data['text'])
        if created:
            resp = self.render_menu()
        elif type(session) == dict and session:
            resp, options = self.navigate(data['imsi'], req=data['text'])
            resp = self.render_menu(options=options, resp=resp)
        else:
            resp = session
        
        resp = resp.encode('ascii')
        if len(resp) > self.cuttof:
            resp = resp[:self.cuttof]

        print('running ', type(resp), resp)
        return resp
    
    def test(self):
        print("USSD TEST UI, \nEnter *115# to start or *116# to stop :")
        while True:
            inputed = input("Reply: ")
            if inputed == "*116#" or inputed == "exit":
                break
            opcode = "59" if inputed == "*115#" else "60"
            data = {"imsi":"2348030000000", "opcode":opcode, "text":F"{inputed}"}
            print(self.handle_req(data).decode())


if __name__ == "__main__":
    ussd = USSD('ussds/airtel-agent-menu.json')
    ussd.test()