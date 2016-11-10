#!/opt/python3.4.4/bin/python3

import time
import hashlib
import random as r
import json
import re
import os
import sys
import logging

# CONFIG
PORT = 5000
RETURN_GPS = True
MAX_MESSAGE_LENGTH = 1024
LOGFOLDER = '/home/pi/obd/logs/'

id_counter = 0
STIME = time.time()

log = logging.getLogger('server.common')


def generate_session_id():
    return hashlib.md5(str(int(time.time())).encode()).hexdigest()


def simulate_ecu_data():
    global id_counter
    data = {}
    data['RPM'] = r.randrange(0, 8500)
    data['VOLTAGE'] = float('%.2f' % r.uniform(10.3, 14.0))
    data['TPS'] = r.randrange(0, 160)
    data['ECT'] = r.randrange(15, 105)  # engine coolant temp
    data['MAP'] = r.randrange(30, 89)
    data['IAT'] = r.randrange(0, 40)  # intake air temp
    data['SPEED'] = r.randrange(0, 186)
    data['INJ'] = r.randrange(0, 999)
    data['GEAR'] = r.randrange(0, 6)
    data['TMP'] = float('%.2f' % r.uniform(-5.0, 36.4))
    data['PWM'] = r.randrange(0, 100)
    data['ID'] = id_counter
    id_counter += 1
    return json.dumps(data)


def write_to_log(fh, data):
    data['time'] = time.time() - STIME  # calculate time since start
    fh.write(json.dumps(data) + '\n')  # write to file


def debug_obd_data(data):

    log.debug("RPM: %s", data['RPM'])
    log.debug("TPS: %s", data['TPS'])
    log.debug("ECT: %s", data['ECT'])
    log.debug("IAT: %s", data['IAT'])
    log.debug("MAP: %s", data['MAP'])
    log.debug("VOLTAGE: %.1f", data['VOLTAGE'])
    log.debug("SPEED: %s", data['SPEED'])
    log.debug("INJ: %s", data['INJ'])
    log.debug("GEAR: %s", data['GEAR'])


# detect if the code is running on a pi and what version
def pi_version():
    # Check /proc/cpuinfo for the Hardware field value.
    # 2708 is pi 1
    # 2709 is pi 2
    # Anything else is not a pi.
    with open('/proc/cpuinfo', 'r') as infile:
        cpuinfo = infile.read()
    # Match a line like 'Hardware   : BCM2709'
    match = re.search('^Hardware\s+:\s+(\w+)$', cpuinfo,
                      flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        # Couldn't find the hardware, assume it isn't a pi.
        return None
    if match.group(1) == 'BCM2708':
        # Pi 1
        return 1
    elif match.group(1) == 'BCM2709':
        # Pi 2
        return 2
    else:
        # Something else, not a pi.
        return None


def check_path(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def signal_handler(signal, frame):
    print('Server stops now')
    sys.exit(0)
