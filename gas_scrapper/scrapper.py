import os
from enum import Enum

import pandas as pd
import requests
from bs4 import BeautifulSoup


class UF(Enum):
    DF = "Distrito Federal"
    GO = "Goiás"
    AL = "Alagoas"
    CE = "Ceará"
    ES = "Espírito Santo"
    MT = "Mato Grosso"
    MA = "Maranhão"
    MG = "Minas Gerais"
    PR = "Paraná"
    PB = "Paraíba"
    PA = "Pará"
    PE = "Pernambuco"
    RJ = "Rio de Janeiro"
    SC = "Santa Catarina"
    SP = "São Paulo"
    RS = "Rio Grande do Sul"


class GasDFPetrobraz:
    def __init__(self):
        """
        Initialize the object by setting the URL for Petrobras fuel prices API, making a GET
        request to the URL, and storing the HTML content of the response.
        If the response status code is not 200, raise a ValueError.
        """
        self.url = (
            "https://precos.petrobras.com.br/web/precos-dos-combustiveis/w/gasolina/df"
        )
        response = requests.get(self.url, timeout=100)
        if response.status_code != 200:
            raise ValueError(f"Falha na requisição com código {response.status_code}")
        self.html_content = response.content
        self._gas = None

    @property
    def gas(self):
        """
        This function is a property getter for the gas attribute. It does not take any parameters and returns the current gas price.
        """
        self._gas = self.get_gas_price()
        return self._gas

    def get_gas_price(self) -> float:
        """
        Retrieves and returns the gas price from the HTML content.

        :param self: The instance of the class.
        :return: The gas price as a float.
        """
        soup = BeautifulSoup(self.html_content, "lxml")
        if soup.select_one(".h4.real-value#telafinal-precofinal") is None:
            raise ValueError("Precos indisponíveis")

        gas_value = float(
            soup.select_one(".h4.real-value#telafinal-precofinal")
            .text.strip()
            .replace(",", ".")
        )

        return gas_value


class GasPricePetrobras:
    def __init__(self):

        self.base_url = (
            "https://precos.petrobras.com.br/web/precos-dos-combustiveis/w/gasolina/"
        )

    def get_df(self):
        response = self._get_response(UF.DF)
        gas_value = self._get_gas_value(response)
        return gas_value

    def get_go(self):
        response = self._get_response(UF.GO)
        gas_value = self._get_gas_value(response)
        return gas_value

    def get_mg(self):
        response = self._get_response(UF.MG)
        gas_value = self._get_gas_value(response)
        return gas_value

    def get_sp(self):
        response = self._get_response(UF.SP)
        gas_value = self._get_gas_value(response)
        return gas_value

    def _get_gas_value(self, response):
        soup = BeautifulSoup(response.content, "lxml")
        if soup.select_one(".h4.real-value#telafinal-precofinal") is None:
            raise ValueError("Precos indisponíveis")

        gas_value = float(
            soup.select_one(".h4.real-value#telafinal-precofinal")
            .text.strip()
            .replace(",", ".")
        )
        return gas_value

    def _get_response(self, uf: UF):
        base_url = self._make_url(uf)
        response = requests.get(base_url, timeout=100)
        if response.status_code != 200:
            raise ValueError(f"Falha na requisição com código {response.status_code}")
        return response

    def _make_url(self, uf: UF):
        url = self.base_url + uf.name.lower()
        return url


if __name__ == "__main__":
    gas = GasPricePetrobras()
    print(gas.get_sp())
