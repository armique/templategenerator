"""Validation and normalization of external completed-sales rows."""

import hashlib
import json
import math
import re
from collections.abc import Collection, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from marktwert.application.imports.models import ImportIssueCode, RawSalesRow
from marktwert.domain.money import Money
from marktwert.domain.sales import (
    ItemCondition,
    ListingFormat,
    ProductSnapshot,
    SaleObservation,
    SellerSnapshot,
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "external_item_id": (
        "item_id",
        "itemid",
        "ebay_item_id",
        "artikelnummer",
        "artikel_id",
    ),
    "title": ("title", "titel", "artikelbezeichnung"),
    "sold_price": ("sold_price", "verkaufspreis", "price", "preis"),
    "shipping_price": (
        "shipping_price",
        "shipping",
        "shipping_cost",
        "versand",
        "versandkosten",
    ),
    "sold_at": (
        "sold_at",
        "sold_date",
        "sale_date",
        "date_sold",
        "verkauft_am",
        "verkaufsdatum",
    ),
    "currency": ("currency", "währung", "waehrung"),
    "condition": ("condition", "zustand"),
    "listing_format": (
        "listing_format",
        "listing_type",
        "format",
        "angebotsformat",
    ),
    "best_offer": ("best_offer", "preisvorschlag"),
    "bid_count": ("bid_count", "bids", "gebote"),
    "listing_url": ("listing_url", "url", "artikel_url"),
    "thumbnail_url": ("thumbnail_url", "thumbnail", "bild_url"),
    "location": ("location", "standort"),
    "seller_name": ("seller", "seller_name", "verkäufer", "verkaeufer"),
    "seller_feedback_percentage": (
        "seller_rating",
        "seller_feedback_percentage",
        "verkäuferbewertung",
        "verkaeuferbewertung",
    ),
    "seller_feedback_count": (
        "seller_feedback_count",
        "feedback_count",
        "bewertungen",
    ),
    "brand": ("brand", "marke", "hersteller"),
    "model": ("model", "modell"),
    "part_number": ("part_number", "mpn", "teilenummer"),
    "category": ("category", "kategorie"),
}
REQUIRED_FIELDS = frozenset(
    {"external_item_id", "title", "sold_price", "sold_at"}
)
DATE_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


class RowValidationError(ValueError):
    """Identify a user-correctable validation problem in one source row."""

    def __init__(self, code: ImportIssueCode, message: str) -> None:
        """Store a stable issue code with a safe message."""
        super().__init__(message)
        self.code = code


class SalesRowMapper:
    """Convert supported English/German columns into a sale observation."""

    def __init__(self, default_timezone: str) -> None:
        """Resolve the timezone used for source dates without offsets."""
        try:
            self._timezone = ZoneInfo(default_timezone)
        except ZoneInfoNotFoundError as error:
            message = f"unknown import timezone: {default_timezone}"
            raise ValueError(message) from error

    def missing_required_fields(
        self,
        headers: Collection[str],
    ) -> tuple[str, ...]:
        """Return canonical required fields absent from the source schema."""
        return tuple(
            sorted(
                field_name
                for field_name in REQUIRED_FIELDS
                if not any(
                    alias in headers for alias in FIELD_ALIASES[field_name]
                )
            )
        )

    def map(
        self,
        row: RawSalesRow,
        *,
        source: str,
        acquired_at: datetime,
    ) -> SaleObservation:
        """Validate and map one source row."""
        if all(_is_blank(value) for value in row.values.values()):
            raise RowValidationError(ImportIssueCode.EMPTY_ROW, "row is empty")

        currency = _optional_text(_value(row.values, "currency")) or "EUR"
        currency = currency.upper()
        return SaleObservation(
            source=source,
            external_item_id=_required_text(row.values, "external_item_id"),
            title=_required_text(row.values, "title"),
            sold_price=_parse_money(
                _required_value(row.values, "sold_price"),
                currency,
                field_name="sold_price",
            ),
            shipping_price=_parse_optional_money(
                _value(row.values, "shipping_price"),
                currency,
            ),
            sold_at=_parse_datetime(
                _required_value(row.values, "sold_at"),
                self._timezone,
            ),
            acquired_at=acquired_at,
            raw_record_hash=_record_hash(row.values),
            condition=_parse_condition(_value(row.values, "condition")),
            listing_format=_parse_listing_format(
                _value(row.values, "listing_format")
            ),
            best_offer=_parse_optional_bool(_value(row.values, "best_offer")),
            bid_count=_parse_optional_nonnegative_int(
                _value(row.values, "bid_count"),
                field_name="bid_count",
            ),
            listing_url=_optional_text(_value(row.values, "listing_url")),
            thumbnail_url=_optional_text(_value(row.values, "thumbnail_url")),
            location=_optional_text(_value(row.values, "location")),
            seller=SellerSnapshot(
                name=_optional_text(_value(row.values, "seller_name")),
                feedback_percentage=_parse_optional_percentage(
                    _value(row.values, "seller_feedback_percentage")
                ),
                feedback_count=_parse_optional_nonnegative_int(
                    _value(row.values, "seller_feedback_count"),
                    field_name="seller_feedback_count",
                ),
            ),
            product=ProductSnapshot(
                brand=_optional_text(_value(row.values, "brand")),
                model=_optional_text(_value(row.values, "model")),
                part_number=_optional_text(_value(row.values, "part_number")),
                category=_optional_text(_value(row.values, "category")),
            ),
        )


