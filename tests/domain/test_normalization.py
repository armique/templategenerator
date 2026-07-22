"""Fixture tests for deterministic computer-hardware title normalization."""

import pytest

from marktwert.domain.normalization import (
    NORMALIZATION_VERSION,
    HardwareCategory,
    HardwareTitleNormalizer,
)


@pytest.mark.parametrize(
    ("title", "brand", "model", "normalized_title"),
    [
        (
            "Gigabyte RTX3070 Gaming OC Rev2",
            "Gigabyte",
            "RTX 3070",
            "Gigabyte RTX 3070 Gaming OC",
        ),
        (
            "RTX3070 Gigabyte Gaming",
            "Gigabyte",
            "RTX 3070",
            "Gigabyte RTX 3070 Gaming",
        ),
        (
            "Gigabyte GeForce RTX 3070 OC",
            "Gigabyte",
            "RTX 3070",
            "Gigabyte RTX 3070 OC",
        ),
        ("AMD Ryzen 5700X", "AMD", "Ryzen 5700X", "AMD Ryzen 5700X"),
        ("Intel i7-12700K", "Intel", "i7-12700K", "Intel i7-12700K"),
    ],
)
def test_normalizer_canonicalizes_common_gpu_and_cpu_titles(
    title: str,
    brand: str,
    model: str,
    normalized_title: str,
) -> None:
    result = HardwareTitleNormalizer().normalize(title)

    assert result.brand == brand
    assert result.model == model
    assert result.normalized_title == normalized_title
    assert result.normalization_version == NORMALIZATION_VERSION
    assert result.normalization_confidence is not None
    assert result.normalization_confidence >= 8_000


def test_normalizer_extracts_ram_attributes() -> None:
    result = HardwareTitleNormalizer().normalize(
        "Corsair DDR5 32GB 6000MHz CL36"
    )

    assert result.category == HardwareCategory.RAM.value
    assert result.model == "DDR5"
    assert result.ram_capacity_gb == 32
    assert result.clock_speed_mhz == 6000


def test_normalizer_extracts_motherboard_socket_and_chipset() -> None:
    result = HardwareTitleNormalizer().normalize(
        "ASUS ROG Strix Z790 Gaming LGA1700"
    )

    assert result.category == HardwareCategory.MOTHERBOARD.value
    assert result.chipset == "Z790"
    assert result.socket == "LGA1700"


def test_normalizer_converts_storage_terabytes_to_gigabytes() -> None:
    result = HardwareTitleNormalizer().normalize("Samsung 1TB NVMe SSD")

    assert result.category == HardwareCategory.STORAGE.value
    assert result.storage_size_gb == 1000
    assert result.normalized_title == "Samsung NVME"
