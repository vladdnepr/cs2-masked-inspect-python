"""Tests for CS2 inspect link serialization/deserialization.

Run with:  pytest python/tests/
"""

import math
import struct

import pytest

from cs2_inspect import ItemPreviewData, Sticker, deserialize, is_classic, is_masked, serialize


# ---------------------------------------------------------------------------
# Known test vectors
# ---------------------------------------------------------------------------

# A real CS2 item encoded with XOR key 0xE3
NATIVE_HEX = (
    "E3F3367440334DE2FBE4C345E0CBE0D3E7DB6943400AE0A379E481ECEBE2F36FD9DE2BDB515EA6E30D74D981"
    "ECEBE3F37BCBDE640D475DA6E35EFCD881ECEBE3F359D5DE37E9D75DA6436DD3DD81ECEBE3F366DCDE3F8F9B"
    "DDA69B43B6DE81ECEBE3F33BC8DEBB1CA3DFA623F7DDDF8B71E293EBFD43382B"
)

# A tool-generated link with key 0x00
TOOL_HEX = "00183C20B803280538E9A3C5DD0340E102C246A0D1"


# ---------------------------------------------------------------------------
# Deserialize tests
# ---------------------------------------------------------------------------

class TestDeserialize:
    def test_native_xor_key(self):
        item = deserialize(NATIVE_HEX)
        assert item.itemid == 46876117973
        assert item.defindex == 7  # AK-47
        assert item.paintindex == 422
        assert item.paintseed == 922
        assert item.rarity == 3
        assert item.quality == 4

    def test_native_paintwear(self):
        item = deserialize(NATIVE_HEX)
        assert abs(item.paintwear - 0.04121) < 0.0001

    def test_native_sticker_count(self):
        item = deserialize(NATIVE_HEX)
        assert len(item.stickers) == 5

    def test_native_sticker_ids(self):
        item = deserialize(NATIVE_HEX)
        sticker_ids = [s.sticker_id for s in item.stickers]
        assert sticker_ids == [7436, 5144, 6970, 8069, 5592]

    def test_tool_hex_key_zero(self):
        item = deserialize(TOOL_HEX)
        assert item.defindex == 60
        assert item.paintindex == 440
        assert item.paintseed == 353
        assert item.rarity == 5

    def test_tool_hex_paintwear(self):
        item = deserialize(TOOL_HEX)
        # Expected float: 0.005411375779658556
        assert abs(item.paintwear - 0.005411375779658556) < 1e-7

    def test_lowercase_hex(self):
        item = deserialize(TOOL_HEX.lower())
        assert item.defindex == 60

    def test_accepts_steam_url(self):
        url = (
            "steam://rungame/730/76561202255233023/"
            "+csgo_econ_action_preview%20A" + TOOL_HEX
        )
        item = deserialize(url)
        assert item.defindex == 60

    def test_accepts_csgo_style_url(self):
        url = "csgo://rungame/730/76561202255233023/+csgo_econ_action_preview A" + TOOL_HEX
        item = deserialize(url)
        assert item.defindex == 60

    def test_payload_too_short_raises(self):
        with pytest.raises((ValueError, Exception)):
            deserialize("0000")


# ---------------------------------------------------------------------------
# Serialize tests
# ---------------------------------------------------------------------------

