from fastapi import FastAPI, HTTPException, Depends,BackgroundTasks
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
from datetime import datetime
from fastapi_mqtt.fastmqtt import FastMQTT
from fastapi_mqtt.config import MQTTConfig


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
        db_station = models.Station(address="G3", id=2)
        db.add(db_station)
        db_station = models.Station(address="G5", id=3)
        db.add(db_station)
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
        
        db_locker = models.Locker(state=0, height=20, width=50, depth=25, station_id=2, id=4, personal_id=1)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=20, width=60, depth=25, station_id=2, id=5, personal_id=2)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=20, width=30, depth=25, station_id=2, id=6, personal_id=3)
        db.add(db_locker)
        db.commit()
        db_locker = models.Locker(state=0, height=30, width=30, depth=30, station_id=3, id=7, personal_id=1)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=30, width=40, depth=30, station_id=3, id=8, personal_id=2)
        db.add(db_locker)
        db_locker = models.Locker(state=0, height=20, width=50, depth=30, station_id=3, id=9, personal_id=3)
        db.add(db_locker)
        db.commit()
        
    if not db.query(models.User).count():
        db_user = models.User(name="operario1", email="oper1@example.com", typeUser="operario")
        db.add(db_user)
        db_user = models.User(name="operario2", email="oper2@example.com", typeUser="operario")
        db.add(db_user)
        db_user = models.User(name="cliente1", email="client1@example.com", typeUser="cliente")
        db.add(db_user)
        db_user = models.User(name="cliente2", email="client2@example.com", typeUser="cliente")
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

def encontrar_locker_mas_pequeno(alto_paquete, ancho_paquete, profundidad_paquete, lockers):
    """
    Encuentra la caja más pequeña posible que puede acomodar un paquete dado.

    Args:
    - alto_paquete (float): Alto del paquete.
    - ancho_paquete (float): Largo del paquete.
    - profundidad_paquete (float): Profundidad del paquete.
    - lockers (list): lista de lockers, formato (locker_id, station_id): (alto, largo, profundidad).

    Returns:
    - locker or None: id del locker más pequeño posible. Si no hay ninguna caja que pueda acomodar el paquete, retorna None.
    """
    mejor_locker = None
    mejor_volumen = float(1000*1000*1000)
    dimensiones_permutadas = permutations([alto_paquete, ancho_paquete, profundidad_paquete])

    for locker in lockers:
        for dimensiones_paquete in dimensiones_permutadas:
            alto_paquete, ancho_paquete, profundidad_paquete = locker[3], locker[4], locker[5]
            if (
                dimensiones_paquete[0] <= alto_paquete and
                dimensiones_paquete[1] <= ancho_paquete and
                dimensiones_paquete[2] <= profundidad_paquete
            ):
                volumen_locker = alto_paquete * ancho_paquete * profundidad_paquete
                if volumen_locker < mejor_volumen:
                    mejor_locker = locker[0]
                    mejor_volumen = volumen_locker

    return mejor_locker

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

app = FastAPI()

mqtt_config = MQTTConfig(
    host="ab34c5b092fc416db7e2f21aa7d38514.s1.eu.hivemq.cloud",
    port=8883,
    ssl=True,
    keepalive=60,
    username="M0ki1",
    password="1331Mati??",
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


@mqtt.on_connect()
def connect(client, flags, rc, properties):
    mqtt.client.subscribe("/mqtt") #subscribing mqtt topic
    print("Connected: ", client, flags, rc, properties)

@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    print("Received message: ",topic, payload.decode(), qos, properties)
    return 0

@mqtt.subscribe("/test1")
async def message_to_topic(client, topic, payload, qos, properties):
    print("Received message to specific topic: ", topic, payload.decode(), qos, properties)

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
async def reservar(alto_paquete: int, ancho_paquete: int, profundidad_paquete: int, user_id: int, db: dp_dependecy):
    try:
        try:
            sql_query = text(f"SELECT * FROM locker WHERE state = 0")
            result = db.execute(sql_query)
            lockers = result.fetchall()
            if len(lockers) == 0:
                return {"message": "Failed to reserve, no available lockers"}
            sql_query = text(f'SELECT * FROM "user" WHERE id = {user_id}')
            result = db.execute(sql_query)
            user = result.fetchone()
            if user is None:
                return {"message": "Failed to reserve, user does not exist"}
            locker = encontrar_locker_mas_pequeno(alto_paquete, ancho_paquete, profundidad_paquete, lockers)
            if locker is None:
                return {"message": "Failed to reserve, package is too big for available lockers"}
            else:
                # Creo una orden ficticia, porque debería exisitr una orden de antes
                db_order = models.Order(name="order ficitica", width=ancho_paquete, height=alto_paquete, depth=profundidad_paquete)
                db.add(db_order)
                db.commit()
                # Reservo el locker cambiando el estado
                sql_query = text(f"UPDATE locker SET state = 1 WHERE id = {locker}")
                db.execute(sql_query)
                db.commit()
                # Creo la reserva
                db_reservation = models.Reservation(user_id=user_id, order_id=db_order.id, locker_id=locker, locker_personal_id=get_locker_personal_id(db, locker), station_id=station_by_locker_id(db, locker)[0], fecha=datetime.now(), estado="activa")
                db.add(db_reservation)
                db.commit()
                # asigno un codigo al locker
                clave = generar_clave_alfanumerica()
                sql_query = text(f"UPDATE locker SET code = '{clave}' WHERE locker.id = {locker}")
                db.execute(sql_query)
                db.commit()
                # añadir el cambio de estado a la tabla states
                sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker}, 1)")
                db.execute(sql_query)
                db.commit()
                
                # ACA DEBERIA DE MANDAR EL CORREO Y TAMBIEN MANDAR UN MQTT CON QUE EL ESTADO DE ESE LOCKER 
                #PASA A 1 -> RESERVADO
                return {"message": "Reservation successful", "locker_id": locker, "station_id": station_by_locker_id(db, locker)[0], "code": clave}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    
