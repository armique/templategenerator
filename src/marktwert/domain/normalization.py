"""Deterministic, versioned computer-hardware title normalization."""

import re
import unicodedata
from enum import StrEnum

from marktwert.domain.sales.observation import ProductSnapshot

NORMALIZATION_VERSION = "hardware-rules-1"
MAXIMUM_CONFIDENCE = 9_800
MODEL_CONFIDENCE = 5_500
BRAND_CONFIDENCE = 2_000
ATTRIBUTE_CONFIDENCE = 500
BASE_CONFIDENCE = 1_000
TERABYTE_IN_GIGABYTES = 1_000

BRANDS: tuple[tuple[str, str], ...] = (
    ("gigabyte", "Gigabyte"),
    ("asus", "ASUS"),
    ("asrock", "ASRock"),
    ("corsair", "Corsair"),
    ("crucial", "Crucial"),
    ("kingston", "Kingston"),
    ("samsung", "Samsung"),
    ("western digital", "Western Digital"),
    ("wd", "Western Digital"),
    ("seagate", "Seagate"),
    ("be quiet", "be quiet!"),
    ("seasonic", "Seasonic"),
    ("sapphire", "Sapphire"),
    ("powercolor", "PowerColor"),
    ("palit", "Palit"),
    ("zotac", "Zotac"),
    ("gainward", "Gainward"),
    ("intel", "Intel"),
    ("amd", "AMD"),
    ("msi", "MSI"),
    ("xfx", "XFX"),
)


class HardwareCategory(StrEnum):
    """Canonical hardware categories produced by deterministic rules."""

    UNKNOWN = "unknown"
    GPU = "gpu"
    CPU = "cpu"
    MOTHERBOARD = "motherboard"
    RAM = "ram"
    STORAGE = "storage"
    POWER_SUPPLY = "power_supply"


class HardwareTitleNormalizer:
    """Extract stable hardware identity without inventing missing facts."""

    def normalize(
        self,
        title: str,
        *,
        source: ProductSnapshot | None = None,
    ) -> ProductSnapshot:
        """Normalize one title while preserving explicit source attributes."""
        source = source or ProductSnapshot()
        normalized_text = _normalize_text(title)
        evidence: list[str] = []

        detected_brand = _detect_brand(normalized_text)
        brand = source.brand or detected_brand
        if detected_brand is not None:
            evidence.append(f"brand:{detected_brand}:dictionary")

        model, detected_category = _detect_model(normalized_text)
        model = source.model or model
        category = source.category or detected_category.value
        if model is not None:
            evidence.append(f"model:{model}:pattern")

        chipset = source.chipset or _extract_chipset(normalized_text)
        socket = source.socket or _extract_socket(normalized_text)
        revision = source.revision or _extract_revision(normalized_text)
        clock_speed = source.clock_speed_mhz or _extract_clock(normalized_text)
        capacity = _extract_capacity_gb(normalized_text)
        ram_capacity = source.ram_capacity_gb
        memory_size = source.memory_size_gb
        storage_size = source.storage_size_gb
        if category == HardwareCategory.RAM.value:
            ram_capacity = ram_capacity or capacity
        elif category == HardwareCategory.GPU.value:
            memory_size = memory_size or capacity
        elif category == HardwareCategory.STORAGE.value:
            storage_size = storage_size or _extract_storage_gb(normalized_text)

        extracted_attributes = {
            "chipset": chipset,
            "socket": socket,
            "revision": revision,
            "clock_speed_mhz": clock_speed,
            "ram_capacity_gb": ram_capacity,
            "memory_size_gb": memory_size,
            "storage_size_gb": storage_size,
        }
        evidence.extend(
            f"{name}:{value}:pattern"
            for name, value in extracted_attributes.items()
            if value is not None
        )
        normalized_title = _build_normalized_title(
            original=title,
            normalized_text=normalized_text,
            brand=brand,
            model=model,
            chipset=chipset,
        )
        confidence = BASE_CONFIDENCE
        if model is not None:
            confidence += MODEL_CONFIDENCE
        if brand is not None:
            confidence += BRAND_CONFIDENCE
        confidence += ATTRIBUTE_CONFIDENCE * len(
            _extracted_attributes_with_values(extracted_attributes)
        )

        return ProductSnapshot(
            normalized_title=normalized_title,
            brand=brand,
            model=model,
            part_number=source.part_number,
            category=category,
            chipset=chipset,
            ram_capacity_gb=ram_capacity,
            clock_speed_mhz=clock_speed,
            socket=socket,
            revision=revision,
            memory_size_gb=memory_size,
            storage_size_gb=storage_size,
            normalization_confidence=min(confidence, MAXIMUM_CONFIDENCE),
            normalization_version=NORMALIZATION_VERSION,
            normalization_evidence=tuple(evidence),
        )


def _extracted_attributes_with_values(
    attributes: dict[str, str | int | None],
) -> tuple[str | int, ...]:
    return tuple(value for value in attributes.values() if value is not None)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\b(rtx|gtx|rx|ddr|rev)(?=\d)", r"\1 ", normalized)
    return " ".join(re.sub(r"[^\w.+/-]+", " ", normalized).split())


