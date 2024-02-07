from flask import Flask, jsonify
from flask_restful import Api, Resource

from db_control import DBManager, FuelManager

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
api = Api(app)


# Definindo os recursos da API
class GetGasPrice(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.db_manager = DBManager()
        self.gas_manager = FuelManager(self.db_manager)

    def get(self, uf=None):
        if uf:
            uf = uf.upper()
            gas = self.gas_manager.find_by_state(uf)
            return jsonify(mensagem="Precos disponiveis", precos=gas)
        else:
            gas_list = self.gas_manager.find_all()
            return jsonify(mensagem="Precos disponiveis", precos=gas_list)


api.add_resource(GetGasPrice, "/gas", "/gas/<string:uf>")

if __name__ == "__main__":
    app.run(debug=True)
