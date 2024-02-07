import os
from typing import Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gas_scrapper import UF, GasPricePetrobras
from models import FuelModel

DB_URI = "sqlite:///./data/gas_db.sqlite3"


class DBManager:
    def __init__(self):
        self.engine = create_engine(DB_URI)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        FuelModel.metadata.create_all(self.engine)

    def create_session(self):
        return self.Session()


class FuelManager:
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager

    def find_by_state(self, uf: UF | str) -> Optional[Dict]:
        with self.db_manager.create_session() as session:
            fuel = session.query(FuelModel).filter_by(uf=str(uf)).first()
            return self._fuel_to_dict(fuel)

    def find_all(self) -> Optional[List[Dict]]:
        with self.db_manager.create_session() as session:
            fuels = session.query(FuelModel).all()
            fuels_dicts = []
            for fuel in fuels:
                fuel_dict = self._fuel_to_dict(fuel)
                if fuel_dict:
                    fuels_dicts.append(fuel_dict)

            return fuels_dicts

    def _fuel_to_dict(self, fuel: Optional[FuelModel]) -> Optional[Dict]:
        if fuel:
            return {"uf": fuel.uf, "price": fuel.value}
        return None

    def update_price(self, uf: UF | str, new_price: float) -> None:
        with self.db_manager.create_session() as session:
            fuel = session.query(FuelModel).filter_by(uf=str(uf)).first()
            if fuel:
                fuel.value = new_price
            else:
                fuel = FuelModel(uf=str(uf), value=new_price)
                session.add(fuel)
            session.commit() 


def create_db():
    os.makedirs("data", exist_ok=True)
    db_manager = DBManager()
    db_manager.create_tables()
    fuel_manager = FuelManager(db_manager)

    gas_prices = GasPricePetrobras().get_all()
    for uf, price in gas_prices.items():
        fuel_manager.update_price(uf, price)
