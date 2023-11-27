# boot.py -- run on boot-up
import network
import machine

WIFI_SSID = 'POCO X3 Pro'
WIFI_PASSWORD = 'Aa.55778'

SERVER = 'ab34c5b092fc416db7e2f21aa7d38514.s1.eu.hivemq.cloud'
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



SSL_PARAMS = {"server_hostname":"ab34c5b092fc416db7e2f21aa7d38514.s1.eu.hivemq.cloud"}


