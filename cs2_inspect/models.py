"""Data classes for CS2 inspect link items."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Sticker:
    """Represents a sticker or keychain applied to a CS2 item.

    This models the protobuf Sticker message used in CEconItemPreviewDataBlock.
    The same message type is used for both stickers (field 12) and keychains (field 20).
    """

    slot: int = 0
    sticker_id: int = 0
    wear: Optional[float] = None
    scale: Optional[float] = None
    rotation: Optional[float] = None
    tint_id: int = 0
    offset_x: Optional[float] = None
    offset_y: Optional[float] = None
    offset_z: Optional[float] = None
    pattern: int = 0
    highlight_reel: Optional[int] = None
    paint_kit: Optional[int] = None


@dataclass
class ItemPreviewData:
    """Represents a CS2 item as encoded in an inspect link.

    Fields map directly to the CEconItemPreviewDataBlock protobuf message
    used by the CS2 game coordinator.

    paintwear is stored as a float32 (IEEE 754). On the wire it is reinterpreted
    as a uint32 — this class always exposes it as a Python float for convenience.
    """

    accountid: int = 0
    itemid: int = 0
    defindex: int = 0
    paintindex: int = 0
    rarity: int = 0
    quality: int = 0
    paintwear: Optional[float] = None
    paintseed: int = 0
    killeaterscoretype: int = 0
    killeatervalue: int = 0
    customname: str = ""
    stickers: list[Sticker] = field(default_factory=list)
    inventory: int = 0
    origin: int = 0
    questid: int = 0
    dropreason: int = 0
    musicindex: int = 0
    entindex: int = 0
    petindex: int = 0
    keychains: list[Sticker] = field(default_factory=list)
