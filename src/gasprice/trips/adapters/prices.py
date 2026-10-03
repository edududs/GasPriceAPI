"""The trips context reads prices through its own port; this adapter answers it from the prices context."""

from gasprice.prices.adapters.composition import get_board
from gasprice.prices.domain import Fuel
from gasprice.trips.domain import PriceTable


class BoardFuelPrices:
    def table(self, fuel: Fuel) -> PriceTable:
        board = get_board(fuel)
        return PriceTable(
            fuel=fuel,
            prices={entry.state: entry.average for entry in board.entries},
            mean=board.mean,
            period_end=board.latest_period,
        )