def _value(
    values: Mapping[str, object | None],
    canonical_name: str,
) -> object | None:
    for alias in FIELD_ALIASES[canonical_name]:
        if alias in values:
            return values[alias]
    return None


def _required_value(
    values: Mapping[str, object | None],
    canonical_name: str,
) -> object:
    value = _value(values, canonical_name)
    if _is_blank(value):
        message = f"{canonical_name} is required"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message)
    return value


def _required_text(
    values: Mapping[str, object | None],
    canonical_name: str,
) -> str:
    return str(_required_value(values, canonical_name)).strip()


def _optional_text(value: object | None) -> str | None:
    return None if _is_blank(value) else str(value).strip()


def _is_blank(value: object | None) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _parse_money(value: object, currency: str, *, field_name: str) -> Money:
    try:
        amount = _parse_decimal(value)
        return Money.from_major_units(amount, currency)
    except (InvalidOperation, ValueError) as error:
        message = f"{field_name} is not a valid monetary amount"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message) from error


def _parse_optional_money(value: object | None, currency: str) -> Money | None:
    if _is_blank(value):
        return None
    return _parse_money(value, currency, field_name="shipping_price")


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError
    if isinstance(value, int | Decimal):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError
        return Decimal(str(value))

    text = str(value).strip().casefold()
    text = text.replace("\u00a0", "").replace(" ", "")
    text = text.replace("eur", "").replace("€", "").replace("'", "")
    if not text or re.search(r"[^\d,.\-+]", text):
        raise ValueError
    return Decimal(_normalize_decimal_separators(text))


def _normalize_decimal_separators(value: str) -> str:
    if "," in value and "." in value:
        decimal_separator = "," if value.rfind(",") > value.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        return value.replace(thousands_separator, "").replace(decimal_separator, ".")

    separator = "," if "," in value else "." if "." in value else None
    if separator is None:
        return value
    parts = value.split(separator)
    if len(parts) > 2:
        decimal_digits = parts[-1]
        if len(decimal_digits) in {1, 2}:
            return "".join(parts[:-1]) + "." + decimal_digits
        return "".join(parts)
    whole, decimal_digits = parts
    if len(decimal_digits) in {1, 2}:
        return f"{whole}.{decimal_digits}"
    return whole + decimal_digits


def _parse_datetime(value: object, timezone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = _parse_formatted_datetime(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(UTC)


def _parse_formatted_datetime(value: str) -> datetime:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    message = "sold_at is not a supported date"
    raise RowValidationError(ImportIssueCode.INVALID_VALUE, message)


def _parse_condition(value: object | None) -> ItemCondition | None:
    normalized = (_optional_text(value) or "").casefold()
    if not normalized:
        return None
    mapping = {
        "new": ItemCondition.NEW,
        "neu": ItemCondition.NEW,
        "used": ItemCondition.USED,
        "gebraucht": ItemCondition.USED,
    }
    return mapping.get(normalized)


def _parse_listing_format(value: object | None) -> ListingFormat | None:
    normalized = (_optional_text(value) or "").casefold()
    if not normalized:
        return None
    mapping = {
        "auction": ListingFormat.AUCTION,
        "auktion": ListingFormat.AUCTION,
        "buy it now": ListingFormat.BUY_IT_NOW,
        "buy_it_now": ListingFormat.BUY_IT_NOW,
        "sofort-kaufen": ListingFormat.BUY_IT_NOW,
        "sofort kaufen": ListingFormat.BUY_IT_NOW,
    }
    return mapping.get(normalized)


def _parse_optional_bool(value: object | None) -> bool | None:
    if _is_blank(value):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "ja"}:
        return True
    if normalized in {"0", "false", "no", "nein"}:
        return False
    message = "best_offer is not a valid boolean"
    raise RowValidationError(ImportIssueCode.INVALID_VALUE, message)


def _parse_optional_nonnegative_int(
    value: object | None,
    *,
    field_name: str,
) -> int | None:
    if _is_blank(value):
        return None
    try:
        parsed = int(str(value).strip())
    except ValueError as error:
        message = f"{field_name} is not a valid integer"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message) from error
    if parsed < 0:
        message = f"{field_name} cannot be negative"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message)
    return parsed


def _parse_optional_percentage(value: object | None) -> Decimal | None:
    if _is_blank(value):
        return None
    try:
        normalized_value = (
            value.replace("%", "") if isinstance(value, str) else value
        )
        percentage = _parse_decimal(normalized_value)
    except (InvalidOperation, ValueError) as error:
        message = "seller_rating is not a valid percentage"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message) from error
    if not Decimal(0) <= percentage <= Decimal(100):
        message = "seller_rating must be between 0 and 100"
        raise RowValidationError(ImportIssueCode.INVALID_VALUE, message)
    return percentage


def _record_hash(values: Mapping[str, object | None]) -> str:
    canonical = json.dumps(
        values,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
