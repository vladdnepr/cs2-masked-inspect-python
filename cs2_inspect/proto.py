"""Pure Python protobuf binary encoder and decoder.

No external dependencies. Implements only the wire types needed for
CEconItemPreviewDataBlock and the nested Sticker message:
  - Varint (wire type 0): uint32, uint64, int32
  - 32-bit (wire type 5): float32 (fixed32)
  - Length-delimited (wire type 2): string, bytes, nested message
"""

from __future__ import annotations

import struct
from typing import Any


# ---------------------------------------------------------------------------
# Wire types
# ---------------------------------------------------------------------------
WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LEN = 2
WIRE_32BIT = 5


# ---------------------------------------------------------------------------
# Low-level reading helpers
# ---------------------------------------------------------------------------

class ProtoReader:
    """Reads protobuf fields from a bytes buffer."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    @property
    def pos(self) -> int:
        return self._pos

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def read_byte(self) -> int:
        if self._pos >= len(self._data):
            raise EOFError("Unexpected end of protobuf data")
        b = self._data[self._pos]
        self._pos += 1
        return b

    def read_bytes(self, n: int) -> bytes:
        if self._pos + n > len(self._data):
            raise EOFError(f"Need {n} bytes but only {len(self._data) - self._pos} remain")
        chunk = self._data[self._pos: self._pos + n]
        self._pos += n
        return chunk

    def read_varint(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.read_byte()
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
            if shift >= 64:
                raise ValueError("Varint too long")
        return result

    def read_tag(self) -> tuple[int, int]:
        """Return (field_number, wire_type)."""
        tag = self.read_varint()
        return tag >> 3, tag & 0x07

    def read_float32(self) -> float:
        raw = self.read_bytes(4)
        return struct.unpack("<f", raw)[0]

    def read_length_delimited(self) -> bytes:
        length = self.read_varint()
        return self.read_bytes(length)

    def read_all_fields(self) -> list[tuple[int, int, Any]]:
        """Read all (field_number, wire_type, value) tuples until EOF."""
        fields: list[tuple[int, int, Any]] = []
        field_count = 0
        while self.remaining() > 0:
            field_count += 1
            if field_count > 100:
                raise ValueError("Protobuf field count exceeds limit of 100")
            field_num, wire_type = self.read_tag()
            if wire_type == WIRE_VARINT:
                value = self.read_varint()
            elif wire_type == WIRE_64BIT:
                value = self.read_bytes(8)
            elif wire_type == WIRE_LEN:
                value = self.read_length_delimited()
            elif wire_type == WIRE_32BIT:
                value = self.read_bytes(4)
            else:
                raise ValueError(f"Unknown wire type {wire_type} for field {field_num}")
            fields.append((field_num, wire_type, value))
        return fields


# ---------------------------------------------------------------------------
# Low-level writing helpers
# ---------------------------------------------------------------------------

class ProtoWriter:
    """Writes protobuf fields to an in-memory buffer."""

    def __init__(self) -> None:
        self._buf: list[bytes] = []

    def to_bytes(self) -> bytes:
        return b"".join(self._buf)

    def _write_varint(self, value: int) -> None:
        if value < 0:
            # Encode as 64-bit two's complement for negative ints
            value = value & 0xFFFFFFFFFFFFFFFF
        parts = []
        while True:
            b = value & 0x7F
            value >>= 7
            if value:
                parts.append(b | 0x80)
            else:
                parts.append(b)
                break
        self._buf.append(bytes(parts))

    def _write_tag(self, field_num: int, wire_type: int) -> None:
        self._write_varint((field_num << 3) | wire_type)

    def write_uint32(self, field_num: int, value: int) -> None:
        if value == 0:
            return
        self._write_tag(field_num, WIRE_VARINT)
        self._write_varint(value)

    def write_uint64(self, field_num: int, value: int) -> None:
        if value == 0:
            return
        self._write_tag(field_num, WIRE_VARINT)
        self._write_varint(value)

    def write_int32(self, field_num: int, value: int) -> None:
        if value == 0:
            return
        self._write_tag(field_num, WIRE_VARINT)
        self._write_varint(value)

    def write_string(self, field_num: int, value: str) -> None:
        if not value:
            return
        encoded = value.encode("utf-8")
        self._write_tag(field_num, WIRE_LEN)
        self._write_varint(len(encoded))
        self._buf.append(encoded)

    def write_float32_fixed(self, field_num: int, value: float) -> None:
        """Write a float32 as wire type 5 (fixed 32-bit)."""
        self._write_tag(field_num, WIRE_32BIT)
        self._buf.append(struct.pack("<f", value))

    def write_bytes(self, field_num: int, data: bytes) -> None:
        if not data:
            return
        self._write_tag(field_num, WIRE_LEN)
        self._write_varint(len(data))
        self._buf.append(data)

    def write_embedded(self, field_num: int, writer: "ProtoWriter") -> None:
        """Write a nested message."""
        data = writer.to_bytes()
        self.write_bytes(field_num, data)


# ---------------------------------------------------------------------------
# CEconItemPreviewDataBlock encode / decode
# ---------------------------------------------------------------------------

def float32_to_uint32(f: float) -> int:
    """Reinterpret a float32 as its raw IEEE 754 uint32 bit pattern."""
    return struct.unpack("<I", struct.pack("<f", f))[0]


def uint32_to_float32(u: int) -> float:
    """Reinterpret a raw uint32 IEEE 754 bit pattern as float32."""
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def encode_sticker(s: "Sticker") -> bytes:  # noqa: F821  (forward ref ok)
    from .models import Sticker
    w = ProtoWriter()
    w.write_uint32(1, s.slot)
    w.write_uint32(2, s.sticker_id)
    if s.wear is not None:
        w.write_float32_fixed(3, s.wear)
    if s.scale is not None:
        w.write_float32_fixed(4, s.scale)
    if s.rotation is not None:
        w.write_float32_fixed(5, s.rotation)
    w.write_uint32(6, s.tint_id)
    if s.offset_x is not None:
        w.write_float32_fixed(7, s.offset_x)
    if s.offset_y is not None:
        w.write_float32_fixed(8, s.offset_y)
    if s.offset_z is not None:
        w.write_float32_fixed(9, s.offset_z)
    w.write_uint32(10, s.pattern)
    if s.highlight_reel is not None:
        w.write_uint32(11, s.highlight_reel)
    if s.paint_kit is not None:
        w.write_uint32(12, s.paint_kit)
    return w.to_bytes()


def decode_sticker(data: bytes) -> "Sticker":  # noqa: F821
    from .models import Sticker
    reader = ProtoReader(data)
    s = Sticker()
    for field_num, wire_type, value in reader.read_all_fields():
        if field_num == 1:
            s.slot = value
        elif field_num == 2:
            s.sticker_id = value
        elif field_num == 3:
            s.wear = struct.unpack("<f", value)[0]
        elif field_num == 4:
            s.scale = struct.unpack("<f", value)[0]
        elif field_num == 5:
            s.rotation = struct.unpack("<f", value)[0]
        elif field_num == 6:
            s.tint_id = value
        elif field_num == 7:
            s.offset_x = struct.unpack("<f", value)[0]
        elif field_num == 8:
            s.offset_y = struct.unpack("<f", value)[0]
        elif field_num == 9:
            s.offset_z = struct.unpack("<f", value)[0]
        elif field_num == 10:
            s.pattern = value
        elif field_num == 11:
            s.highlight_reel = value
        elif field_num == 12:
            s.paint_kit = value
    return s


def encode_item(item: "ItemPreviewData") -> bytes:  # noqa: F821
    from .models import ItemPreviewData
    w = ProtoWriter()
    w.write_uint32(1, item.accountid)
    w.write_uint64(2, item.itemid)
    w.write_uint32(3, item.defindex)
    w.write_uint32(4, item.paintindex)
    w.write_uint32(5, item.rarity)
    w.write_uint32(6, item.quality)
    # paintwear: float32 reinterpreted as uint32 varint
    if item.paintwear is not None:
        pw_uint32 = float32_to_uint32(item.paintwear)
        w.write_uint32(7, pw_uint32)
    w.write_uint32(8, item.paintseed)
    w.write_uint32(9, item.killeaterscoretype)
    w.write_uint32(10, item.killeatervalue)
    w.write_string(11, item.customname)
    for sticker in item.stickers:
        sticker_bytes = encode_sticker(sticker)
        w.write_bytes(12, sticker_bytes)
    w.write_uint32(13, item.inventory)
    w.write_uint32(14, item.origin)
    w.write_uint32(15, item.questid)
    w.write_uint32(16, item.dropreason)
    w.write_uint32(17, item.musicindex)
    w.write_int32(18, item.entindex)
    w.write_uint32(19, item.petindex)
    for kc in item.keychains:
        kc_bytes = encode_sticker(kc)
        w.write_bytes(20, kc_bytes)
    return w.to_bytes()


def decode_item(data: bytes) -> "ItemPreviewData":  # noqa: F821
    from .models import ItemPreviewData
    reader = ProtoReader(data)
    item = ItemPreviewData()
    for field_num, wire_type, value in reader.read_all_fields():
        if field_num == 1:
            item.accountid = value
        elif field_num == 2:
            item.itemid = value
        elif field_num == 3:
            item.defindex = value
        elif field_num == 4:
            item.paintindex = value
        elif field_num == 5:
            item.rarity = value
        elif field_num == 6:
            item.quality = value
        elif field_num == 7:
            item.paintwear = uint32_to_float32(value)
        elif field_num == 8:
            item.paintseed = value
        elif field_num == 9:
            item.killeaterscoretype = value
        elif field_num == 10:
            item.killeatervalue = value
        elif field_num == 11:
            item.customname = value.decode("utf-8")
        elif field_num == 12:
            item.stickers.append(decode_sticker(value))
        elif field_num == 13:
            item.inventory = value
        elif field_num == 14:
            item.origin = value
        elif field_num == 15:
            item.questid = value
        elif field_num == 16:
            item.dropreason = value
        elif field_num == 17:
            item.musicindex = value
        elif field_num == 18:
            item.entindex = value
        elif field_num == 19:
            item.petindex = value
        elif field_num == 20:
            item.keychains.append(decode_sticker(value))
    return item
