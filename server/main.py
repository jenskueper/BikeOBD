#!/opt/python3.4.4/bin/python3.4

import time
import json
import logging
import threading
import common as c
import svr
import signal
import os

# settings
LOG_FOLDER = 'logs'
ERROR_LOGFILE = 'bikeobd.error.log'
DATA_LOGFILE = 'bikeobd.trip.log'
SVR_IP = '0.0.0.0'

err_counter = 0

if __name__ == '__main__':
    signal.signal(signal.SIGINT, c.signal_handler)

    log = logging.getLogger('server')
    log.setLevel(logging.WARNING)

    # make sure log folder exists
    c.check_path(LOG_FOLDER)

    # creat file handler which write the logs to the sd card
    fh = logging.FileHandler(os.path.join(LOG_FOLDER, ERROR_LOGFILE))
    fh.setLevel(logging.INFO)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # create formatter and add it to the handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add handler to the logger
    log.addHandler(fh)
    log.addHandler(ch)

    # make it easier to read the log file
    log.info('----------------------------')

    host = svr.Host((SVR_IP, c.PORT))  # start socket server

    # server needs to run in a seperate thread since timing is important for
    # serial communication
    log.info('Starting asyncore loop as thread')
    loop_thread = threading.Thread(target=svr.asyncore.loop, kwargs=dict(
        timeout=0.01), name="Asyncore Loop")
    loop_thread.daemon = True
    loop_thread.start()

    log.debug('Creating data log file')
    # todo correct filename
    datafile = open(os.path.join(LOG_FOLDER, DATA_LOGFILE), 'a')

    if c.pi_version() is not None:  # running on a pi
        import obd
        import heatedgrips
        log.info('Seting up DLC communication')
        obd = obd.Obd()

        heatedgrips = heatedgrips.Heatedgrips(obd)

        log.info('Entering main loop')
        i = 7

        # check if the current errorcount is below the threshold
        while err_counter < obd.ERRORMAX or True:

            # delay to reduce the amout of data and to prevent the ECU from
            # dropping out
            time.sleep(obd.TIMEUPDATE)

            # request table 11 data from the ECU
            response = obd.serial_write(
                obd.gen_table_request(17, 0, 20), False)
            # table 209 (D4?) start 0, end 1, pos 5  81 -> neutral/clutch, 80
            # gear, 83 kickstand

            if response == "":  # no valid response from the ecu
                err_counter += 1
            else:
                err_counter = 0
                data = response.split()
                obd.data['RPM'] = int(data[5], 16) * 256 + \
                    int(data[6], 16)  # rpm
                obd.data['TPS'] = int(data[8], 16)  # tps
                obd.data['ECT'] = int(data[10], 16) - 40  # ect
                obd.data['IAT'] = int(data[12], 16) - 40  # iat
                obd.data['MAP'] = int(data[14], 16)  # map
                obd.data['VOLTAGE'] = float(
                    int(data[17], 16)) / 10  # battery voltage
                obd.data['SPEED'] = int(data[18], 16)  # speed
                obd.data['INJ'] = int(data[19], 16) * 256 + \
                    int(data[20], 16)  # inj
                obd.data['ID'] = c.id_counter

                if(heatedgrips):
                    obd.data['INJ'] = int(heatedgrips.get_temperature() * 100)
                    obd.data['MAP'] = round(float(heatedgrips.get_pwm()) * 100)

                """os.system('cls')
                for (i, d) in enumerate(data):
                    print("Pos: "+str(i)+" Data: "+str(d))"""

                c.id_counter += 1

                # gear calculation gear

                if obd.data['SPEED'] > 5:
                    # only calculate for higher speeds
                    # because low speed calculations are inaccurate
                    obd.calculate_gear()
                else:
                    obd.data['GEAR'] = 0  # neutral

                # check if data is available
                # check if there is a significant change
                if len(obd.data) > 0 and obd.is_important():

                    # only broadcast if there are clients to receive the msg
                    if len(host.remote_clients) > 0:
                        host.broadcast(json.dumps(obd.data) +
                                       '\n')  # send the msg

                    # write it to the log file
                    c.write_to_log(datafile, obd.data)

                # c.debug_obd_data(obd.data)

    else:  # running on something else --> going into test mode
        while 1:
            if len(host.remote_clients) > 0:
                host.broadcast(c.simulate_ecu_data() + '\n')
            time.sleep(1)

host.close()  # close socket server
datafile.close()  # close file