class TestSerialize:
    def test_known_hex_output(self):
        data = ItemPreviewData(
            defindex=60,
            paintindex=440,
            paintseed=353,
            paintwear=0.005411375779658556,
            rarity=5,
        )
        result = serialize(data)
        assert result == TOOL_HEX

    def test_returns_uppercase(self):
        data = ItemPreviewData(defindex=1)
        result = serialize(data)
        assert result == result.upper()

    def test_starts_with_00(self):
        data = ItemPreviewData(defindex=1)
        result = serialize(data)
        assert result.startswith("00")

    def test_minimum_length(self):
        # header (1) + at least 1 proto byte + checksum (4) => 6 bytes => 12 hex chars
        data = ItemPreviewData(defindex=1)
        result = serialize(data)
        assert len(result) >= 12


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def _roundtrip(self, data: ItemPreviewData) -> ItemPreviewData:
        return deserialize(serialize(data))

    def test_defindex(self):
        data = ItemPreviewData(defindex=7)
        assert self._roundtrip(data).defindex == 7

    def test_paintindex(self):
        data = ItemPreviewData(paintindex=422)
        assert self._roundtrip(data).paintindex == 422

    def test_paintseed(self):
        data = ItemPreviewData(paintseed=999)
        assert self._roundtrip(data).paintseed == 999

    def test_paintwear_precision(self):
        # float32 has ~7 significant digits
        original = 0.123456789
        data = ItemPreviewData(paintwear=original)
        result = self._roundtrip(data)
        # Round-trip via float32 — compare within float32 epsilon
        expected = struct.unpack("<f", struct.pack("<f", original))[0]
        assert abs(result.paintwear - expected) < 1e-7

    def test_itemid_large(self):
        data = ItemPreviewData(itemid=46876117973)
        assert self._roundtrip(data).itemid == 46876117973

    def test_stickers(self):
        data = ItemPreviewData(
            defindex=7,
            stickers=[
                Sticker(slot=0, sticker_id=7436),
                Sticker(slot=1, sticker_id=5144),
            ],
        )
        result = self._roundtrip(data)
        assert len(result.stickers) == 2
        assert result.stickers[0].sticker_id == 7436
        assert result.stickers[1].sticker_id == 5144

    def test_sticker_slots(self):
        data = ItemPreviewData(
            stickers=[Sticker(slot=3, sticker_id=123)],
        )
        result = self._roundtrip(data)
        assert result.stickers[0].slot == 3

    def test_sticker_wear(self):
        data = ItemPreviewData(
            stickers=[Sticker(sticker_id=1, wear=0.5)],
        )
        result = self._roundtrip(data)
        assert result.stickers[0].wear is not None
        assert abs(result.stickers[0].wear - 0.5) < 1e-6

    def test_keychains(self):
        data = ItemPreviewData(
            keychains=[Sticker(slot=0, sticker_id=999, pattern=42)],
        )
        result = self._roundtrip(data)
        assert len(result.keychains) == 1
        assert result.keychains[0].sticker_id == 999
        assert result.keychains[0].pattern == 42

    def test_customname(self):
        data = ItemPreviewData(defindex=7, customname="My Knife")
        result = self._roundtrip(data)
        assert result.customname == "My Knife"

    def test_rarity_quality(self):
        data = ItemPreviewData(rarity=6, quality=9)
        result = self._roundtrip(data)
        assert result.rarity == 6
        assert result.quality == 9

    def test_full_item(self):
        data = ItemPreviewData(
            accountid=0,
            itemid=46876117973,
            defindex=7,
            paintindex=422,
            rarity=3,
            quality=4,
            paintwear=0.04121,
            paintseed=922,
            stickers=[
                Sticker(slot=0, sticker_id=7436),
                Sticker(slot=1, sticker_id=5144),
                Sticker(slot=2, sticker_id=6970),
                Sticker(slot=3, sticker_id=8069),
                Sticker(slot=4, sticker_id=5592),
            ],
        )
        result = self._roundtrip(data)
        assert result.defindex == 7
        assert result.paintindex == 422
        assert result.paintseed == 922
        assert len(result.stickers) == 5
        assert [s.sticker_id for s in result.stickers] == [7436, 5144, 6970, 8069, 5592]


# ---------------------------------------------------------------------------
# Hybrid URL and validation tests
# ---------------------------------------------------------------------------

HYBRID_URL = (
    'steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20'
    'S76561199323320483A50075495125D1101C4C4FCD4AB10092D31B8143914211829A1FAE3FD125119591141117308191301'
    'EA550C1111912E3C111151D12C413E6BAC54D1D29BAD731E191501B92C2C9B6BF92F5411C25B2A731E191501B92C2C'
    'EA2B182E5411F7212A731E191501B92C2C4F89C12F549164592A799713611956F4339F'
)

CLASSIC_URL = (
    'steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20'
    'S76561199842063946A49749521570D2751293026650298712'
)


class TestValidation:
    def test_is_masked_true_for_pure_hex_payload(self):
        url = 'steam://run/730//+csgo_econ_action_preview%20' + TOOL_HEX
        assert is_masked(url) is True

    def test_is_masked_true_for_full_masked_url(self):
        url = 'steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20' + NATIVE_HEX
        assert is_masked(url) is True

    def test_is_masked_true_for_hybrid_url(self):
        assert is_masked(HYBRID_URL) is True

    def test_is_masked_false_for_classic_url(self):
        assert is_masked(CLASSIC_URL) is False

    def test_is_classic_true_for_classic_url(self):
        assert is_classic(CLASSIC_URL) is True

    def test_is_classic_false_for_masked_url(self):
        url = 'steam://run/730//+csgo_econ_action_preview%20' + TOOL_HEX
        assert is_classic(url) is False

    def test_is_classic_false_for_hybrid_url(self):
        assert is_classic(HYBRID_URL) is False

    def test_deserialize_hybrid_url_returns_correct_itemid(self):
        item = deserialize(HYBRID_URL)
        assert item.itemid == 50075495125


# ---------------------------------------------------------------------------
# Checksum correctness
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_known_hex_checksum_matches(self):
        """Serializing the known item must produce exactly the known hex."""
        data = ItemPreviewData(
            defindex=60,
            paintindex=440,
            paintseed=353,
            paintwear=0.005411375779658556,
            rarity=5,
        )
        assert serialize(data) == TOOL_HEX


