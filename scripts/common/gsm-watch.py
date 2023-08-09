#!/usr/bin/env python3

import subprocess
import time
import json
# Run the command and capture its output
arfcns = {}
time_max_start = time.time()
times = []
lasttime = elapsed = 0
index = 0
gains = [30,50,100,200]
ppms = [35, 34, 33, 36]
confs = [(x,y) for x in gains for y in ppms]
for gain, ppm in confs:
    index += 1 
    start = time.time()
    print(F"ARFCNS = {' '.join(arfcns.keys())!r}\nScanning GSM900 with gain {gain} and ppm {ppm} {round(index+1 / 4 *100, 2)}% Step: {index}/3 last_took: {round(lasttime)}, elapsed: {round(elapsed)}")
    output = subprocess.check_output(F"kal -s GSM900 -g {gain} -e {ppm}", shell=True, stderr=subprocess.PIPE)
    o = output.decode('utf-8').split('\n')
    o = [x.strip().lower().split() for x in o if 'chan:' in x]
    o = [(x[1], x[2].replace('(', "").replace("mhz", ""), x[4].replace(")", ""), x[6]) for x in o]

    
    for a in o:
        if a[2][-3] == 'k':
            dev = float(a[2][:-3]) * 1000
        else:
            dev = float(a[2][:-2])
        if str(a[0]) not in arfcns:
            arfcns[a[0]] ={'freq': float(a[1]), 'dev': dev, 'pwr': float(a[3])}
        else:
            #make averages
            arfcns[a[0]]['freq'] = (arfcns[a[0]]['freq'] + float(a[1])) / 2
            arfcns[a[0]]['dev'] = (arfcns[a[0]]['dev'] + dev) / 2
            arfcns[a[0]]['pwr'] = (arfcns[a[0]]['pwr'] + float(a[3])) / 2
    lasttime = round(time.time() - start)
    elapsed += lasttime
    with open('arfcns.json', 'w') as file:
        file.write(json.dumps(arfcns))
    