# pdf parte 3
@app.post('/confirm_reservation', tags=['CONFIRM RESERVATION'])
async def confirm_reservation(reservation: int, db: dp_dependecy):
    try:
        try:
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
                sql_query = text(f"SELECT * FROM locker WHERE id = {reserva[2]}")
                result = db.execute(sql_query)
                locker_obtenido = result.fetchone()
                #Igual la idea aca es que si pasa mucho tiempo gg y murio la reserva por lo que
                #Habria que borrarla de la BBDD
                if locker_obtenido[2] == 1:
                    #Correo de que el operario debe ver esta 
                    sql_query = text(f'SELECT * FROM "user" WHERE id={1}')
                    result = db.execute(sql_query)
                    operario = result.fetchone()
                    await send_email_async('Verificar medidas',f'{operario[2]}',
                            f"debes verificar la reserva {reservation}")
                    #TODO va a entregar y el mqtt cambiar el estado del cajon especifico a reservado
                    



                    return {"message": f"Time passed since reservation: {time_difference}"}
                else:
                    #TODO cambiar mqtt a disponible si esto pasa cajon, 0
                    return {"message": f"Failed to confirm reservation, locker is not reserved, it is {estados_generales[locker_obtenido[2]]} "}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    
# del pdf es la 4
@app.post('/cancel_reservation', tags=['CANCEL RESERVATION'])
async def cancel_reservation(reservation: int, db: dp_dependecy): #TODO NUMERO DE CAJON
    try:
        try:
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to cancel reservation, reservation does not exist"}
            else:
                sql_query = text(f"SELECT * FROM locker WHERE id = {reserva[2]}")
                result = db.execute(sql_query)
                locker_obtenido = result.fetchone()
                if locker_obtenido[2] == 1:
                    sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker_obtenido[0]}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"UPDATE reservation SET estado = 'cancelada' WHERE reservation.id = {reservation}")
                    db.execute(sql_query)
                    db.commit()
                    sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker_obtenido[0]}, 0)")
                    db.execute(sql_query)
                    db.commit()
                    #TODO Cambiar cajon a disponible con el mqtt






                    return {"message": "Reservation canceled successfully"}
                else:
                    return {"message": f"Failed to cancel reservation, locker is not reserved, it is {estados_generales[locker_obtenido[2]]} "}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}

# del pdf es la 5
@app.post('/reservation_state', tags=['RESERVATION STATE'])
async def reservation_state(reservation: int, db: dp_dependecy):
    data = []
    try:
        try:
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
async def confirm(height: int, width: int, depth: int, reservation: int, db: dp_dependecy):
    try:
        try:
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[2]}')
                result = db.execute(sql_query)
                locker = result.fetchone()
                if locker is None:
                    return {"message": "Failed to confirm, locker does not exist"}
                else:
                    #compare the dimensions of the package with the dimensions of the locker
                    if height <= locker[3] and width <= locker[4] and depth <= locker[5]:

                        #TODO
                        #Mandar correo a operario con la clave de este locker para que lo 
                        #pueda abrir
                        sql_query = text(f'SELECT * FROM "user" WHERE id={1}')
                        result = db.execute(sql_query)
                        operario = result.fetchone()
                        await send_email_async('Entregar Product',f'{operario[2]}',
                                f"Debes entregar en la Estacion G1 el paquete con reservacion {reservation} con el codigo: {locker[6]}")
                        return {"message": "Package confirmed"}
                    else:
                        sql_query = text(f"UPDATE locker SET state = 0 WHERE id = {locker[0]}")
                        #TODO mandar mqtt para cambiar el estado del locker a disponible
                        db.execute(sql_query)
                        db.commit()
                        sql_query = text(f"UPDATE reservation SET estado = 'cancelada' WHERE reservation.id = {reservation}")
                        db.execute(sql_query)
                        db.commit()
                        sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({locker[0]}, 0)")
                        db.execute(sql_query)
                        db.commit()

                        sql_query = text(f"SELECT * FROM locker WHERE height >= {height} AND width >= {width} AND depth >= {depth} AND state = 0")
                        result = db.execute(sql_query)
                        lockers = result.fetchone()
                        if lockers is None:
                            return {"message": "Failed to confirm, no available lockers"}
                        else:
                            sql_query = text(f"UPDATE locker SET state = 1 WHERE id = {lockers[0]}")
                            db.execute(sql_query)
                            db.commit()
                            sql_query = text(f"UPDATE reservation SET locker_id = {lockers[0]}, locker_personal_id = {lockers[1]}, station_id = {lockers[7]} WHERE id = {reservation}")
                            db.execute(sql_query)
                            db.commit()
                            sql_query = text(f"INSERT INTO states (locker_id, state) VALUES ({lockers[0]}, 1)")
                            db.execute(sql_query)
                            db.commit()
                            return {"message": f"Package re-assigned to locker {lockers[0]}"}

        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    



