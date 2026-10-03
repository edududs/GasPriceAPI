from argparse import ArgumentParser
from pathlib import Path
from typing import Any, override

from django.core.management.base import BaseCommand, CommandError

from gasprice.trips.adapters.catalog import DjangoVehicleCatalog
from gasprice.trips.adapters.pbev import PbevWorkbook
from gasprice.trips.adapters.reference import ReferenceProfiles
from gasprice.trips.application import ImportVehicles, VehicleSourceError, VehicleSourceReader
from gasprice.trips.domain import TripError


class Command(BaseCommand):
    help = "Importa o catálogo de consumo de veículos. Substitui o catálogo anterior da mesma fonte."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--file", type=Path, help="Planilha .xlsx da tabela PBEV do INMETRO.")
        group.add_argument(
            "--reference", action="store_true", help="Perfis genéricos de referência (sem modelos reais)."
        )
        parser.add_argument("--year", type=int, help="Ano da tabela, quando a planilha não tiver a coluna.")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        reader: VehicleSourceReader = (
            ReferenceProfiles()
            if options["reference"]
            else PbevWorkbook(options["file"], year=options["year"])
        )
        try:
            harvest = ImportVehicles(DjangoVehicleCatalog())(reader)
        except (VehicleSourceError, TripError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(harvest.vehicles)} veículos importados, {len(harvest.skipped)} linhas ignoradas"
            )
        )
