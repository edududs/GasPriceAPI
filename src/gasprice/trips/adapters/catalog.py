from collections.abc import Sequence
from decimal import Decimal

from django.db import transaction

from gasprice.prices.domain import Fuel, normalize
from gasprice.trips.adapters.models import VehicleRecord
from gasprice.trips.domain import Efficiency, Vehicle, VehicleSource

COLUMNS: dict[Fuel, tuple[str, str]] = {
    Fuel.GASOLINE: ("gasoline_city", "gasoline_highway"),
    Fuel.ETHANOL: ("ethanol_city", "ethanol_highway"),
    Fuel.DIESEL_S10: ("diesel_city", "diesel_highway"),
}
"""Light diesel vehicles sold today run on S10, so the label's diesel figure prices as S10."""


class DjangoVehicleCatalog:
    def search(self, query: str, *, limit: int = 20) -> list[Vehicle]:
        scope = VehicleRecord.objects.all()
        for word in normalize(query).split():
            scope = scope.filter(search_key__contains=word)
        return [_to_vehicle(record) for record in scope[:limit]]

    def get(self, vehicle_id: str) -> Vehicle | None:
        if not vehicle_id.isdigit():
            return None
        record = VehicleRecord.objects.filter(pk=int(vehicle_id)).first()
        return _to_vehicle(record) if record is not None else None

    def replace(self, source: VehicleSource, vehicles: Sequence[Vehicle]) -> int:
        with transaction.atomic():
            VehicleRecord.objects.filter(source=source.value).delete()
            VehicleRecord.objects.bulk_create([_to_record(vehicle) for vehicle in vehicles], batch_size=500)
        return len(vehicles)


def _to_record(vehicle: Vehicle) -> VehicleRecord:
    record = VehicleRecord(
        source=vehicle.source.value,
        brand=vehicle.brand,
        model=vehicle.model,
        version=vehicle.version,
        year=vehicle.year,
        search_key=normalize(f"{vehicle.brand} {vehicle.model} {vehicle.version} {vehicle.year or ''}"),
    )
    for fuel, (city, highway) in COLUMNS.items():
        efficiency = vehicle.efficiencies.get(fuel)
        if efficiency is not None:
            setattr(record, city, efficiency.city)
            setattr(record, highway, efficiency.highway)
    return record


def _to_vehicle(record: VehicleRecord) -> Vehicle:
    efficiencies: dict[Fuel, Efficiency] = {}
    for fuel, (city, highway) in COLUMNS.items():
        city_value: Decimal | None = getattr(record, city)
        highway_value: Decimal | None = getattr(record, highway)
        if city_value is not None and highway_value is not None:
            efficiencies[fuel] = Efficiency(city=city_value, highway=highway_value)
    return Vehicle(
        id=str(record.pk),
        source=VehicleSource(record.source),
        brand=record.brand,
        model=record.model,
        version=record.version,
        year=record.year,
        efficiencies=efficiencies,
    )
