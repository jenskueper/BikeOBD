# BikeOBD

### Honda motorcycles
Python server that is supposed to run on a Raspberry Pi to communicate with the ECU (engine control unit) and can read the following data:
- RPM
- TPS (throttle position sensor)
- MAP-sensor (manifold absolute pressure)
- IAT (intake air temperature)
- ECT (engine coolant temperature
- speed
- battary voltage
- injection time
- gear

The Raspberry Pi talks to a FT232RL chip via USB which is connected to an MC33660 (Freescale). It also controls al relay which is able to pull the K-Line (ISO 9141-2) low.  

The project should be compatible to all Honda motorcycles which were built 2002 and later. 


Ideas for the future:
- measure acceleration (0-60mph/30-60mph...)
- draw graphs
- highlight max/ideal/critical values
- change settings (gear table, return gps etc.) on the phone for the server
- show average/min/max values on the phone

Detailed information about the curcuit: coming soon
