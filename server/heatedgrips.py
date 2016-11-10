#!/opt/python3.4.4/bin/python3.4

import time
import threading
import RPi.GPIO as GPIO
from w1 import W1ThermSensor


class Heatedgrips(object):

    STARTHEATINGTIME = 220  # startuptime where the power is 100% in seconds
    STARTTEMP = 21.0
    ENDTEMP = -10.0
    DUTYCYCLE = 5  # in seconds

    first_start = 0
    pwm = 0
    start_iat = None

    def control(self):
        while 1:
            # only turn on heated grips if the engine is running
            if 'RPM' in self.obd.data and self.obd.data['RPM'] > 1000:
                if self.first_start == 0:  # running for the first time
                    if self.obd.data['ECT'] < 60:  # engine is cold
                        # prepare for 100% heat power to accelerate the process
                        self.first_start = time.time()
                        self.start_iat = self.obd.data['IAT']
                    else:
                        self.first_start = -1
                if (time.time() - self.first_start < self.STARTHEATINGTIME and
                        self.first_start > 0):
                    self.pwm = 1  # full heating for the first seconds 
                else:
                    tmp = self.sensor.get_temperature()
                    self.pwm = round(self.calculate_pwm(tmp), 2)
                GPIO.output(29, True)
                time.sleep(self.DUTYCYCLE * self.pwm)
                GPIO.output(29, False)
                time.sleep(self.DUTYCYCLE * (1 - self.pwm))

    def __init__(self, obd):
        # setting up gpio
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        # pin for mosfet which controls the heated grips
        GPIO.setup(29, GPIO.OUT)

        self.obd = obd
        try:
            self.sensor = W1ThermSensor()
        except:
            raise ValueError('Problem while connecting to the sensor')

        # start controller as thread to allow an exact pwm
        controller = threading.Thread(target=self.control,
                                      name="Heatedgrips controller")
        controller.daemon = True
        controller.start()

    def get_pwm(self):
        return self.pwm

    def get_temperature(self):
        return self.sensor.get_temperature()

    def calculate_pwm(self, temp):
        pwm = (-1.0 / (self.STARTTEMP - self.ENDTEMP)) * (temp - self.ENDTEMP) + 1.0
        if(pwm > 1):
            pwm = 1
        elif(pwm < 0):
            pwm = 0
        return pwm
