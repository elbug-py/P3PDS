from fastapi import FastAPI, HTTPException, Depends,BackgroundTasks, Request
import requests
import models
from database import engine, SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Annotated
import json
from itertools import permutations
from enum import Enum
import random
import string
import os
from send_email import send_email_async
from datetime import datetime, timedelta
from fastapi_mqtt.fastmqtt import FastMQTT
from fastapi_mqtt.config import MQTTConfig
import json
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="sacc/templates")
MQTT = False


def generar_clave_alfanumerica(longitud=12):
    """
    Genera una clave alfanumérica aleatoria.

    Args:
    - longitud (int): Longitud de la clave. Por defecto, 12.

    Returns:
    - str: Clave alfanumérica generada.
    """
    caracteres = string.ascii_letters + string.digits  # Letras (mayúsculas y minúsculas) y dígitos
    clave_generada = ''.join(random.choice(caracteres) for _ in range(longitud))
    return clave_generada

locker_state = {
    "stations": [
        {
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
        },
        {
            "station_id": "G3",
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
    ]
}


def get_comparisson_locker_state(virtual_locker_state, pyhsical_locker_state):
    if str(virtual_locker_state) == str(pyhsical_locker_state):
        return "STATUS OK"
    else:
        return "STATUS WITH DIFFERENCES"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def load_initial_data(db: Session):
    # Verificar si la tabla Station está vacía
    if not db.query(models.Station).count():
        # Si está vacía, cargar datos
        db_station = models.Station(address="G1", id=1)
        db.add(db_station)
        # db_station = models.Station(address="G3", id=2)
        # db.add(db_station)
        # db_station = models.Station(address="G5", id=3)
        # db.add(db_station)
        db.commit()

    # Verificar si la tabla Locker está vacía
    if not db.query(models.Locker).count():
        # Si está vacía, cargar datos
        db_locker = models.Locker(state=0, height=20, width=40, depth=20, station_id=1, id=1, personal_id=1)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=30, width=40, depth=20, station_id=1, id=2, personal_id=2)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=40, width=40, depth=20, station_id=1, id=3, personal_id=3)
        db.add(db_locker)
        db.commit()
        
        # db_locker = models.Locker(state=0, height=20, width=50, depth=25, station_id=2, id=4, personal_id=1)
        # db.add(db_locker)
        # db_locker = models.Locker(state=0, height=20, width=60, depth=25, station_id=2, id=5, personal_id=2)
        # db.add(db_locker)
        # db_locker = models.Locker(state=0, height=20, width=30, depth=25, station_id=2, id=6, personal_id=3)
        # db.add(db_locker)
        # db.commit()
        # db_locker = models.Locker(state=0, height=30, width=30, depth=30, station_id=3, id=7, personal_id=1)
        # db.add(db_locker)
        # db_locker = models.Locker(state=0, height=30, width=40, depth=30, station_id=3, id=8, personal_id=2)
        # db.add(db_locker)
        # db_locker = models.Locker(state=0, height=20, width=50, depth=30, station_id=3, id=9, personal_id=3)
        # db.add(db_locker)
        # db.commit()
        
    if not db.query(models.User).count():
        db_user = models.User(name="operario1", token=generar_clave_alfanumerica())
        db.add(db_user)
        db_user = models.User(name="operario2", token=generar_clave_alfanumerica())
        db.add(db_user)
        db_user = models.User(name="cliente1", token=generar_clave_alfanumerica())
        db.add(db_user)
        db_user = models.User(name="cliente2", token=generar_clave_alfanumerica())
        db.add(db_user)
        db.commit()

    if not db.query(models.States).count():
        lockers = db.query(models.Locker).all()
        for locker in lockers:
            db_state = models.States(locker_id=locker.id, state=locker.state)
            db.add(db_state)
        db.commit()
    
    
dp_dependecy = Annotated[Session, Depends(get_db)]
rellenar = True
if rellenar:
    load_initial_data(db=SessionLocal())

