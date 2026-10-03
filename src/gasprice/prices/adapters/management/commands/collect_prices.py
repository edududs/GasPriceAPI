from argparse import ArgumentParser
from typing import Any, override

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gasprice.prices.adapters.anp import AnpSource
from gasprice.prices.adapters.composition import clock, repository
from gasprice.prices.adapters.demo import DemoSource
from gasprice.prices.adapters.http import build_client
from gasprice.prices.adapters.petrobras import PetrobrasSource
from gasprice.prices.application import CollectPrices, PriceSource
from gasprice.prices.domain import Source


class Command(BaseCommand):
    help = "Coleta preços de uma fonte e grava no banco. Sai com erro se a coleta falhar."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--source", choices=[source.value for source in Source], default=Source.ANP.value)
        parser.add_argument(
            "--workbook",
            help="ANP: URL ou caminho de uma planilha específica (ex.: a série histórica desde 2013). "
            "Sem ela, a planilha mais recente é descoberta na página do levantamento.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        source_name = Source(options["source"])
        with build_client(settings.GASPRICE_HTTP_TIMEOUT) as client:
            today = timezone.localdate
            source: PriceSource
            match source_name:
                case Source.ANP:
                    source = AnpSource(
                        client, page_url=settings.GASPRICE_ANP_PAGE_URL, workbook=options["workbook"]
                    )
                case Source.PETROBRAS:
                    source = PetrobrasSource(client, today=today)
                case Source.DEMO:
                    source = DemoSource(today=today)
            run = CollectPrices(repository, clock)(source)
        if not run.succeeded:
            msg = f"{run.source}: {run.error}"
            raise CommandError(msg)
        self.stdout.write(
            self.style.SUCCESS(f"{run.source}: {run.written} preços gravados, {run.skipped} ignorados")
        )