# 7 del pdf
@app.post('/ready', tags=['READY'])
async def ready(reservation: int, db: dp_dependecy):
    try:
        try:
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to ready, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM "user" WHERE id = {reserva[1]}')
                result = db.execute(sql_query)
                user = result.fetchone()
                if user is None:
                    return {"message": "Failed to ready, user does not exist"}
                else:
                    #TODO ACA MANDAR UN CORREO AL USER
                    return {"message": f'user {user[1]} ready to pick up package'}
        except Exception as e:
            return {"message": f"Error: {e}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}
    

@app.post('/load', tags = ["LOAD"])
async def load(reservation: int,code: str, db: dp_dependecy):
    try:
        try:
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[2]}')
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
                    #TODO aca debo hacer la llamada MQTT para abrir el cajon
                    sql_query = text(f'SELECT * FROM "user" WHERE id = {reserva[1]}')
                    result = db.execute(sql_query)
                    user = result.fetchone()
                    clave = generar_clave_alfanumerica()
                    sql_query = text(f"UPDATE locker SET code = '{clave}' WHERE locker.id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()
                    print(f"Nueva clave: ${clave}")
                    #TODO mandar el correo a este usuario con la nueva clave
                    sql_query = text(f'SELECT * FROM "user" WHERE id={3}')
                    result = db.execute(sql_query)
                    cliente = result.fetchone()
                    await send_email_async('Retirar producto',f'{cliente[2]}',
                            f"Debes retirar en la Estacion G1 el paquete con reservacion {reservation} con el codigo: {clave}")




                    return {"message": f"Se ha abierto el espacio {locker[1]}, la nueva clave es {clave}"}
        except Exception as E:
            return {"message": f"{E}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}


@app.post('/unload', tags = ["UNLOAD"])
async def load(reservation: int,code: str, db: dp_dependecy):
    try:
        try:
            sql_query = text(f"SELECT * FROM reservation WHERE id = {reservation}")
            result = db.execute(sql_query)
            reserva = result.fetchone()
            if reserva is None:
                return {"message": "Failed to confirm, reservation does not exist"}
            else:
                sql_query = text(f'SELECT * FROM locker WHERE id = {reserva[2]}')
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
                    sql_query = text(f"UPDATE reservation SET estado = finalizada WHERE id = {reservation}")
                    db.execute(sql_query)
                    db.commit()
                    
                    print(locker[6])
                    #TODO aca debo hacer la llamada MQTT para abrir el cajon

                   
                    sql_query = text(f"UPDATE locker SET code = NULL WHERE locker.id = {locker[0]}")
                    db.execute(sql_query)
                    db.commit()




                    return {"message": f"Se ha abierto el espacio {locker[1]}"}
        except Exception as E:
            return {"message": f"{E}"}
    except requests.exceptions.Timeout:
        return {"message": "Timeout error"}


@app.get('/send-email/asynchronous', tags = ["TEST_MAILER"])
async def send_email_asynchronous():
    await send_email_async('Hello World','mamunoz11@miuandes.cl',
    {'title': 'Hello World', 'name': 'John Doe'})
    return 'Success'

@app.get("/test",tags=["TEST"])
async def test(db:dp_dependecy):
    sql_query = text(f'SELECT * FROM "user" WHERE id={1}')
    result = db.execute(sql_query)
    operario = result.fetchone()
    print(operario[2])
    return "lol"
# 7 del pdf

async def func():
    mqtt.publish("/test1", "Hello from Fastapi") #publishing mqtt topic

    return {"result": True,"message":"Published" }