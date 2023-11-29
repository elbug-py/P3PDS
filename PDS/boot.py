# boot.py -- run on boot-up
import network
import machine

WIFI_SSID = 'wifi-campus'
WIFI_PASSWORD = 'uandes2200'

SERVER = 'b691d2e8433d49499db17af66c771b55.s1.eu.hivemq.cloud'
CLIENT_ID = 'BICHOTA_CAJON'




# Connect to wifi

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if not wlan.isconnected():
    print('Connecting to network...')
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while not wlan.isconnected():
        pass

    print('Connection successful')
    print('Network config:', wlan.ifconfig())


# Load AWS certificates



SSL_PARAMS = {"server_hostname":"b691d2e8433d49499db17af66c771b55.s1.eu.hivemq.cloud"}


