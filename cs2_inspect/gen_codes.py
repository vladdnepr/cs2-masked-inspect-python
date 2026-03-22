"""Gen code utilities for CS2 inspect links.

Gen codes are space-separated command strings used on community servers:
    !gen {defindex} {paintindex} {paintseed} {paintwear}
    !gen {defindex} {paintindex} {paintseed} {paintwear} {s0_id} {s0_wear} ... {s4_id} {s4_wear} [{kc_id} {kc_wear} ...]

Stickers are always represented as 5 slot pairs (padded with 0 0 for empty slots).
Keychains follow stickers without padding.
"""

from __future__ import annotations

from typing import Optional

from .models import ItemPreviewData, Sticker

INSPECT_BASE = "steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20"


def _format_float(value: float, precision: int = 8) -> str:
    """Format float, stripping trailing zeros up to 8 decimal places."""
    formatted = f"{value:.{precision}f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _serialize_sticker_pairs(stickers: list[Sticker], pad_to: Optional[int] = None) -> list[str]:
    """Serialize stickers to pairs of [id, wear], optionally padding to fixed number of slots."""
    result: list[str] = []
    filtered = [s for s in stickers if s.sticker_id != 0]

    if pad_to is not None:
        slot_map = {s.slot: s for s in filtered}
        for slot in range(pad_to):
            s = slot_map.get(slot)
            if s:
                result.append(str(s.sticker_id))
                result.append(_format_float(float(s.wear) if s.wear is not None else 0.0))
            else:
                result.extend(["0", "0"])
    else:
        for s in sorted(filtered, key=lambda x: x.slot):
            result.append(str(s.sticker_id))
            result.append(_format_float(float(s.wear) if s.wear is not None else 0.0))

    return result


def to_gen_code(item: ItemPreviewData, prefix: str = "!gen") -> str:
    """Convert an ItemPreviewData to a gen code string.

    Args:
        item: The item to convert.
        prefix: The command prefix, e.g. ``"!gen"`` or ``"!g"``.

    Returns:
        A space-separated gen code string like ``"!gen 7 474 306 0.22540508"``.
    """
    wear_str = _format_float(float(item.paintwear)) if item.paintwear is not None else "0"
    parts = [
        str(item.defindex),
        str(item.paintindex),
        str(item.paintseed),
        wear_str,
    ]

    has_stickers = any(s.sticker_id != 0 for s in item.stickers)
    has_keychains = any(s.sticker_id != 0 for s in item.keychains)

    if has_stickers or has_keychains:
        parts.extend(_serialize_sticker_pairs(item.stickers, pad_to=5))
        parts.extend(_serialize_sticker_pairs(item.keychains))

    payload = " ".join(parts)
    return f"{prefix} {payload}" if prefix else payload


def generate(
    def_index: int,
    paint_index: int,
    paint_seed: int,
    paint_wear: float,
    *,
    rarity: int = 0,
    quality: int = 0,
    stickers: Optional[list[Sticker]] = None,
    keychains: Optional[list[Sticker]] = None,
) -> str:
    """Generate a full Steam inspect URL from item parameters.

    Args:
        def_index: Weapon definition ID (e.g. 7 = AK-47).
        paint_index: Skin/paint ID.
        paint_seed: Pattern index (0-1000).
        paint_wear: Float value (0.0-1.0).
        rarity: Item rarity tier (0-7).
        quality: Item quality (e.g. 9 = StatTrak).
        stickers: List of Sticker objects applied to the item.
        keychains: List of Sticker objects used as keychains.

    Returns:
        A full ``steam://rungame/...`` inspect URL.
    """
    from .inspect_link import serialize

    data = ItemPreviewData(
        defindex=def_index,
        paintindex=paint_index,
        paintseed=paint_seed,
        paintwear=paint_wear,
        rarity=rarity,
        quality=quality,
        stickers=stickers or [],
        keychains=keychains or [],
    )
    hex_str = serialize(data)
    return f"{INSPECT_BASE}{hex_str}"


def gen_code_from_link(hex_or_url: str, prefix: str = "!gen") -> str:
    """Generate a gen code string from an existing CS2 inspect link.

    Deserializes the inspect link and converts the item data to gen code format.

    Args:
        hex_or_url: A hex payload or full steam:// inspect URL.
        prefix: The command prefix, e.g. ``"!gen"`` or ``"!g"``.

    Returns:
        A gen code string like ``"!gen 7 474 306 0.22540508"``.
    """
    from .inspect_link import deserialize
    item = deserialize(hex_or_url)
    return to_gen_code(item, prefix)


def parse_gen_code(gen_code: str) -> ItemPreviewData:
    """Parse a gen code string into an ItemPreviewData.

    Accepts codes like:
        ``"!gen 7 474 306 0.22540508"``
        ``"7 941 2 0.22540508 0 0 0 0 7203 0 0 0 0 0 36 0"``

    Args:
        gen_code: The gen code string to parse.

    Returns:
        An :class:`ItemPreviewData` with the parsed values.

    Raises:
        ValueError: If the code has fewer than 4 numeric tokens.
    """
    tokens = gen_code.strip().split()
    # Skip leading !-prefixed command (e.g. !gen, !g)
    if tokens and tokens[0].startswith("!"):
        tokens = tokens[1:]

    if len(tokens) < 4:
        raise ValueError(
            f"Gen code must have at least 4 tokens (defindex paintindex paintseed paintwear), got: {gen_code!r}"
        )

    def_index = int(tokens[0])
    paint_index = int(tokens[1])
    paint_seed = int(tokens[2])
    paint_wear = float(tokens[3])
    rest = tokens[4:]

    stickers: list[Sticker] = []
    keychains: list[Sticker] = []

    if len(rest) >= 10:
        # 5 sticker pairs
        sticker_tokens = rest[:10]
        for slot in range(5):
            sid = int(sticker_tokens[slot * 2])
            wear = float(sticker_tokens[slot * 2 + 1])
            if sid != 0:
                stickers.append(Sticker(slot=slot, sticker_id=sid, wear=wear))
        rest = rest[10:]

    for i in range(0, len(rest) - 1, 2):
        sid = int(rest[i])
        wear = float(rest[i + 1])
        if sid != 0:
            keychains.append(Sticker(slot=i // 2, sticker_id=sid, wear=wear))

    return ItemPreviewData(
        defindex=def_index,
        paintindex=paint_index,
        paintseed=paint_seed,
        paintwear=paint_wear,
        stickers=stickers,
        keychains=keychains,
    )