timeout_seconds = 10

def create_record(db: Session, reservation_id: int, user_id: int, locker_id: int, station_id: int, fecha: datetime, order_id: int, accion: str, email: str = None):
    if email is not None:
        db_historial = models.Historial(reservation_id=reservation_id, user_id=user_id, locker_id=locker_id, station_id=station_id, fecha=fecha, order_id=order_id, accion=accion, email=email)
    else:
        db_historial = models.Historial(reservation_id=reservation_id, user_id=user_id, locker_id=locker_id, station_id=station_id, fecha=fecha, order_id=order_id, accion=accion)
    db.add(db_historial)
    db.commit()

def get_locker_from_global_states(personal_id: int, station_name: str, locker_state=locker_state):
    for station in locker_state["stations"]:
        if station["station_id"] == station_name:
            for locker in station["lockers"]:
                if locker["nickname"] == str(personal_id):
                    return locker["state"]
    return None

def get_all_locker_from_station(db: Session, station_id: int):
    sql_query = text(f"SELECT * FROM locker WHERE station_id = {station_id}")
    result = db.execute(sql_query)
    return result.fetchall()

def all_stations(db: Session):
    sql_query = text(f"SELECT * FROM station")
    result = db.execute(sql_query)
    return result.fetchall()

def all_lockers(db: Session):
    sql_query = text(f"SELECT * FROM locker")
    result = db.execute(sql_query)
    return result.fetchall()

def get_locker_by_station_and_personal_id(db: Session, station_id: int, personal_id: int):
    sql_query = text(f"SELECT * FROM locker WHERE station_id = {station_id} AND personal_id = {personal_id}")
    result = db.execute(sql_query)
    return result.fetchone()[0]

def all_users(db: Session):
    sql_query = text(f"SELECT * FROM user")
    result = db.execute(sql_query)
    return result.fetchall()

def get_locker_personal_id(db: Session, locker_id: int):
    sql_query = text(f"SELECT * FROM locker WHERE id = {locker_id}")
    result = db.execute(sql_query)
    return result.fetchone()[1]

def locker_and_station_by_reservation_id(db: Session, reservation_id: int):
    sql_query = text(f"SELECT * FROM locker WHERE id = (SELECT locker_id FROM 'order' WHERE id = (SELECT order_id FROM reservation WHERE id = {reservation_id}))")
    result = db.execute(sql_query)
    return result.fetchone()

def station_by_locker_id(db: Session, locker_id: int):
    sql_query = text(f"SELECT * FROM station WHERE id = (SELECT station_id FROM locker WHERE id = {locker_id})")
    result = db.execute(sql_query)
    return result.fetchone()

def calcular_volumen(tupla):
    alto, ancho, profundo = tupla[3], tupla[4], tupla[5]
    return alto * ancho * profundo

def encontrar_locker_mas_pequeno(alto_paquete, ancho_paquete, profundidad_paquete, lockers):
    lockers_ordenados = sorted(lockers, key=calcular_volumen)
    for i in lockers_ordenados:
        if alto_paquete <= i[3] and ancho_paquete <= i[4] and profundidad_paquete <= i[5]:
            return i
    return None

def revisar_reservas_expiradas(db: Session, max_hours: int = 24):
    sql_query = text(f"SELECT * FROM reservation WHERE estado = 'activa'")
    result = db.execute(sql_query)
    reservas = result.fetchall()
    for reserva in reservas:
        if datetime.now() - reserva[6] > timedelta(hours=max_hours):
            create_record(db, reserva[0], reserva[1], reserva[3], reserva[5], datetime.now(), reserva[2], "Reserva expirada, estado cambia a cancelada")
            sql_query = text(f"UPDATE reservation SET estado = 'cancelada' WHERE id = {reserva[0]}")
            db.execute(sql_query)
            db.commit()
            sql_query = text(f"SELECT * FROM locker WHERE id = {reserva[3]}")
            result = db.execute(sql_query)
            locker_obtenido = result.fetchone()
            if locker_obtenido[2] == 1:
                sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker_obtenido[0]}")
                db.execute(sql_query)
                db.commit()
                sql_query = text(f"UPDATE locker SET code = NULL WHERE id = {locker_obtenido[0]}")
                db.execute(sql_query)
                db.commit()
    

