import os
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gas_scrapper import GasPricePetrobras, UF
from models import FuelModel


class CRUDError(Exception):
    """Base exception for CRUD errors."""


class OperationType(Enum):
    """Enum for CRUD operation types."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


class DB:
    @staticmethod
    def create():
        os.makedirs("./data", exist_ok=True)
        engine = create_engine("sqlite:///./data/gas_db.sqlite3")
        Session = sessionmaker(bind=engine)
        session = Session()

        session.close()
        FuelModel.metadata.create_all(engine)


class DBManager:
    """Class for managing the database."""

    def __init__(self):
        self._engine = create_engine("sqlite:///./data/gas_db.sqlite3")
        self._sessionmaker = sessionmaker(bind=self._engine)

        # Create tables if they don't exist
        DB.create()

    def create_session(self):
        """Create a new session."""
        return self._sessionmaker()

    def execute_operation(
        self, session, operation_type: OperationType, **kwargs: Any
    ) -> Any:
        """Execute the specified CRUD operation."""
        operation = self._get_operation(operation_type)
        try:
            return operation(session, **kwargs)
        except Exception as e:
            raise CRUDError(e) from e

    def _get_operation(self, operation_type: OperationType):
        """Return the specific CRUD operation function."""
        operations = {
            OperationType.CREATE: self._create,
            OperationType.READ: self._read,
            OperationType.UPDATE: self._update,
            OperationType.DELETE: self._delete,
        }
        return operations[operation_type]

    @staticmethod
    def _create(session, model: FuelModel) -> FuelModel:
        """Create a new record in the database."""
        session.add(model)
        session.commit()
        return model

    @staticmethod
    def _read(session, **kwargs: Any) -> Optional[FuelModel]:
        """Return a record from the database."""
        filter_criteria = kwargs.get("filter")
        if filter_criteria:
            return session.query(FuelModel).filter_by(**filter_criteria).first()
        else:
            return session.query(FuelModel).all()

    @staticmethod
    def _update(session, model: FuelModel) -> FuelModel:
        """Update a record in the database."""
        session.merge(model)
        session.commit()
        return model

    @staticmethod
    def _delete(session, **kwargs: Any) -> None:
        """Delete a record from the database."""
        filter_criteria = kwargs.get("filter")
        session.query(FuelModel).filter_by(**filter_criteria).delete()
        session.commit()


class FuelManager:
    """Class for managing fuel prices in the database."""

    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
        self.session = self.db_manager.create_session()

    def _to_json(self, fuel_model: FuelModel) -> dict:
        """Convert a FuelModel to a serializable JSON dictionary."""
        return {
            "uf": fuel_model.uf,
            "price": fuel_model.value,
            # Add other fields as needed
        }

    def find_by_state(self, uf: UF | str) -> Optional[Dict]:
        try:
            if isinstance(uf, UF):
                uf = uf.name

            val = self.db_manager.execute_operation(
                self.session, OperationType.READ, filter={"uf": uf}
            )

            return self._to_json(val)
        finally:
            self.session.close()

    def find_all(self) -> Optional[List[Dict]]:
        try:
            prices = []
            for fuel in self.db_manager.execute_operation(
                self.session, OperationType.READ
            ):
                prices.append(self._to_json(fuel))
            return prices
        finally:
            self.session.close()

    def find(self, **kwargs) -> Optional[Dict]:
        try:
            filter_criteria = kwargs.get("filter")
            if filter_criteria:
                if isinstance(filter_criteria, UF):
                    filter_criteria = {"uf": filter_criteria.value}
                val = self.db_manager.execute_operation(
                    self.session, OperationType.READ, filter=filter_criteria
                )
                return self._to_json(val)
            else:
                val = self.db_manager.execute_operation(
                    self.session, OperationType.READ
                )[0]
                return self._to_json(val)
        finally:
            self.session.close()

    def update_price(self, uf: UF | str, new_price: float) -> None:
        """Update the fuel price in the database."""
        try:
            if isinstance(uf, UF):
                uf = uf.name
            fuel = self.db_manager.execute_operation(
                self.session, OperationType.READ, filter={"uf": uf}
            )
            if fuel:
                fuel.value = new_price
                self.db_manager.execute_operation(
                    self.session, OperationType.UPDATE, model=fuel
                )
            else:
                new_model = FuelModel(value=new_price, uf=uf)
                self.db_manager.execute_operation(
                    self.session, OperationType.CREATE, model=new_model
                )
        finally:
            self.session.close()

    def create_price(self, uf: UF | str, new_price: float) -> None:
        """Create a new record in the database."""
        try:
            if isinstance(uf, UF):
                uf = uf.name
            new_model = FuelModel(value=new_price, uf=uf)
            self.db_manager.execute_operation(
                self.session, OperationType.CREATE, model=new_model
            )
        finally:
            self.session.close()


def run():
    db_manager = DBManager()
    fuel_manager = FuelManager(db_manager)
    gas_df = GasPricePetrobras().get_df()
    gas_mg = GasPricePetrobras().get_mg()
    gas_go = GasPricePetrobras().get_go()
    gas_sp = GasPricePetrobras().get_sp()

    fuel_manager.update_price(UF.DF, gas_df)
    fuel_manager.update_price(UF.MG, gas_mg)
    fuel_manager.update_price(UF.GO, gas_go)
    fuel_manager.update_price(UF.SP, gas_sp)


run()
