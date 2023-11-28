# main.py -- put your code here!import os
import time
import ujson
import machine
import esp32
import random
import usocket as socket
from machine import Pin, PWM  
from umqtt.simple import MQTTClient


class Servo:
    # these defaults work for the standard TowerPro SG90
    __servo_pwm_freq = 50
    __min_u10_duty = 26 - 0 # offset for correction
    __max_u10_duty = 123- 0  # offset for correction
    min_angle = 0
    max_angle = 180
    current_angle = 0.001


    def __init__(self, pin):
        self.__initialise(pin)


    def update_settings(self, servo_pwm_freq, min_u10_duty, max_u10_duty, min_angle, max_angle, pin):
        self.__servo_pwm_freq = servo_pwm_freq
        self.__min_u10_duty = min_u10_duty
        self.__max_u10_duty = max_u10_duty
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.__initialise(pin)


    def move(self, angle):
        # round to 2 decimal places, so we have a chance of reducing unwanted servo adjustments
        angle = round(angle, 2)
        # do we need to move?
        if angle == self.current_angle:
            return
        self.current_angle = angle
        # calculate the new duty cycle and move the motor
        duty_u10 = self.__angle_to_u10_duty(angle)
        self.__motor.duty(duty_u10)

    def __angle_to_u10_duty(self, angle):
        return int((angle - self.min_angle) * self.__angle_conversion_factor) + self.__min_u10_duty


    def __initialise(self, pin):
        self.current_angle = -0.001
        self.__angle_conversion_factor = (self.__max_u10_duty - self.__min_u10_duty) / (self.max_angle - self.min_angle)
        self.__motor = PWM(Pin(pin))
        self.__motor.freq(self.__servo_pwm_freq)

def mqtt_connect(client_id, endpoint, ssl_params):
    mqtt = MQTTClient(
        client_id=client_id,
        server=endpoint,
        ssl_params=ssl_params,
        port=0,
        keepalive=4000,
        ssl=True,
        user=b"M0ki1",
        password=b"1331Mati??",

    )
    print('Connecting to HiveMQ...')
    mqtt.connect()
    print('Done')
    return mqtt
      
def mqtt_publish(client, topic, message=''):
    print('Publishing message...')
    client.publish(topic, message)
    print(message)



#Asignando pines a los servos
motor1 = Servo(pin=14)
motor2 = Servo(pin=12)
motor3 = Servo(pin=27)

#Asignadno pines a los sensores infrarrojos
pin_sensor_IR_1 = machine.Pin(25, machine.Pin.IN)
pin_sensor_IR_2 = machine.Pin(32, machine.Pin.IN)
pin_sensor_IR_3 = machine.Pin(26, machine.Pin.IN)

#Asignando pines a magneticos (solo 1 para la EP2)
pin_sensor_magnetico_1 = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
pin_sensor_magnetico_2 = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_UP)
pin_sensor_magnetico_3 = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_UP)

#Ponindo los servos en 180 grados (posicion cerrado)
# motor1.move(0)
# time.sleep(0.25)
# motor2.move(0)
# time.sleep(0.25)
# motor3.move(0)
# time.sleep(0.25)
# time.sleep(3)
time.sleep(0.25)
motor1.move(120)
time.sleep(0.25)
motor2.move(120)
time.sleep(0.25)
motor3.move(120)
time.sleep(0.25)

general_states= {
    "station_id": "G1", 
    "lockers": [
    {
        "nickname": "1",
        "state": 0,
        "is_open": False,
        "is_empty": True,
    },
    {
        "nickname": "2",
        "state": 0,
        "is_open": False,
        "is_empty": True,
    },
    {
        "nickname": "3",
        "state": 0,
        "is_open": False,
        "is_empty": True,
    }
    ]
}

def leer_sensor_IR(locker_id):
    time.sleep(0.25)
    if locker_id == 1:
        estado = pin_sensor_IR_1.value()
    elif locker_id == 2:
        estado = pin_sensor_IR_2.value()
    elif locker_id == 3:
        estado = pin_sensor_IR_3.value()
    time.sleep(0.25)
    print(f"Locker {locker_id} - IR: {estado}")
    if estado == 0:
        general_states["lockers"][locker_id-1]["is_empty"] = True
        return True
    else:
        general_states["lockers"][locker_id-1]["is_empty"] = False

        return False
    