def _detect_brand(value: str) -> str | None:
    padded = f" {value} "
    for token, canonical in BRANDS:
        if f" {token} " in padded:
            return canonical
    return None


def _detect_model(value: str) -> tuple[str | None, HardwareCategory]:
    detected = _detect_gpu_model(value) or _detect_cpu_model(value)
    if detected is not None:
        return detected
    chipset = _extract_chipset(value)
    model: str | None = None
    category = HardwareCategory.UNKNOWN
    if chipset is not None:
        model, category = chipset, HardwareCategory.MOTHERBOARD
    elif re.search(r"\bddr\s*[345]\b", value):
        model, category = _extract_ddr(value), HardwareCategory.RAM
    elif re.search(r"\b(?:ssd|nvme|hdd)\b", value):
        model, category = _extract_storage_model(value), HardwareCategory.STORAGE
    elif re.search(r"\b\d{3,4}\s*w\b", value):
        model, category = _extract_power_model(value), HardwareCategory.POWER_SUPPLY
    return model, category


def _detect_gpu_model(value: str) -> tuple[str, HardwareCategory] | None:
    nvidia = re.search(
        r"\b(?:geforce\s+)?(rtx|gtx)\s*(\d{3,4})(?:\s*(ti|super))?\b",
        value,
    )
    if nvidia:
        suffix = f" {nvidia.group(3).title()}" if nvidia.group(3) else ""
        return (
            f"{nvidia.group(1).upper()} {nvidia.group(2)}{suffix}",
            HardwareCategory.GPU,
        )

    radeon = re.search(r"\b(?:radeon\s+)?rx\s*(\d{3,4})(?:\s*(xt|xtx))?\b", value)
    if radeon:
        suffix = f" {radeon.group(2).upper()}" if radeon.group(2) else ""
        return f"RX {radeon.group(1)}{suffix}", HardwareCategory.GPU
    return None


def _detect_cpu_model(value: str) -> tuple[str, HardwareCategory] | None:
    ryzen = re.search(r"\bryzen\s*(?:(3|5|7|9)\s*)?(\d{4}[a-z0-9]{0,3})\b", value)
    if ryzen:
        tier = f" {ryzen.group(1)}" if ryzen.group(1) else ""
        return f"Ryzen{tier} {ryzen.group(2).upper()}", HardwareCategory.CPU

    intel = re.search(r"\bi\s*([3579])[-\s]*(\d{4,5})([a-z]{0,2})\b", value)
    if intel:
        return (
            f"i{intel.group(1)}-{intel.group(2)}{intel.group(3).upper()}",
            HardwareCategory.CPU,
        )
    return None


def _extract_chipset(value: str) -> str | None:
    match = re.search(r"\b([abchxz])\s*[-]?\s*(\d{3})\b", value)
    return f"{match.group(1).upper()}{match.group(2)}" if match else None


def _extract_socket(value: str) -> str | None:
    match = re.search(r"\b(am[45]|lga\s*\d{4})\b", value)
    return match.group(1).replace(" ", "").upper() if match else None


def _extract_revision(value: str) -> str | None:
    match = re.search(r"\b(?:rev(?:ision)?\.?\s*)(\d+(?:\.\d+)?)\b", value)
    return f"Rev {match.group(1)}" if match else None


def _extract_clock(value: str) -> int | None:
    match = re.search(r"\b(\d{3,5})\s*(?:mhz|mt/s)\b", value)
    return int(match.group(1)) if match else None


def _extract_capacity_gb(value: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*gb\b", value)
    return int(match.group(1)) if match else None


def _extract_storage_gb(value: str) -> int | None:
    terabytes = re.search(r"\b(\d+(?:[.,]\d+)?)\s*tb\b", value)
    if terabytes:
        amount = float(terabytes.group(1).replace(",", "."))
        return round(amount * TERABYTE_IN_GIGABYTES)
    return _extract_capacity_gb(value)


def _extract_ddr(value: str) -> str:
    match = re.search(r"\bddr\s*([345])\b", value)
    return f"DDR{match.group(1)}" if match else "RAM"


def _extract_storage_model(value: str) -> str:
    match = re.search(r"\b(nvme|ssd|hdd)\b", value)
    return match.group(1).upper() if match else "Storage"


def _extract_power_model(value: str) -> str:
    match = re.search(r"\b(\d{3,4})\s*w\b", value)
    return f"{match.group(1)}W" if match else "Power Supply"


def _build_normalized_title(
    *,
    original: str,
    normalized_text: str,
    brand: str | None,
    model: str | None,
    chipset: str | None,
) -> str:
    parts: list[str] = []
    if brand is not None:
        parts.append(brand)
    if model is not None:
        parts.append(model)
    elif chipset is not None:
        parts.append(chipset)
    for token, canonical in (("gaming", "Gaming"), ("oc", "OC")):
        if re.search(rf"\b{token}\b", normalized_text):
            parts.append(canonical)
    return " ".join(dict.fromkeys(parts)) if parts else " ".join(original.split())
