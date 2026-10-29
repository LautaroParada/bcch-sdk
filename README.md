# bcch-sdk

Cliente Python **no oficial** para la API REST de la Base de Datos Estadísticos (BDE)
del Banco Central de Chile. No existe afiliación, patrocinio ni respaldo del Banco Central
de Chile.

El paquete se concentra en acceso y descubrimiento de series: autenticación REST por API Key
Token, transporte HTTP seguro, respuestas tipadas, consultas múltiples con control de tasa,
integración opcional con pandas y un catálogo BDE local. No incluye análisis económico,
transformaciones, proyecciones ni visualizaciones.

## Requisitos

- Python 3.11 o superior.
- API Key Token para las operaciones REST.
- No se requieren token, red ni pandas para consultar el catálogo local.

## Instalación desde GitHub

Después de que esta modernización sea aceptada e integrada en el repositorio original:

```bash
python -m pip install git+https://github.com/LautaroParada/bcch-sdk.git
```

Para instalaciones reproducibles, prefiera una versión etiquetada:

```bash
python -m pip install git+https://github.com/LautaroParada/bcch-sdk.git@v1.0.0
```

También puede fijar un commit exacto:

```bash
python -m pip install git+https://github.com/LautaroParada/bcch-sdk.git@<commit-sha>
```

La etiqueta estable `v1.0.0` solo debe crearse después de la revisión y aceptación upstream.
La versión candidata de este cambio es `1.0.0.dev0` y no se publica.

`bcch 0.0.2` en PyPI es la distribución histórica. `pip install bcch` no es la ruta
recomendada para el desarrollo actual.

Instalación para contribuir:

```bash
git clone https://github.com/LautaroParada/bcch-sdk.git
cd bcch-sdk
python -m pip install -e ".[dev]"
```

La integración con DataFrame es opcional:

```bash
python -m pip install "bcch[dataframe] @ git+https://github.com/LautaroParada/bcch-sdk.git"
```

## Autenticación

La documentación REST actual exige incluir un API Key Token en cada consulta. Cree una cuenta
BDE, habilite el acceso a la API y copie el token desde **Mi Cuenta → Apikey Token**, siguiendo
la [guía oficial de acceso](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/acceso_api.html).
El token tiene carácter secreto y no debe quedar en el código fuente.

```python
import os

from bcch import BancoCentralDeChile

client = BancoCentralDeChile(token=os.environ["BCCH_TOKEN"])
```

Las versiones históricas de este SDK recibían usuario y contraseña. Este cliente REST moderno
no transmite esos campos. El constructor histórico falla localmente con
`BCCHLegacyAuthenticationError` e indica la migración a `BancoCentralDeChile(token="...")`.
No se implementa SOAP ni un fallback oculto.

El timeout predeterminado es 30 segundos. Puede ajustarlo con
`BancoCentralDeChile(token=..., timeout=60)`.

## Obtener una serie

```python
result = client.get_series(
    "F073.TCO.PRE.Z.D",
    start="2025-01-01",
    end="2025-12-31",
)

print(result.series_id)
print(result.title_es)
print(result.observations[0].date)
print(result.observations[0].value)
print(result.observations[0].status_code)
```

`get_series()` llama explícitamente a `function=GetSeries`. Las fechas de entrada usan
`YYYY-MM-DD`; las fechas de observación REST se convierten a `datetime.date`. Un valor
`"NaN"` se representa como `None` y su `status_code`, por ejemplo `"ND"`, se conserva.
El JSON completo permanece disponible en `result.raw`.

Los alias históricos `serie`, `timeseries`, `from_`, `firstdate`, `to_` y
`lastdate` siguen disponibles.

## Buscar series en vivo

```python
series_mensuales = client.search_series(frequency="monthly")

for item in series_mensuales[:3]:
    print(item.series_id, item.title_es)
```

`search_series()` ejecuta una consulta REST en vivo con `function=SearchSeries`. Acepta
`DAILY`, `MONTHLY`, `QUARTERLY` y `ANNUAL`, sin distinguir mayúsculas, además de
`diaria`, `mensual`, `trimestral` y `anual`.

## Obtener varias series

```python
results = client.get_many(
    {
        "usd": "F073.TCO.PRE.Z.D",
        "uf": "F073.UFF.PRE.Z.D",
        "ipc_indice": "F074.IPC.IND.Z.EP23.C.M",
        "ipc_variacion": "F074.IPC.VAR.Z.EP23.C.M",
    },
    start="2025-01-01",
    end="2025-12-31",
)

print(results["uf"].observations[-1])
```

`get_many()` es una conveniencia del SDK: la API REST no tiene endpoint masivo. Realiza
consultas individuales y devuelve un `dict[str, SeriesResult]` en el orden de entrada.
El cliente respeta el límite oficial de hasta **5 series diferentes por segundo por cuenta**
y no usa paralelismo sin control.

