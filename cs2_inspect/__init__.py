"""CS2 inspect link encoder/decoder.

Usage:
    from cs2_inspect import serialize, deserialize, ItemPreviewData, Sticker

    # Decode a native CS2 inspect link (XOR key != 0x00)
    item = deserialize("E3F3367440334D...")
    print(item.defindex, item.paintwear)

    # Encode an item to a hex payload
    data = ItemPreviewData(defindex=60, paintindex=440, paintseed=353,
                           paintwear=0.005411375779658556, rarity=5)
    hex_str = serialize(data)  # "00183C20B803..."
"""

from .inspect_link import deserialize, is_classic, is_masked, serialize
from .models import ItemPreviewData, Sticker

__all__ = ["serialize", "deserialize", "is_masked", "is_classic", "ItemPreviewData", "Sticker"]