app = FastAPI()
if MQTT:

    mqtt_config = MQTTConfig(
        host="b691d2e8433d49499db17af66c771b55.s1.eu.hivemq.cloud",
        port=8883,
        ssl=True,
        keepalive=60,
        username="MQTTeam",
        password="AWShaters123",
    )
    mqtt = FastMQTT(config=mqtt_config)
    mqtt.init_app(app)

estados_generales = {
    0: "available",
    1: "reserved",
    2: "loading",
    3: "used",
    4: "unloading"
}

def get_state_by_state_number(state_number, estados_generales=estados_generales):
    return estados_generales[state_number]
    

if MQTT:
    @mqtt.on_connect()
    def connect(client, flags, rc, properties):
        mqtt.client.subscribe("/mqtt") #subscribing mqtt topic
        print("Connected: ", client, flags, rc, properties)

    @mqtt.on_message()
    async def message(client, topic, payload, qos, properties):
        print("Received message: ",topic, payload.decode(), qos, properties)
        return 0
    #TODO change this in function of the actual topic

    #! CHECK WHEN CHANGING THE TOPIC SUBSCRIBING TO ADAPT THE NEW MULTI STATION
    @mqtt.subscribe("status")
    async def message_to_topic(client, topic, payload, qos, properties):
        print("Received message to specific topic: ", topic, payload.decode(), qos, properties)
        print(payload.decode())
        global locker_state
        # locker_state = json.loads(payload.decode())
        # print(json.loads(payload.decode()))

    @mqtt.on_disconnect()
    def disconnect(client, packet, exc=None):
        print("Disconnected")

    @mqtt.on_subscribe()
    def subscribe(client, mid, qos, properties):
        print("subscribed", client, mid, qos, properties)


# del pdf es la 1
@app.get("/stations",tags=['GET STATIONS'])
async def get_available_lockers(db: dp_dependecy):
    try:
        try:
            revisar_reservas_expiradas(db)
            lockers = all_lockers(db)
            data = {}
            for i in lockers:
                if i[2] == 0:
                    if i[7] not in data:
                        data[i[7]] = {i[1]: ("available", f"{i[3]}x{i[4]}x{i[5]}")}
                    else:
                        data[i[7]][i[1]] = ("available", f"{i[3]}x{i[4]}x{i[5]}")
            for i in all_stations(SessionLocal()):
                if i[0] not in data:
                    data[i[1]] = "No hay casilleros disponibles"
                else:
                    data[i[1]] = data.pop(i[0])
            return {"content": data}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}

