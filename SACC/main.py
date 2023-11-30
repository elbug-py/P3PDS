import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List
import models
from database import engine, SessionLocal
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi.templating import Jinja2Templates
import os

templates = Jinja2Templates(directory="templates")


class Station(BaseModel):
    name: str
    address: str
    
class Locker(BaseModel):
    state: int
    personal_id: int
    height: int
    width: int
    depth: int
    code: str
    station: List[Station]
    
class Order(BaseModel):
    name: str
    width: int
    height: int
    depth: int
    
class User(BaseModel):
    name: str
    token: str
    timeForPickup: int
    
    
class Reservation(BaseModel):
    # user: List[User]
    client_email: str
    order: List[Order]
    locker: List[Locker]
    locker_personal_id: int
    station: List[Station]
    fecha: datetime
    estado: str #activa, cancelada, finalizada
    user_id: List[User]

class States(BaseModel):
    id: int
    locker_id: List[Locker]
    state: int
    
class Historial(BaseModel):
    reservation_id: List[Reservation]
    user_id: List[User]
    locker_id: List[Locker]
    station_id: List[Station]
    fecha: datetime
    order: List[Order]
    accion: str
    email: str
    



if __name__=="__main__":
    models.Base.metadata.create_all(bind=engine)
    try:
        if os.environ.get("DEPLOYADO") == "FALSE":
            uvicorn.run("app.app:app",port=8000, reload=True)
        else:
            port = int(os.environ.get("PORT", 8000))
            uvicorn.run("app.app:app", host="0.0.0.0", port=port, log_level="info", reload=True)
    except:
        uvicorn.run("app.app:app",port=8000, reload=True)



