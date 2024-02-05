import os

import pandas as pd
import requests
from bs4 import BeautifulSoup


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

        self._save_gas_price(gas_value)

        return gas_value

    def _save_gas_price(self, gas_value) -> None:
        """
        Save gas price to a JSON file.

        Parameters:
            gas_value (float): The value of the gas price.

        Returns:
            None
        """
        df = pd.DataFrame(
            {
                "date": [pd.to_datetime("today")],
                "preco_gas": [gas_value],
            }
        )
        os.makedirs("./gas_scrapper/data", exist_ok=True)
        df.to_json(
            "./gas_scrapper/data/gas_price.json", orient="records", date_format="iso"
        )