# del pdf es la 2
@app.post('/reserve', tags=['RESERVAR'])
async def reservar(alto_paquete: int, ancho_paquete: int, profundidad_paquete: int, client_email: str,token :str, db: dp_dependecy):
    try:
        try:
            sql_query = text('SELECT * FROM "user" WHERE token = :token')
            result = db.execute(sql_query, {'token': token})
            print(result)
            e_commerce = result.fetchone()

            if (e_commerce) == None:
                return {"message": "Token no valido"}
            print(e_commerce)

            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM locker WHERE state = 0")
            result = db.execute(sql_query)
            lockers = result.fetchall()
            if len(lockers) == 0:
                return {"message": "Failed to reserve, no available lockers"}
            #REMOVE this doesn't go anymore.
            # sql_query = text(f'SELECT * FROM "user" WHERE id = {user_id}')
            # result = db.execute(sql_query)
            # user = result.fetchone()
            # if user is None:
            #     return {"message": "Failed to reserve, user does not exist"}
            #REMOVE


            locker_encontrado = encontrar_locker_mas_pequeno(alto_paquete, ancho_paquete, profundidad_paquete, lockers)
            if locker_encontrado is None:
                return {"message": "Failed to reserve, package is too big for available lockers"}
            else:
                # Creo una orden ficticia, porque debería exisitr una orden de antes
                db_order = models.Order(name="order ficitica", width=ancho_paquete, height=alto_paquete, depth=profundidad_paquete)
                db.add(db_order)
                db.commit()
                # Reservo el locker cambiando el estado
                sql_query = text(f"UPDATE locker SET state = 1 WHERE id = {locker_encontrado[0]}")
                db.execute(sql_query)
                db.commit()
                # Creo la reserva
                db_reservation = models.Reservation(client_email=client_email, 
                                                    order_id=db_order.id, 
                                                    locker_id=locker_encontrado[0], 
                                                    locker_personal_id=get_locker_personal_id(db, locker_encontrado[0]), 
                                                    station_id=station_by_locker_id(db, locker_encontrado[0])[0], 
                                                    fecha=datetime.now(), 
                                                    estado="activa",
                                                    user_id=e_commerce[0])
                db.add(db_reservation)
                db.commit()
                # asigno un codigo al locker
                clave = generar_clave_alfanumerica()
                sql_query = text(f"UPDATE locker SET code = '{clave}' WHERE locker.id = {locker_encontrado[0]}")
                db.execute(sql_query)
                db.commit()
                # añadir el cambio de estado a la tabla states
                sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker_encontrado[0]}, 1)")
                db.execute(sql_query)
                db.commit()
                sql_query = text(f'SELECT * FROM "locker" WHERE id = {locker_encontrado[0]}')
                result = db.execute(sql_query)
                locker_personal = result.fetchone()
                #!This may broke for the client_email change in reserve, keep an eye in it

                create_record(db, db_reservation.id, e_commerce[0], locker_encontrado[0], station_by_locker_id(db, locker_encontrado[0])[0], datetime.now(), db_order.id, "creacion reserva",client_email)
                
                #TODO change this to be in order with the MQTT group standars
                #TODO agree?
                
                #TODO Check what the heck is doing the others with this
                if MQTT:
                    # mqtt.publish("g1/reserve", {"nickname":f"{locker_personal[1]}","state":"1"}) #publishing mqtt topic
                    # print("QUE TA PASANDO")
                    # mqtt.publish("g1/verification", {"nickname":""}) #publishing mqtt topic
                    pass

                return {"message": "Reservation successful", "locker_id": locker_encontrado[0], "station_id": station_by_locker_id(db, locker_encontrado[0])[0], "code": clave}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    
# pdf parte 3
@app.post('/confirm_reservation', tags=['CONFIRM RESERVATION'])
async def confirm_reservation(reservation: int,token:str, db: dp_dependecy):
    try:
        try:
            sql_query = text('SELECT * FROM "user" WHERE token = :token')
            result = db.execute(sql_query, {'token': token})
            print(result)
            e_commerce = result.fetchone()

            if (e_commerce) == None:
                return {"message": "Token no valido"}
            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm reservation, reservation does not exist"}
            else:
                #get time from reservation and compare with current time
                time_reserved = reserva[6]
                time_now = datetime.now()
                time_difference = time_now - time_reserved
                sql_query = text(f"SELECT * FROM locker WHERE id = {reserva[3]}")
                result = db.execute(sql_query)
                locker_obtenido = result.fetchone()
              
                if locker_obtenido[2] == 1:
                    #*THIS IS GOOD, THIS IS WHEN EVERYTHING GOES RIGTH
                    #!This may broke for the client_email change in reserve, keep an eye in it
                    create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], "reserva confirmada",reserva[1])
                    
                    #TODO va a entregar y el mqtt cambiar el estado del cajon especifico a reservado
                    
                    # if MQTT:
                    #     #*Always check the status so this is not going to be used
                    #     mqtt.publish("g1/verification", {"nickname":""}) #publishing mqtt topic


                    return {"message": f"Time passed since reservation: {time_difference}"}
                else:
                    #!This may broke for the client_email change in reserve, keep an eye in it
                    create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], "No se logro reservar",reserva[1])

                    #TODO Check what the heck is doing the others with this
                    
                    if MQTT:
                        pass
                        # mqtt.publish("g1/reserve", {"nickname":locker_obtenido[1],"state":0}) #publishing mqtt topic
                    
                    return {"message": f"Failed to confirm reservation, locker is not reserved, it is {estados_generales[locker_obtenido[2]]} "}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    
