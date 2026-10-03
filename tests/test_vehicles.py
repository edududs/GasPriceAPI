from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from trip_fakes import flex
from workbooks import pbev_workbook, plain_vehicle_sheet, workbook

from gasprice.prices.domain import Fuel
from gasprice.trips.adapters.catalog import DjangoVehicleCatalog
from gasprice.trips.adapters.pbev import PbevWorkbook, parse_pbev
from gasprice.trips.adapters.reference import ReferenceProfiles
from gasprice.trips.application import VehicleSourceError
from gasprice.trips.domain import Efficiency, VehicleSource


def test_pbev_reads_the_multi_row_header() -> None:
    harvest = parse_pbev(
        pbev_workbook(
            [
                ("Compacto", "FIAT", "ARGO", "DRIVE 1.0", "F", "9,1", "10,4", "13,1", "14,9"),
                ("Picape", "TOYOTA", "HILUX", "SRV 2.8", "D", None, None, 9.2, 11.1),
                ("Compacto", "VW", "POLO", "TSI", "F", "-", "-", None, None),
                ("Fora de série", "X", "Y", "Z", "E", 7.0, 8.0, None, None),
                (None, None, None, None, None, None, None, None, None),
                ("Notas: valores em km/l", None, None, None, None, None, None, None, None),
            ]
        ),
        year=2025,
    )
    argo, hilux, ethanol_only = harvest.vehicles
    assert (argo.brand, argo.model, argo.version, argo.year) == ("Fiat", "ARGO", "DRIVE 1.0", 2025)
    assert argo.efficiencies == {
        Fuel.ETHANOL: Efficiency(city=Decimal("9.1"), highway=Decimal("10.4")),
        Fuel.GASOLINE: Efficiency(city=Decimal("13.1"), highway=Decimal("14.9")),
    }
    assert hilux.efficiencies.keys() == {Fuel.DIESEL_S10}
    assert ethanol_only.efficiencies.keys() == {Fuel.ETHANOL}
    assert harvest.skipped == ("linha 9: sem km/l de cidade e estrada",)


def test_pbev_reads_a_plain_sheet_with_years() -> None:
    harvest = parse_pbev(
        plain_vehicle_sheet([("Renault", "Kwid", "Zen", "2024/2025", 14.0, 15.2, 9.8, 10.8)])
    )
    (kwid,) = harvest.vehicles
    assert kwid.year == 2024
    assert kwid.is_flex


def test_pbev_reports_bad_values() -> None:
    harvest = parse_pbev(plain_vehicle_sheet([("Renault", "Kwid", "", "", "abc", 15.2, None, None)]))
    assert harvest.vehicles == ()
    assert "não é um preço" in harvest.skipped[0] or "abc" in harvest.skipped[0]


def test_pbev_rejects_files_without_the_table(tmp_path: Path) -> None:
    with pytest.raises(VehicleSourceError, match="MARCA"):
        parse_pbev(workbook([]))
    with pytest.raises(VehicleSourceError, match="planilha"):
        parse_pbev(b"not a workbook")
    with pytest.raises(VehicleSourceError, match="não foi possível ler"):
        PbevWorkbook(tmp_path / "missing.xlsx").read()


def test_reference_profiles_are_labelled() -> None:
    harvest = ReferenceProfiles().read()
    assert len(harvest.vehicles) >= 4
    assert all(vehicle.source is VehicleSource.REFERENCE for vehicle in harvest.vehicles)


@pytest.mark.django_db
def test_catalog_replace_search_and_get() -> None:
    catalog = DjangoVehicleCatalog()
    catalog.replace(VehicleSource.PBEV, [flex(version="Drive 1.0"), flex(model="Pulse", version="Audace")])
    catalog.replace(VehicleSource.REFERENCE, ReferenceProfiles().read().vehicles)
    assert [vehicle.model for vehicle in catalog.search("fiat")] == ["Argo", "Pulse"]
    assert [vehicle.model for vehicle in catalog.search("argo drive 2025")] == ["Argo"]
    assert catalog.search("referencia picape")[0].efficiencies.keys() == {Fuel.DIESEL_S10}
    found = catalog.search("pulse")[0]
    assert catalog.get(found.id) == found
    assert catalog.get("999") is None
    assert catalog.get("abc") is None

    catalog.replace(VehicleSource.PBEV, [flex(model="Mobi")])
    assert [vehicle.model for vehicle in catalog.search("fiat")] == ["Mobi"]
    assert catalog.search("referencia"), "replacing one source keeps the others"


@pytest.mark.django_db
def test_import_command(tmp_path: Path) -> None:
    path = tmp_path / "pbev.xlsx"
    path.write_bytes(pbev_workbook([("Compacto", "FIAT", "MOBI", "LIKE", "F", 9.0, 10.0, 13.0, 14.0)]))
    out = StringIO()
    call_command("import_vehicles", "--file", str(path), "--year", "2025", stdout=out)
    assert "1 veículos importados" in out.getvalue()
    call_command("import_vehicles", "--reference", stdout=StringIO())
    with pytest.raises(CommandError):
        call_command("import_vehicles", "--file", str(tmp_path / "missing.xlsx"), stdout=StringIO())
    empty = tmp_path / "empty.xlsx"
    empty.write_bytes(pbev_workbook([("Compacto", "FIAT", "MOBI", "LIKE", "F", None, None, None, None)]))
    with pytest.raises(CommandError, match="nenhum veículo"):
        call_command("import_vehicles", "--file", str(empty), stdout=StringIO())