## Catálogo local y SearchSeries no son lo mismo

El snapshot local fue convertido desde el archivo de catálogo BDE identificado como
**2026-10-29**. Conserva 30.920 filas, 25.291 códigos únicos y todos los contextos
duplicados por capítulo o cuadro. La metadata incluye la huella SHA-256 del XLSX fuente.
La fecha identifica el archivo de origen; no certifica la disponibilidad de cada serie en vivo.

```python
from bcch import SeriesCatalog

# No requiere token, red ni pandas.
catalog = SeriesCatalog()

matches = catalog.search(
    "inflación",
    frecuencia="Mensual",
    vigencia="Vigente",
)

ipc = catalog.get("F074.IPC.IND.Z.EP23.C.M")
for context in ipc.contexts:
    print(context.chapter, context.table, context.name)
```

El mismo catálogo está disponible como `client.catalog`:

```python
usd = client.catalog.get("F073.TCO.PRE.Z.D")
fuentes_bcch = client.catalog.search(
    source="Banco Central de Chile",
    unit="Índice",
    limit=10,
)
```

- `client.search_series(...)`: catálogo operativo obtenido desde el REST en vivo; requiere
  token y red.
- `client.catalog.search(...)`: snapshot local enriquecido; no requiere token ni red.

`catalog.search()` permite filtrar por texto, frecuencia, vigencia, capítulo, fuente y unidad.
La búsqueda textual no distingue mayúsculas ni acentos. `catalog.get(code)` devuelve todos
los contextos del código, sin deduplicarlos.

## pandas opcional

```python
frame = result.to_dataframe()
print(frame.head())

combined = client.get_many_dataframe(
    ["F073.TCO.PRE.Z.D", "F073.UFF.PRE.Z.D"],
    start="2025-01-01",
    end="2025-01-31",
)
```

El import principal de `bcch` no importa pandas. Si no está instalado, un método específico
de DataFrame explica cómo instalar el extra `bcch[dataframe]`.

## Compatibilidad histórica

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("always", DeprecationWarning)
    observations = client.get_macro(
        serie="F073.TCO.PRE.Z.D",
        from_="2025-01-01",
        to_="2025-01-31",
    )
    series_infos = client.get_busqueda(frecuencia="quarterly")
```

`get_macro()` mantiene el resultado histórico: una lista de diccionarios de observaciones.
`get_busqueda()` mantiene una lista de diccionarios `SeriesInfos`. Ambos emiten
`DeprecationWarning`. La única excepción de compatibilidad es la autenticación histórica por
usuario/contraseña, rechazada localmente por seguridad.

## Manejo de errores

```python
from bcch import (
    BCCHAPIError,
    BCCHAuthenticationError,
    BCCHConnectionError,
    BCCHResponseError,
    BCCHTimeoutError,
)

try:
    client.get_series("F073.TCO.PRE.Z.D")
except BCCHAuthenticationError:
    print("Revise el API Key Token")
except BCCHTimeoutError:
    print("La consulta excedió el timeout")
except BCCHConnectionError:
    print("No fue posible conectar con el servicio")
except BCCHAPIError as exc:
    print(exc.code, exc.description)
except BCCHResponseError:
    print("La respuesta no respetó el contrato esperado")
```

El transporte usa `requests.Session`, reintentos acotados solo para fallas transitorias y
validación de `Codigo` y `Descripcion`; HTTP 200 no basta para considerar exitosa una
operación. Los mensajes no incluyen el token.

## Actualizar el catálogo

```bash
python scripts/update_catalog.py /ruta/al/catalogo-oficial.xlsx
```

El script valida hoja, columnas e invariantes del snapshot autorizado. Conserva todas las
filas y produce `catalog.csv.gz` y `catalog_metadata.json` deterministas. Las URL de ejemplo
se reconstruyen con el marcador `TOKEN`, sin copiar credenciales del XLSX. El XLSX original
no forma parte del paquete.

## Desarrollo

```bash
ruff check .
pytest
python -m build
```

CI ejecuta estas validaciones en Python 3.11, 3.12, 3.13 y 3.14. No existe workflow de
publicación a PyPI y las pruebas normales no requieren credenciales.

## Fuente de datos, términos y licencia

Fuente de los datos y metadatos: **Banco Central de Chile, Base de Datos Estadísticos (BDE)**.
Consulte la [documentación REST oficial](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/documentacion.html),
la [ayuda y soporte](https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/ayuda_soporte.html)
y los términos de uso de la BDE antes de redistribuir resultados.

Los datos pertenecen a sus fuentes originales. Este software no ofrece asesoría financiera,
legal, tributaria ni económica.

El código conserva la autoría original de Lautaro Parada Opazo y se distribuye bajo
Apache License 2.0. Consulte [LICENSE](LICENSE).