# del pdf es la 4
@app.post('/cancel_reservation', tags=['CANCEL RESERVATION'])
async def cancel_reservation(reservation: int,token:str, db: dp_dependecy): #TODO NUMERO DE CAJON
    try:
        try:
            sql_query = text('SELECT * FROM "user" WHERE token = :token')
            result = db.execute(sql_query, {'token': token})
            print(result)
            e_commerce = result.fetchone()

            if (e_commerce) == None:
                return {"message": "Token no valido"}
            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to cancel reservation, reservation does not exist"}
            else:
                sql_query = text(f"SELECT * FROM locker WHERE id = {reserva[3]}")
                result = db.execute(sql_query)
                locker_obtenido = result.fetchone()
                if locker_obtenido[2] == 1:
                    sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker_obtenido[0]}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE locker SET code = NULL WHERE id = {locker_obtenido[0]}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE reservation SET estado = 'cancelada' WHERE reservation.id = {reservation}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker_obtenido[0]}, 0)")
                    db.execute(sql_query)
                    db.commit()
                    create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], "cancelacion reserva",reserva[1])
                    #TODO Cambiar cajon a disponible con el mqtt
                    if MQTT:
                        #!Its seems that we are gonna delete this
                        # #TODO change this into the agreement
                        # mqtt.publish("g1/reserve", {"nickname":locker_obtenido[1],"state":0}) #publishing mqtt topic
                        # mqtt.publish("g1/verification", {"nickname":""}) #publishing mqtt topic
                        pass





                    return {"message": "Reservation canceled successfully"}
                else:
                    return {"message": f"Failed to cancel reservation, locker is not reserved, it is {estados_generales[locker_obtenido[2]]} "}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}

