from db_handler import DBManager, FuelManager
from gas_scrapper import GasDFPetrobraz
from models import FuelModel


# Definindo os recursos da API
class GetGasPrice:
    def __init__(self) -> None:
        self.db_manager = DBManager()
        self.gas_manager = FuelManager(self.db_manager)

    def get(self, uf=None):
        if uf:
            gas = self.gas_manager.find(uf=uf)
            print(gas.preco_gas)
        else:
            gas_list = self.gas_manager.find_all()
            print(gas_list)


gas = GetGasPrice()
gas.get("DF")
