from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import declarative_base


class FuelModel(declarative_base()):
    __tablename__ = "gasolina"

    id = Column(Integer, primary_key=True)
    uf = Column(String(50), unique=True, nullable=True)
    value = Column(Float)
