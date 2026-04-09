"""Serialize and deserialize CS2 masked inspect links.

Binary format:
    [key_byte] [proto_bytes XOR'd with key] [4-byte checksum XOR'd with key]

For tool-generated links key_byte = 0x00 (no XOR needed).
For native CS2 links key_byte != 0x00 — every subsequent byte must be XOR'd.

Checksum algorithm:
    crc = crc32(buffer)           where buffer = [0x00] + proto_bytes (before XOR)
    xored = (crc & 0xffff) ^ (len(proto_bytes) * crc)   (unsigned 32-bit arithmetic)
    checksum = big-endian uint32 of (xored & 0xFFFFFFFF)
"""

from __future__ import annotations

import binascii
import re
import struct
import zlib
from typing import Union

from .models import ItemPreviewData
from .proto import decode_item, encode_item


# Regex to extract the hex payload from a full steam:// or CS2 inspect URL.
# The payload is always preceded by a literal 'A' which follows a space (%20, + or literal).
_INSPECT_URL_RE = re.compile(
    r"(?:%20|\s|\+)A([0-9A-Fa-f]+)",
    re.IGNORECASE,
)

# Hybrid: S/A/D prefix with hex proto after D
_HYBRID_URL_RE = re.compile(
    r'S\d+A\d+D([0-9A-Fa-f]+)$',
    re.IGNORECASE,
)

_CLASSIC_URL_RE = re.compile(
    r'csgo_econ_action_preview(?:%20|\s)[SM]\d+A\d+D\d+$',
    re.IGNORECASE,
)

_MASKED_URL_RE = re.compile(
    r'csgo_econ_action_preview(?:%20|\s)%?[0-9A-Fa-f]{10,}$',
    re.IGNORECASE,
)


def _extract_hex(hex_or_url: str) -> str:
    """Return the raw hex string from either a bare hex or a full inspect URL."""
    stripped = hex_or_url.strip()

    # Hybrid format: S\d+A\d+D<hexproto>
    m = _HYBRID_URL_RE.search(stripped)
    if m and re.search(r'[A-Fa-f]', m.group(1)):
        return m.group(1)

    # Classic/market URL: A<hex> preceded by %20, space, or + (A is a prefix marker, not hex).
    # If stripping A yields odd-length hex, A is actually the first byte of the payload —
    # fall through to the pure-masked check below which captures it with A included.
    m = _INSPECT_URL_RE.search(stripped)
    if m and len(m.group(1)) % 2 == 0:
        return m.group(1)

    # Pure masked format: csgo_econ_action_preview%20<hexblob> (no S/A/M prefix).
    # Also handles payloads whose first hex character happens to be A.
    mm = re.search(r'csgo_econ_action_preview(?:%20|\s|\+)%?([0-9A-Fa-f]{10,})$', stripped, re.IGNORECASE)
    if mm:
        return mm.group(1)

    # Bare hex — remove any whitespace
    return re.sub(r"\s+", "", stripped)


def is_masked(link: str) -> bool:
    """Return True if the link contains a decodable protobuf payload (offline)."""
    stripped = link.strip()
    if _MASKED_URL_RE.search(stripped):
        return True
    m = _HYBRID_URL_RE.search(stripped)
    if m and re.search(r'[A-Fa-f]', m.group(1)):
        return True
    return False


def is_classic(link: str) -> bool:
    """Return True if the link is a classic S/A/D inspect URL with decimal did."""
    return bool(_CLASSIC_URL_RE.search(link.strip()))


def _crc32_checksum(buffer: bytes, proto_len: int) -> bytes:
    """Compute the 4-byte big-endian checksum appended to the link payload."""
    crc = zlib.crc32(buffer) & 0xFFFFFFFF
    xored = ((crc & 0xFFFF) ^ (proto_len * crc)) & 0xFFFFFFFF
    return struct.pack(">I", xored)


def serialize(data: ItemPreviewData) -> str:
    """Encode an ItemPreviewData to an uppercase hex inspect-link payload.

    The returned string can be embedded into a steam:// inspect URL or used
    standalone. key_byte is always 0x00 (no XOR applied).

    Returns:
        Uppercase hex string, e.g. "00183C20B803..."
    """
    if data.paintwear is not None and (data.paintwear < 0.0 or data.paintwear > 1.0):
        raise ValueError(
            f"paintwear must be in [0.0, 1.0], got {data.paintwear}"
        )
    if data.customname is not None and len(data.customname) > 100:
        raise ValueError(
            f"customname must not exceed 100 characters, got {len(data.customname)}"
        )
    proto_bytes = encode_item(data)
    buffer = b"\x00" + proto_bytes
    checksum = _crc32_checksum(buffer, len(proto_bytes))
    payload = buffer + checksum
    return binascii.hexlify(payload).decode("ascii").upper()


def deserialize(hex_or_url: str) -> ItemPreviewData:
    """Decode an inspect-link hex payload (or full URL) into an ItemPreviewData.

    Accepts:
        - A raw uppercase or lowercase hex string
        - A full steam://rungame/... inspect URL
        - A CS2-style csgo://rungame/... URL

    The function handles the XOR obfuscation used in native CS2 links
    (where the first byte is the XOR key applied to all subsequent bytes).
    """
    hex_str = _extract_hex(hex_or_url)
    if len(hex_str) > 4096:
        raise ValueError(
            f"Payload too long (max 4096 hex chars): {hex_or_url[:64]!r}..."
        )
    raw = binascii.unhexlify(hex_str)

    if len(raw) < 6:
        raise ValueError(f"Payload too short: {len(raw)} bytes")

    key = raw[0]

    if key == 0:
        # No XOR — most common case for tool-generated links
        decrypted = raw
    else:
        decrypted = bytes(b ^ key for b in raw)

    # Layout: [key] [proto_bytes...] [4-byte checksum]
    proto_bytes = decrypted[1:-4]

    return decode_item(proto_bytes)
