"""Unofficial Python client for the Banco Central de Chile BDE REST API."""

from .catalog import SeriesCatalog, SeriesCatalogContext, SeriesCatalogEntry
from .client import BancoCentralDeChile
from .exceptions import (
    BCCHAPIError,
    BCCHAuthenticationError,
    BCCHConnectionError,
    BCCHError,
    BCCHHTTPError,
    BCCHLegacyAuthenticationError,
    BCCHRateLimitError,
    BCCHResponseError,
    BCCHTimeoutError,
)
from .models import Observation, SeriesInfo, SeriesResult

__all__ = [
    "BCCHAPIError",
    "BCCHAuthenticationError",
    "BCCHConnectionError",
    "BCCHError",
    "BCCHHTTPError",
    "BCCHLegacyAuthenticationError",
    "BCCHRateLimitError",
    "BCCHResponseError",
    "BCCHTimeoutError",
    "BancoCentralDeChile",
    "Observation",
    "SeriesCatalog",
    "SeriesCatalogContext",
    "SeriesCatalogEntry",
    "SeriesInfo",
    "SeriesResult",
]

__version__ = "1.0.0.dev0"
