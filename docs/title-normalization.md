# Hardware Title Normalization

MarktWert applies a deterministic, versioned normalization pipeline during
preview and import. Original titles remain unchanged and auditable.

The first rule version detects:

- GPU families such as RTX, GTX, and Radeon RX;
- AMD Ryzen and Intel Core-style CPU models;
- motherboard chipsets and AM4/AM5/LGA sockets;
- DDR generation, RAM capacity, and clock speed;
- SSD/NVMe/HDD capacity;
- power-supply wattage;
- brand, revision, GPU memory, and source part number.

Each product snapshot stores a normalized display title, canonical category and
model, extracted attributes, rule version, confidence in basis points, and
evidence strings. Source-provided facts take precedence over inferred facts.
Rules never invent an `OC`, memory size, revision, or other qualifier that is
not supported by source evidence.

For example:

```text
Gigabyte RTX3070 Gaming OC Rev2
→ Gigabyte RTX 3070 Gaming OC
  model=RTX 3070, revision=Rev 2
```

Normalization is separate from listing classification. A title can have a
correct hardware identity while still being excluded as faulty, packaging-only,
or accessory-only.
