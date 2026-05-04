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
        """Payloads longer than 4096 hex chars must raise MalformedInspectLinkError."""
        long_hex = "00" * 2049  # 4098 hex chars > 4096 limit
        with pytest.raises(ValueError, match="too long"):
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


# ---------------------------------------------------------------------------
# Sticker Slab test vectors (defIndex=1355, quality=8, slab variant via paint_kit)
# ---------------------------------------------------------------------------

# URL A — rarity=5, keychains[0].sticker_id=37, keychains[0].paint_kit=7256
SLAB_URL_A = (
    'steam://run/730//+csgo_econ_action_preview%20'
    '918191895A9BB191B994A199F991E191339096999181B4F149A98D5C0889'
)

# URL B — rarity=3, keychains[0].sticker_id=37, keychains[0].paint_kit=275
SLAB_URL_B = (
    'steam://run/730//+csgo_econ_action_preview%20'
    'CBDBCBD300C1EBCBE3C8FBC3A3CBBBCB69CACCC3CBDBEEAB58C9B8B67C83'
)


class TestStickerSlabVectors:
    def test_slab_a_defindex(self):
        assert deserialize(SLAB_URL_A).defindex == 1355

    def test_slab_a_quality(self):
        assert deserialize(SLAB_URL_A).quality == 8

    def test_slab_a_rarity(self):
        assert deserialize(SLAB_URL_A).rarity == 5

    def test_slab_a_keychain_sticker_id(self):
        keychains = deserialize(SLAB_URL_A).keychains
        assert len(keychains) == 1
        assert keychains[0].sticker_id == 37

    def test_slab_a_keychain_paint_kit(self):
        keychains = deserialize(SLAB_URL_A).keychains
        assert len(keychains) == 1
        assert keychains[0].paint_kit == 7256

    def test_slab_b_defindex(self):
        assert deserialize(SLAB_URL_B).defindex == 1355

    def test_slab_b_quality(self):
        assert deserialize(SLAB_URL_B).quality == 8

    def test_slab_b_rarity(self):
        assert deserialize(SLAB_URL_B).rarity == 3

    def test_slab_b_keychain_sticker_id(self):
        keychains = deserialize(SLAB_URL_B).keychains
        assert len(keychains) == 1
        assert keychains[0].sticker_id == 37

    def test_slab_b_keychain_paint_kit(self):
        keychains = deserialize(SLAB_URL_B).keychains
        assert len(keychains) == 1
        assert keychains[0].paint_kit == 275

    def test_paint_kit_roundtrip(self):
        data = ItemPreviewData(
            defindex=1355,
            quality=8,
            rarity=5,
            keychains=[Sticker(slot=0, sticker_id=37, paint_kit=7256)],
        )
        result = deserialize(serialize(data))
        assert len(result.keychains) == 1
        assert result.keychains[0].sticker_id == 37
        assert result.keychains[0].paint_kit == 7256


# ---------------------------------------------------------------------------
# Malformed URLs (regression: must reject cleanly, never crash with native error)
# ---------------------------------------------------------------------------

from cs2_inspect import MalformedInspectLinkError