# del pdf es la 5
@app.post('/reservation_state', tags=['RESERVATION STATE'])
async def reservation_state(reservation: int, token:str ,db: dp_dependecy):
    data = []
    try:
        try:
            sql_query = text('SELECT * FROM "user" WHERE token = :token')
            result = db.execute(sql_query, {'token': token})
            print(result)
            e_commerce = result.fetchone()

            if (e_commerce) == None:
                return {"message": "Token no valido"}
            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            locker_id = result.fetchone()[3]
            if locker_id is None:
                return {"message": "Failed to get reservation state, reservation does not exist"}
            else:
                sql_query = text(f"SELECT * FROM states WHERE locker_id = {locker_id}")
                result = db.execute(sql_query)
                states = result.fetchall()
                

                for state in states:
                    data.append({"locker_id": state[1], "state": estados_generales[state[2]]})
                
                actual_state = data[-1]["state"]
                message = [f"Current Locker state {reservation} is {actual_state}"]
                for state in data[:-1]:
                    message.append(f"Past Locker state {state['locker_id']} was {state['state']}")
                return {"content": message}
                
            
        except Exception as e:
            return {"message": f"Error: {e}"} 
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    
# 6 del pdf
@app.post('/confirm', tags=['CONFIRM'])
async def confirm(height: int, width: int, depth: int, reservation: int, operator_email: str,token:str, db: dp_dependecy):
    try:
        try:
            sql_query = text('SELECT * FROM "user" WHERE token = :token')
            result = db.execute(sql_query, {'token': token})
            print(result)
            e_commerce = result.fetchone()

            if (e_commerce) == None:
                return {"message": "Token no valido"}
            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[3]}')
                result = db.execute(sql_query)
                locker = result.fetchone()
                if locker is None:
                    return {"message": "Failed to confirm, locker does not exist"}
                else:
                    #compare the dimensions of the package with the dimensions of the locker
                    if height <= locker[3] and width <= locker[4] and depth <= locker[5]:

                        create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], "Medidas y reserva confirmadas",reserva[1])
                        create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], f"Correo enviado al operario{operator_email}",reserva[1])

                        print(locker)
                        await send_email_async('Entregar Product',f'{operator_email}',
                                f"Debes entregar en la Estacion G1 en el espacio {locker[1]} el paquete con reservacion {reservation} con el codigo: {locker[6]}")
                        return {"message": "Package confirmed"}
                    else:
                        sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker[0]}")
                        #TODO mandar mqtt para cambiar el estado del locker a disponible
                        if MQTT:
                            #TODO change this in function of the agreement
                            #!So aparently we are going to delte this
                            # mqtt.publish("g1/reserve", {"nickname":locker[1],"state":0}) #publishing mqtt topic
                            pass
                        
                        db.execute(sql_query)
                        db.commit()
                        sql_query = text(f"UPDATE reservation SET estado = 'cancelada' WHERE reservation.id = {reservation}")
                        db.execute(sql_query)
                        db.commit()
                        sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker[0]}, 0)")
                        db.execute(sql_query)
                        db.commit()
                        sql_query = text(f"SELECT * FROM locker WHERE state = 0")
                        result = db.execute(sql_query)
                        lockers = result.fetchall()
                        if len(lockers) == 0:
                            return {"message": "Failed to reserve, no available lockers"}
                        locker = encontrar_locker_mas_pequeno(height,width,depth,lockers)
                        if locker is None:
                            return {"message": "Failed to confirm, no available lockers"}
                        else:
                            sql_query = text(f"UPDATE locker SET state = 1 WHERE id = {locker[0]}")
                            db.execute(sql_query)
                            db.commit()
                            sql_query = text(f"UPDATE reservation SET locker_id = {locker[0]}, locker_personal_id = {locker[1]}, station_id = {locker[7]} WHERE id = {reservation}")
                            db.execute(sql_query)
                            db.commit()
                            sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker[0]}, 1)")
                            db.execute(sql_query)
                            db.commit()
                            create_record(db, reserva[0], e_commerce[0], reserva[3], reserva[5], datetime.now(), reserva[2], "Reasignacion de locker por espacio, reserva sigue activa y confirmada",reserva[1])
                            if MQTT:
                                #TODO Change this to the agree stament
                                mqtt.publish("g1/reserve", {"nickname":locker[1],"state":0}) #publishing mqtt topic
                                mqtt.publish("g1/verification", {"nickname":""}) #publishing mqtt topic

                            return {"message": f"Package re-assigned to locker {locker[0]}"}

        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    