def mover_servo(locker_id, angulo):
    time.sleep(0.25)
    if locker_id == 1:
        motor1.move(angulo)
    elif locker_id == 2:
        motor2.move(angulo)
    elif locker_id == 3:
        motor3.move(angulo)
    else:
        print("ERRROR")
    time.sleep(0.25)

def verificacion_fisica():
    for i in range(1,4):
        leer_sensor_IR(i)

    estados = ujson.dumps(general_states)
    mqtt_publish(client=mqtt,message=estados,topic="g1/physical_verification")
    #ACA MANDAMOS EL ESTADO

def leer_sensor_magentico(locker_id):
    time.sleep(0.25)
    if locker_id == 1:
        estado = pin_sensor_magnetico_1.value()
    elif locker_id == 2:
        estado = pin_sensor_magnetico_2.value()
    elif locker_id == 3:
        estado = pin_sensor_magnetico_3.value()
    print(f"Locker {locker_id} - Magnetico: {estado}")
    time.sleep(0.25) 
    if estado == 0:
        general_states["lockers"][locker_id-1]["is_open"] = False
        return True
    else:
        general_states["lockers"][locker_id-1]["is_open"] = True
        return False

def esperar_cierre(locker_id):
    time.sleep(0.25)
    while True:
        lectura = leer_sensor_magentico(locker_id)
        print(f"Locker {locker_id} - Magnetico: {lectura}")
        if lectura:
            print("Puerta cerrada")
            break
        else:
            print(f"Puerta abierta")
            pass
        time.sleep(0.25)
    time.sleep(0.25)
    
def esperar_infrarrojo(locker_id, modo):
    time.sleep(0.25)
    while True:
        lectura = leer_sensor_IR(locker_id)
        print(f"Locker {locker_id} - IR: {lectura}")
        if modo == "cargar":
            if lectura:
                print("Paquete Cargado")
                general_states["lockers"][locker_id-1]["state"] = 3
                print("")
                break
            else:
                print(f"No hay nada en el locker")
                pass
        elif modo == "retirar":
            if not lectura:
                print("Paquete Retirado")
                general_states["lockers"][locker_id-1]["state"] = 0
                print("")
                break
            else:
                print(f"Hay algo en el locker")
        time.sleep(0.25)
    time.sleep(0.25)
    
def abrir_locker(locker_id, modo):
    print(f"Abriendo locker {locker_id} para {modo}")
    mover_servo(locker_id, 0)
    esperar_infrarrojo(locker_id, modo)
    esperar_cierre(locker_id)
    mover_servo(locker_id, 120)
    print(f"Locker {locker_id} cerrado") 


#ESte seria nuestro verificador de mensajes  

def mqtt_subscribe(topic,msg):
    print("LLEGO CARTAAA")
    message = ujson.loads(msg)
    print('Message received...')
    topico = topic.decode("utf-8")
    accion= (topico.split("/"))[-1]
    casillero= int(message["nickname"])
    print(message)
    if accion == "verification":
            response = verificacion_fisica()
    elif accion == "load":
        response = abrir_locker(casillero, "cargar")
    elif accion == "unload":
        response = abrir_locker(casillero, "retirar")
    elif accion == "reserve":
        incoming_state = int(message["state"])
        general_states["lockers"][casillero-1]["state"] = incoming_state
    else:
        print("ACCION NO RECONOCIDA")
    estados = ujson.dumps(general_states)

    mqtt_publish(client=mqtt,message=estados,topic="g1/physical_verification")
    
    
# MAIN
mqtt = mqtt_connect(CLIENT_ID, SERVER, SSL_PARAMS)
mqtt.set_callback(mqtt_subscribe)
mqtt.subscribe("g1/verification")
mqtt.subscribe("g1/load")
mqtt.subscribe("g1/unload")
mqtt.subscribe("g1/reserve")

#Aca tenemos que subscribirnos a los distintos topicos


while True:
    try:
        mqtt.check_msg()
    except Exception as e: 
        print(e)
        print('Unable to check for messages.')
    print("WAITING 2 SECS")
    time.sleep(2)