_MALFORMED_URLS = {
    "truncated mid-keychain (defindex=1, key=0xAD)": "steam://run/730//+csgo_econ_action_preview%20ADBD1050393912ACB5AC8D45AC85A99DA9956A116D5FAEED21ACCFB4A5AFBD348EB0ADAD2D9280ADADDD6F90EDA37510E84D8BEE11CFB4A5ACBD348EB0ADAD2D9280ADAD5D6F906F2B4C13E84D93D591CFB9A5ADBD419EB0ADAD2D9290ADF22010E8B72FB213CFB4A5ADBD549EB0ADAD2D9280ADADED6C90CFD43F10E892DFE513CFB4A5ADBD549EB0ADAD2D9280ADAD85EE902F952210E82EB8A613C52E2D2D2DA1DDA90FACBBA5ADBD89902923AAECE83",
    "truncated mid-keychain (defindex=9, key=0xEE)": "steam://run/730//+csgo_econ_action_preview%20EEFE3144332550EFF6E7CE28E8C6EADEEAD642323218EDAE4DEA8CFAE6ECFE35A7F302BFD6D1D3004FCB50ABAE5CF8528CF7E6EEFE0DA7F3394DDED1C3EEEE7EAFD39E25B3D3AB9EAE70D28CFAE6ECFE32A7F3EEEE6ED1D3595B17D3AB9E8E65538CFAE6ECFE64ADF3EEEE6ED1D3E597F3D3AB2EEA1AD58CF7E6EDFE0BCAF302BFD6D1C3EEEEEF2DD3AEF5F552ABEE31A855866D6E6E6EE29EE64CEFF8E6EEFED8D3B6CBCBACABFD70EED1A31F96E7AFBE5",
    "truncated mid-keychain (defindex=1, key=0x4A)": "steam://run/730//+csgo_econ_action_preview%204A5A8EFCB1B9F44B524B6AA24B624E7A4E72BACFF6B8490AD449285E42485AAB75576316457577CA2422760F4A413E712853424A5AA679574A4ACA75674A4A8A8A770A7F85760FD04246F4285342495AB279574A4ACA75674A4A8A0A7799714A750F0A5140F7285342495AAD7277EB4547F40F0A00EB7122C9CACACA463A4EE84B5D424A5A4C776C02A10A0F34A5C17407F0145C0A1AA",
    "truncated mid-keychain (AK-47 1035, key=0xFA)": "steam://run/730//+csgo_econ_action_preview%20FAEA5766387F45FBE2FDDA71F2D2FECAF3C2142C0C0EF9BA7CFFB2FAAAFA98EEF2F8EA3BFBD7FAFA3ABBC7EA2FB7C7BF9ACC47C698E3F2F9EA03C9E7FAFA7AC5D7FAFABA3AC780CA89C4BFFAAAD9C198E3F2F9EA03C9E7FAFA7AC5D7FAFACEB9C7B60177C4BFAAB82AC698EEF2F9EA03C9E7FAFA7AC5C7C11558C4BFFA43DBC198F5F2FBEA13DEC7759A1147BF9A16F64692797A7A7AF68AF258FBEFF2FAEADEC7DEAC32BBBF0BF9BAC4B760382CC5A2D24",
    "truncated mid-keychain (defindex=40, key=0x9F)": "steam://run/730//+csgo_econ_action_preview%209F8F4F504C7C219E87B7BF629EB79CAF9BA73F1D53419CDF0699FD8B979F8F5CCF82050686A0A2F4038821DA17F3FD22FD8B979F8F49D4825C6AB7A0A25F50B224DA7F0CF222FD8B979D8F5DCF82F9F9B9A0A2B7B25422DA6F6F1422FD8B979D8F5DCF822781DAA0A247B731A2DA7F92EF23FD86979F8F5DCF827EE5CBA0B29F9FDFDFA285AD4322DA9FFD8AA3F71C1F1F1F93EF873D9E88979F8FDDA243C05EDFDA4CFB44A0D202B77EDFCF3F339C3DF89",
    "truncated mid-keychain (M4A1-S 1130, key=0xFA)": "steam://run/730//+csgo_econ_action_preview%20FAEA5B24060844FBE2C6DA10F2D2FECAF3C2631A3308F9BA47F8B2FAAAFA98EEF2FEEA29B2E781EED4C5C7776B78C4BFFAFA21CD98EEF2FAEA09BCE7F02DD9C5C7FE6C57C7BF7A58ED4698EEF2FEEA6DBDE79C9CDCC5C7929F2F47BFFA461BC398E3F2FBEA15BDE7E57FD1C5D7FAFA8AB8C7C2CEDC46BF12973EC798EEF2FEEA24B8E781EED4C5C75696FCC5BF2AEBF2C792797A7A7AF68AF258FBEDF2FAEAD2C7B3683FBBBF065F8CC5B763A382BAAA0C5",
    "truncated mid-keychain (defindex=35, key=0x4D)": "steam://run/730//+csgo_econ_action_preview%204D5D9DF8C7D2F34C556E6DDC4C654E7D4975B2D2AEBB4E0DAB4B2F59454E5D9A70604D4DBD8C7002A356F308CD4603F62F5445495DEB745011C20F72604D4D798F70797F9FF3089D49ABF12F5945495DEB74502B2BAB737045B3FAF308FD4BE8F12F5945495DF868508081417270BFB9D2F308ADD283F12F5945495DF86850AC375972702FA3CBF3083D2EBFF125CECDCDCD413D5AEF4C5A454D5D567084E4F80C08254C547200CE3E1D0D1DF9D24C63938",
    "truncated mid-keychain (AK-47 1171, key=0xCF)": "steam://run/730//+csgo_econ_action_preview%20CFDF6258412F71CED7C8EF5CC6E7C9FFCBF7465B3B38CC8F7ACEADD6C7CEDF3BF2D2F2C5D8F0E2CFCFE40CF27F72E1728AF786F5F2ADC0C7CCDF3BF2F241D88EF18A0F03F6F2ADDBC7CCDF3CF2E2CFCF0F8DF27B3FB7F18A6F5ACDF2ADD6C7CCDF3CF2D2C518ECF0E2CFCF8F0EF2D5C29AF18ACFCFD8F5ADDBC7CFDF3CF2E2CFCF6D8DF24DB0DA718A2FA6DBF3A74C4F4F4FC3BFC76DCED8C7CFDF87F27B950C8E8A37D0A3F182A2B8A48F9F4332CD2C2B6",
    "truncated mid-keychain (defindex=1 1050, key=0xCE)": "steam://run/730//+csgo_econ_action_preview%20CEDE51082D1C70CFD6CFEE54C6E6CAFEC7F631274538CD8E2DC886CE9ECEACDAC6CDDE0C8DD3CECE4EF1F382996B738B4E5E8D75ACD7C6CEDE0C8DD3CECE4EF1E3CECE8E0FF3A56603708BECDBE170ACD7C6CEDE0C8DD3CECE4EF1E3CECEDE0FF37682A5708B0650FB70ACD7C6CEDE0C8DD3CECE4EF1E3CECEDE0FF34E3CEC738BDAC6F870ACD7C6CDDE798AD3CECE4EF1E3CECE0E0EF3333BC5F18BAE8E9FF2A64D4E4E4EC2BECA6CCFD9C6CEDECFF37C6",
    "odd-length bare hex": "ABC",
    "empty string": "",
    "non-hex characters": "ZZZZZZZZZZZZ",
}


class TestMalformedUrls:
    @pytest.mark.parametrize("url", list(_MALFORMED_URLS.values()), ids=list(_MALFORMED_URLS.keys()))
    def test_raises_malformed_inspect_link_error(self, url):
        with pytest.raises(MalformedInspectLinkError):
            deserialize(url)

    def test_error_message_mentions_malformed_and_length(self):
        with pytest.raises(MalformedInspectLinkError, match=r"(?s)Malformed.*(length|even|hex)"):
            deserialize("ABC")

    def test_inherits_from_value_error(self):
        # BC: callers catching ValueError must still work.
        assert issubclass(MalformedInspectLinkError, ValueError)
