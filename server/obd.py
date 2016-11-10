#!/opt/python3.4.4/bin/python3.4

import serial
import time
import sys
import RPi.GPIO as GPIO
import binascii
import logging
import bisect
from statistics import mean


class Obd():

    # config
    TIMESTART = 0.5  # quiet time before starting communications
    TIMEKLOW = 0.09  # little bit longer than required cause the relay takes some time
    TIMEKHIGH = 0.2  # quiet time after low pulse before wakeup
    TIMEINIT = 0.2  # time between wakeup and initialise
    TIMEBTWMESS = 0.1  # time between messages
    TIMEWAITRX = 0.2  # time between sending a msg and listening to the response
    TIMEUPDATE = 0.1  # time between update cycles
    ERRORMAX = 2  # number of consecutive read errors that triggers a re-start
    COUNTMAX = 10  # maximum number of blank port reads per message
    CPUPAUSE = 0.02  # time between each ECU request
    #  GEARTABLE = [162, 103, 76, 64, 56, 51]  # rpm per kph plus 5% for CBR500R
    MIN_UPDATE_TIME = 3  # minimal refresh rate

    # messages and expected response lengths
    WAKEUP = 'FE 04 FF FF'  # no response expected
    WAKEUPLEN = 0
    INITIALISE = '72 05 00 F0 99'  # initialise communications
    INITLEN = 4
    REQTABLE11 = '72 07 72 11 00 14 F0'  # request table 11 data
    TABLE11LEN = 26  # length in decimal
    REQTABLE10 = '72 07 72 10 00 11 F4'
    TABLE10LEN = 6

    # approx message cycle time
    TIMEDELTA = TIMEWAITRX + TABLE10LEN * CPUPAUSE + TIMEUPDATE
    ERRORCOUNT = 0

    data = {}
    old_speed = 0
    geartable = []
    last_update = time.time()

    log = logging.getLogger('server.obd')

    # handshake with the ECU
    def __init__(self):
        self.log.info("Starting setup")

        # gear calc
        self.geartable = []
        self.last_values = []
        self.error_counter = 0

        # setting up gpio
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        # pin for relay to pull the k-line low
        GPIO.setup(40, GPIO.OUT)

        self.ser0 = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=38400,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            dsrdtr=None,
            rtscts=None
        )

        self.log.info("Kline high ")
        time.sleep(self.TIMESTART)
        self.log.info("Kline pulse")
        GPIO.output(40, True)
        time.sleep(self.TIMEKLOW)
        GPIO.output(40, False)
        time.sleep(self.TIMEKHIGH)

        # send wakeup (no response expected)
        self.serial_write(self.WAKEUP, True)
        time.sleep(self.TIMEINIT)

        # response = self.serial_write(self.INITIALISE, True)  # send initialise (expects response)
        # if response == "":
        #    sys.exit(1)  # if init fails exit with error code 1

    def flush_rx(self):  # clear RX Port
        while self.ser0.inWaiting() > 0:
            self.log.debug('in the flushing loop')
            CLEAR = self.ser0.read(self.ser0.inWaiting())  # clear buffer
            CLEAR = binascii.hexlify(CLEAR).upper()
            CLEAR = ' '.join([CLEAR[i:i + 2] for i in range(0, len(CLEAR), 2)])
            self.log.info("Cleared port: " + CLEAR)
            time.sleep(self.CPUPAUSE)
        self.ser0.flushOutput()

        return

    def dec_to_hex(self, dec):
        return ' ' + format(dec, 'x').upper().zfill(2)

    def calculate_checksum(self, msg):
        A = msg.split()  # convert to list
        C = 0
        for i in A:
            C = C + int(i, 16)
        return 256 - C % 256

    def gen_table_request(self, table, start, end):
        d = '72 07 72' + self.dec_to_hex(table) + self.dec_to_hex(start)
        + self.dec_to_hex(end)

        return d + self.dec_to_hex(self.calculate_checksum(d))

    # writes a message to the serial port, and returns the response
    def serial_write(self, msg, init):
        self.flush_rx()
        error = False
        prepared_msg = binascii.unhexlify(msg.replace(" ", ""))
        self.ser0.write(prepared_msg)
        response = ""
        counter = 0
        time.sleep(self.TIMEWAITRX)
        length = 0
        while len(response) < 1024 and not init:  # len(prepared_msg) + length:
            if self.ser0.inWaiting() > 0:
                response += self.ser0.read(1)
                if(len(response) == len(prepared_msg) + 2):
                    length = int(binascii.hexlify(response[len(prepared_msg) +
                                 1:len(prepared_msg) + 2]), 16)
                if(len(response) == len(prepared_msg) + length and length != 0):
                    break
            else:
                counter += 1
                time.sleep(self.CPUPAUSE)  # takes the CPU load down a bit
                if counter == self.COUNTMAX:  # stops continuous cycling
                    self.log.warning("Maximal serial_write error count reached")
                    break
        self.log.info("Count: %s", counter)

        # parse the response
        response = binascii.hexlify(response).upper()
        response = ' '.join([response[i:i + 2] for i in range(0, len(response), 2)])

        if response == "":
            self.log.error("Sent %s but received no echo or response >", msg)
            error = True
        else:
            if response[:len(msg)] != msg:  # check first part of response
                self.log.error("Message not echoed OK. Received echo: %s", response)
                error = True
            else:
                # strip original message
                response = response.replace(msg, "")
                if response == "":
                    self.log.error("Message echoed OK but no ECU response")
                    error = True
                else:
                    response = response.lstrip()
                    if len(response) != length * 3 - 1:
                        self.log.error("Incorrect response length: %s " +
                                       "expected but %s received for msg %s ",
                                       len(response), (length * 3 - 1),
                                       response)
                        error = True
                    else:
                        # calculate checksum and compare checkdigit
                        A = response.split()  # convert to list
                        B = int(A[-1], 16)  # decimalise checkdigit
                        A.pop()  # remove checkdigit
                        C = 0
                        # todo check if check_checksum would work here too
                        for i in A:
                            C = C + int(i, 16)
                        if B != 256 - C % 256:
                            # checkdigit is bad
                            self.log.error(response + "Bad Checkdigit")
                            error = True

        if error is True:
            response = ""  # return only good responses

        self.flush_rx()
        return response

    def is_important(self):
        # if speed difference is minimal
        if(time.time() - self.last_update < self.MIN_UPDATE_TIME and
           'SPEED' in self.data and self.data['SPEED'] - self.old_speed == 0):
            return False
        else:
            self.last_update = time.time()  # update last_update timestamp
            # save the speed to compare it with the upcoming dataset
            self.old_speed = self.data['SPEED']
            return True

    def reset(self):
        self.last_values = []
        self.error_counter = 0

    def calculate_gear(self):
        if 'SPEED' in self.data:
            calc_ratio = int(round(float(self.data['RPM']) /
                             float(self.data['SPEED'])))

            if(len(self.geartable) > 0):
                for gear, ratio in enumerate(reversed(self.geartable), start=1):
                    # check if ratio exists
                    if(ratio * 1.05 > calc_ratio and ratio * 0.95 < calc_ratio):
                        self.data['GEAR'] = gear

            # no matching ratio found

            if(len(self.last_values) > 0):
                last_values_avg = mean(self.last_values)
                self.log.debug('current average is %f and current value is %i'
                               % (last_values_avg, calc_ratio))

                if(last_values_avg * 1.05 > calc_ratio and last_values_avg *
                   0.95 < calc_ratio):
                    self.log.debug('appending %i to list' % calc_ratio)
                    self.last_values.append(calc_ratio)

                    if(len(self.last_values) >= 10):
                        avg = mean(self.last_values)
                        self.reset_values()
                        bisect.insort(self.geartable, avg)  # insert new ratio
                        self.data['GEAR'] = (self.geartable[::-1].index(avg) + 1)

                else:  # increase error counter
                    self.error_counter += 1
                    self.log.debug('increasing error counter to %i'
                                   % self.error_counter)

            else:
                self.log.debug("setting %i  as new start value" % calc_ratio)
                self.last_values.append(calc_ratio)

            if(self.error_counter >= 10):
                print('ERROR COUNTER REACHED, resetting')
                self.reset_values()
                self.last_values.append(calc_ratio)
