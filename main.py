from flask import Flask, jsonify
from flask_restful import Api, Resource
from pydantic import BaseModel
from sqlalchemy import Column, Float, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from models import *

from gas_scrapper import GasDFPetrobraz

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

GAS_DF = GasDFPetrobraz().gas

api = Api(app)

# Configurando o SQLAlchemy
engine = create_engine("sqlite:///./gas_scrapper/data/gas_db.sqlite3")
Session = sessionmaker(bind=engine)

# Criando a tabela (se não existir)
Base = declarative_base()


# Configurando o Pydantic como modelo de dados
class Gas(BaseModel):
    preco_gas: float


class GasolinaModel(Base):
    __tablename__ = "gasolina"
    id = Column(Integer, primary_key=True)
    preco_gas = Column(Float)


Base.metadata.create_all(engine)


# Definindo os recursos da API
class GetGasPrice(Resource):
    def get(self):
        session = Session()
        gas = session.query(Gas).first()
        session.close()
        return jsonify(gas.preco_gas)


api.add_resource(GetGasPrice, "/gas")

if __name__ == "__main__":
    print(GAS_DF)
    app.run(debug=True)