# ---------------------------------------------------------------------------
# Defensive validation tests
# ---------------------------------------------------------------------------

class TestDefensiveChecks:
    def test_deserialize_payload_too_long_raises(self):
        """Payloads longer than 4096 hex chars must raise ValueError."""
        long_hex = "00" * 2049  # 4098 hex chars > 4096 limit
        with pytest.raises(ValueError, match="Payload too long"):
            deserialize(long_hex)

    def test_serialize_paintwear_above_one_raises(self):
        """paintwear > 1.0 must raise ValueError."""
        data = ItemPreviewData(defindex=7, paintwear=1.1)
        with pytest.raises(ValueError, match="paintwear"):
            serialize(data)

    def test_serialize_paintwear_below_zero_raises(self):
        """paintwear < 0.0 must raise ValueError."""
        data = ItemPreviewData(defindex=7, paintwear=-0.1)
        with pytest.raises(ValueError, match="paintwear"):
            serialize(data)

    def test_serialize_paintwear_zero_is_valid(self):
        """paintwear == 0.0 is a valid boundary value."""
        data = ItemPreviewData(defindex=7, paintwear=0.0)
        result = serialize(data)
        assert result.startswith("00")

    def test_serialize_paintwear_one_is_valid(self):
        """paintwear == 1.0 is a valid boundary value."""
        data = ItemPreviewData(defindex=7, paintwear=1.0)
        result = serialize(data)
        assert result.startswith("00")

    def test_serialize_customname_101_chars_raises(self):
        """customname exceeding 100 characters must raise ValueError."""
        data = ItemPreviewData(defindex=7, customname="x" * 101)
        with pytest.raises(ValueError, match="customname"):
            serialize(data)

    def test_serialize_customname_100_chars_is_valid(self):
        """customname of exactly 100 characters must be accepted."""
        data = ItemPreviewData(defindex=7, customname="x" * 100)
        result = serialize(data)
        assert result.startswith("00")


# -------------------------------------------------------------------------
# CSFloat / gen.test.ts test vectors
# -------------------------------------------------------------------------

CSFLOAT_A = "00180720DA03280638FBEE88F90340B2026BC03C96"
CSFLOAT_B = "00180720C80A280638A4E1F5FB03409A0562040800104C62040801104C62040802104C62040803104C6D4F5E30"
CSFLOAT_C = "A2B2A2BA69A882A28AA192AECAA2D2B700A3A5AAA2B286FA7BA0D684BE72"


class TestCsfloatVectors:
    def test_vector_a_defindex(self):
        assert deserialize(CSFLOAT_A).defindex == 7

    def test_vector_a_paintindex(self):
        assert deserialize(CSFLOAT_A).paintindex == 474

    def test_vector_a_paintseed(self):
        assert deserialize(CSFLOAT_A).paintseed == 306

    def test_vector_a_rarity(self):
        assert deserialize(CSFLOAT_A).rarity == 6

    def test_vector_a_paintwear_not_none(self):
        assert deserialize(CSFLOAT_A).paintwear is not None

    def test_vector_a_paintwear(self):
        assert abs(deserialize(CSFLOAT_A).paintwear - 0.6337) < 0.001

    def test_vector_b_sticker_count(self):
        assert len(deserialize(CSFLOAT_B).stickers) == 4

    def test_vector_b_sticker_ids(self):
        for s in deserialize(CSFLOAT_B).stickers:
            assert s.sticker_id == 76

    def test_vector_b_paintindex(self):
        assert deserialize(CSFLOAT_B).paintindex == 1352

    def test_vector_b_paintwear(self):
        assert abs(deserialize(CSFLOAT_B).paintwear - 0.99) < 0.01

    def test_vector_c_defindex(self):
        assert deserialize(CSFLOAT_C).defindex == 1355

    def test_vector_c_quality(self):
        assert deserialize(CSFLOAT_C).quality == 12

    def test_vector_c_keychain_count(self):
        assert len(deserialize(CSFLOAT_C).keychains) == 1

    def test_vector_c_keychain_highlight_reel(self):
        assert deserialize(CSFLOAT_C).keychains[0].highlight_reel == 345

    def test_vector_c_no_paintwear(self):
        assert deserialize(CSFLOAT_C).paintwear is None


class TestRoundtripNewFeatures:
    def test_highlight_reel_roundtrip(self):
        from cs2_inspect.models import Sticker as StickerModel
        data = ItemPreviewData(defindex=7, keychains=[StickerModel(slot=0, sticker_id=36, highlight_reel=345)])
        result = deserialize(serialize(data))
        assert len(result.keychains) == 1
        assert result.keychains[0].highlight_reel == 345

    def test_null_paintwear_roundtrip(self):
        data = ItemPreviewData(defindex=7, paintwear=None)
        result = deserialize(serialize(data))
        assert result.paintwear is None
