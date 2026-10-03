# GasPrice

Preço dos combustíveis por estado: coleta da ANP, site Django + htmx + Tailwind com mapa, API ninja.
Comece pelo [README](README.md); o porquê de cada escolha está em [docs/decisions.md](docs/decisions.md).

## Regras

1. **Idioma.** Código, identificadores e nomes de arquivo em inglês. Documentação e textos de interface em pt-BR.
2. **Hexágono.** `domain/` e `application/` só importam stdlib, pydantic e a própria camada. Django,
   httpx, openpyxl e qualquer SDK moram em `adapters/`. `tests/test_architecture.py` garante isso.
3. **Fonte nova entra como adaptador** que implementa `PriceSource` e devolve um `Harvest`; nunca
   escreve no banco direto. A coleta passa sempre por `CollectPrices`.
4. **Sem tipos frouxos.** pyright strict, ruff `ALL`. Antes de declarar pronto: `uv run poe fix`.
5. **Bugfix entra com o teste que o reproduz.** Mudou o formato de uma fonte: atualize o construtor de
   planilhas em `tests/workbooks.py` antes do parser.
6. **Decisão nova vira linha em `docs/decisions.md`**, no mesmo commit. Decisão antiga não é editada, é substituída.
7. **Front sem build JS.** Interatividade via htmx e fragmentos do servidor; JS só em `web/static/js`,
   bibliotecas vendorizadas em `web/static/vendor`. Mudou classes Tailwind: `uv run poe css`.