@app.post('/load', tags = ["LOAD"])
async def load(reservation: int,code: str, db: dp_dependecy):
    try:
        try:
            #Todo fetch the associated e-commerce to the reservation
            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[3]}')
                result = db.execute(sql_query)
                locker = result.fetchone()
                if locker is None:
                    return {"message": "Failed to confirm, locker does not exist"}
                else:
                    if locker[6] != code:
                        print(locker[6])
                        return {"message":"Clave incorrecta"}
                    sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker[0]}, 3)")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE locker SET state = 3 WHERE id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()
                    print(locker[6])
                    sql_query = text(f"SELECT * FROM station WHERE id = {locker[7]} ")
                    result = db.execute(sql_query)
                    station = result.fetchone()
                    if MQTT:
                        print(locker[5])
                        print('esto deberia ser el numero de la estacion pipi')
                       
                        print(station)
                        for e in station:
                            print(e)
                        #TODO Change this to the agreement, we need to get the addres of these
                        #! UNCOMMENT THIS
                        mqtt.publish("load", {"station_name":f"{station[1]}","nickname":locker[1]}) #publishing mqtt topic


                    
                    clave = generar_clave_alfanumerica()
                    sql_query = text(f"UPDATE locker SET code = '{clave}' WHERE locker.id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()
                    #TODO Change this reserva[1] should be a user/e-commerce_id and  in the end goes the email
                    create_record(db, reserva[0], reserva[8], reserva[3], reserva[5], datetime.now(), reserva[2], f"Paquete cargador en locker {reserva[4]}, estacion: {station[1]} ",reserva[1])
                    print(f"Nueva clave: ${clave}")
              
                    await send_email_async('Retirar producto',f'{reserva[1]}',
                            f"Debes retirar en la Estacion G1 en el espacio {locker[1]} el paquete con reservacion {reservation} con el codigo: {clave}")
                    if MQTT:
                        #TODO Change this to the agreement
                        # mqtt.publish("g1/verification", {"nickname":""}) #publishing mqtt topic
                        pass



                    return {"message": f"Se ha abierto el espacio {locker[1]}, la nueva clave es {clave}"}
        except Exception as E:
            return {"message": f"{E}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}


@app.post('/unload', tags = ["UNLOAD"])
async def load(reservation: int,code: str, db: dp_dependecy):
    try:
        try:
            #Todo fetch the associated e-commerce to the reservation

            revisar_reservas_expiradas(db)
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[3]}')
                result = db.execute(sql_query)
                locker = result.fetchone()
                if locker is None:
                    return {"message": "Failed to confirm, locker does not exist"}
                else:
                    if locker[6] != code:
                        print(locker[6])
                        return {"message":"Clave incorrecta"}
                    sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker[0]}, 0)")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE reservation SET estado = 'finalizada' WHERE id = {reservation}")
                    db.execute(sql_query)
                    db.commit()
                    #TODO Change this reserva[1] should be a user/e-commerce_id and  in the end goes the email

                    create_record(db, reserva[0], reserva[8], reserva[3], reserva[5], datetime.now(), reserva[2], "Paquete retirado de locker",reserva[1])
                    print(locker[6])
                    #TODO aca debo hacer la llamada MQTT para abrir el cajon
                    if MQTT:
                        #TODO change this in function of the agreement
                        sql_query = text(f"SELECT * FROM station WHERE id = {locker[7]} ")
                        result = db.execute(sql_query)
                        station = result.fetchone()
                        #TODO Change this to the agreement, we need to get the addres of these
                        #! CAMBIAR
                        mqtt.publish("unload", {"station_name":f"{station[1]}","nickname":locker[1]}) #publishing mqtt topic


                   
                    sql_query = text(f"UPDATE locker SET code = NULL WHERE locker.id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()




                    return {"message": f"Se ha abierto el espacio {locker[1]}"}
        except Exception as E:
            return {"message": f"{E}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}



@app.get("/Physical_verification",tags=["PHYSICAL"])
async def func():
    global locker_state
    return {"result": True,"message":locker_state }


@app.get("/")
async def home(request: Request, db: dp_dependecy):
    revisar_reservas_expiradas(db)
    return templates.TemplateResponse("home.html", {"request": request})


@app.get('/estado_casilleros/')
async def estado_casilleros(request: Request, db: dp_dependecy):
    sql_query = text(f"SELECT * FROM locker")
    result = db.execute(sql_query)
    lockers = result.fetchall()
    dic = {}
    dic_aux = {}
    stations = all_stations(db)
    station_dic = {}
    for station in stations:
        station_dic[station[0]] = station[1]
    for cont, locker in enumerate(lockers):
        if cont == len(lockers)-1:
            dic_aux[locker[0]] = {"id": locker[0], "personal_id": locker[1], "state": get_state_by_state_number(locker[2]), "height": locker[3], "width": locker[4], "depth": locker[5], "station_id": locker[7], "code": locker[6], "Status_fisico": get_state_by_state_number(get_locker_from_global_states(locker[1], station_dic[locker[7]])), "comparacion": get_comparisson_locker_state(locker[2], get_locker_from_global_states(locker[1], station_dic[locker[7]]))}
            dic[locker[7]] = dic_aux
            break
        if cont == 0:
            dic_aux[locker[0]] = {"id": locker[0], "personal_id": locker[1], "state": get_state_by_state_number(locker[2]), "height": locker[3], "width": locker[4], "depth": locker[5], "station_id": locker[7], "code": locker[6], "Status_fisico": get_state_by_state_number(get_locker_from_global_states(locker[1], station_dic[locker[7]])), "comparacion": get_comparisson_locker_state(locker[2], get_locker_from_global_states(locker[1], station_dic[locker[7]]))}
            continue
        if locker[7] != lockers[cont+1][7]:
            dic_aux[locker[0]] = {"id": locker[0], "personal_id": locker[1], "state": get_state_by_state_number(locker[2]), "height": locker[3], "width": locker[4], "depth": locker[5], "station_id": locker[7], "code": locker[6], "Status_fisico": get_state_by_state_number(get_locker_from_global_states(locker[1], station_dic[locker[7]])), "comparacion": get_comparisson_locker_state(locker[2], get_locker_from_global_states(locker[1], station_dic[locker[7]]))}
            dic[locker[7]] = dic_aux
            dic_aux = {}
        else:
            dic_aux[locker[0]] = {"id": locker[0], "personal_id": locker[1], "state": get_state_by_state_number(locker[2]), "height": locker[3], "width": locker[4], "depth": locker[5], "station_id": locker[7], "code": locker[6], "Status_fisico": get_state_by_state_number(get_locker_from_global_states(locker[1], station_dic[locker[7]])), "comparacion": get_comparisson_locker_state(locker[2], get_locker_from_global_states(locker[1], station_dic[locker[7]]))}
 
    return templates.TemplateResponse("estado_casilleros.html", {"request": request, "saccs": dic})

@app.get('/bitacora/')
async def bitacora(request: Request, db: dp_dependecy, reservation_id: int = None):
    sql_query = text(f"SELECT * FROM historial WHERE reservation_id = {reservation_id}")
    result = db.execute(sql_query)
    acciones = result.fetchall()
    datos = []
    #! Aca seguimos usando usuario, hay que revisarlo para hacerlo calzar con la nueva logica que estamos usando
    for i in acciones:
        sql_query = text(f'SELECT * FROM "user" where id = {i[1]}')
        result = db.execute(sql_query)
        usuario = result.fetchone()
        datos.append((i[0], usuario[1], i[2], i[3], i[4], i[5], i[6], i[7], usuario[3], i[8]))
    
    return templates.TemplateResponse("bitacora.html", {"request": request, "acciones": datos})

@app.get('/reservas/')
async def reservas(request: Request, db: dp_dependecy):
    sql_query = text(f"SELECT * FROM reservation")
    result = db.execute(sql_query)
    reservas = result.fetchall()
    return templates.TemplateResponse("reservas.html", {"request": request, "reservas": reservas})

#TODO we need to make a @app.get('/reservas_activas/') to obtain the active reservas for an specific e-commerce

#TODO We need to create and endpoint to send the messages of changes in the reservation id for an speciffic e-commerce

@app.post('/create_e_commerce')
async def create_e_commerce(name:str,password:str,db: dp_dependecy):
    try:
        if password == 'super_secret_password':
            token = generar_clave_alfanumerica()
            db_user = models.User(name=name, token=token)
            db.add(db_user)
            db.commit()
        
            return {"result": True,"message":"E-commerce creado con exito","token":token }
        else:
            return {"result": False,"message":"No tienes acceso para crear el e-commerce" }
    except:
            return {"result": False,"message":"Ha ocurrido un error" }


