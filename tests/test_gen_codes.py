"""Tests for gen code functionality."""

from cs2_inspect import generate, parse_gen_code, to_gen_code
from cs2_inspect import ItemPreviewData, Sticker

INSPECT_BASE = "steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20"


class TestToGenCode:
    def test_basic_item(self):
        item = ItemPreviewData(defindex=7, paintindex=474, paintseed=306,
                               paintwear=0.22540508210659027)
        code = to_gen_code(item)
        assert code == "!gen 7 474 306 0.22540508"

    def test_custom_prefix(self):
        item = ItemPreviewData(defindex=7, paintindex=474, paintseed=306,
                               paintwear=0.22540508210659027)
        code = to_gen_code(item, prefix="!g")
        assert code == "!g 7 474 306 0.22540508"

    def test_with_sticker_in_slot_2(self):
        item = ItemPreviewData(
            defindex=7, paintindex=941, paintseed=2,
            paintwear=0.22540508210659027,
            stickers=[Sticker(slot=2, sticker_id=7203, wear=0.0)],
        )
        code = to_gen_code(item, prefix="!g")
        assert code == "!g 7 941 2 0.22540508 0 0 0 0 7203 0 0 0 0 0"

    def test_with_sticker_and_keychain(self):
        item = ItemPreviewData(
            defindex=7, paintindex=941, paintseed=2,
            paintwear=0.22540508210659027,
            stickers=[Sticker(slot=2, sticker_id=7203, wear=0.0)],
            keychains=[Sticker(slot=0, sticker_id=36, wear=0.0)],
        )
        code = to_gen_code(item, prefix="!g")
        assert code == "!g 7 941 2 0.22540508 0 0 0 0 7203 0 0 0 0 0 36 0"

    def test_zero_wear_float_format(self):
        item = ItemPreviewData(defindex=7, paintindex=474, paintseed=306,
                               paintwear=0.0)
        code = to_gen_code(item)
        assert code == "!gen 7 474 306 0"

    def test_keychain_with_paint_kit_appends_paint_kit(self):
        item = ItemPreviewData(
            defindex=1355, paintindex=0, paintseed=0, paintwear=0.0,
            keychains=[Sticker(slot=0, sticker_id=37, wear=0.0, paint_kit=929)],
        )
        code = to_gen_code(item, prefix="")
        tokens = code.split()
        assert tokens[-3] == "37"
        assert tokens[-2] == "0"
        assert tokens[-1] == "929"

    def test_keychain_without_paint_kit_no_extra_token(self):
        item = ItemPreviewData(
            defindex=7, paintindex=0, paintseed=0, paintwear=0.0,
            keychains=[Sticker(slot=0, sticker_id=36, wear=0.0)],
        )
        code = to_gen_code(item, prefix="")
        tokens = code.split()
        assert tokens[-2] == "36"
        assert tokens[-1] == "0"


class TestParseGenCode:
    def test_basic_parse(self):
        item = parse_gen_code("!gen 7 474 306 0.22540508")
        assert item.defindex == 7
        assert item.paintindex == 474
        assert item.paintseed == 306
        assert abs(item.paintwear - 0.22540508) < 1e-6

    def test_parse_without_prefix(self):
        item = parse_gen_code("7 474 306 0.22540508")
        assert item.defindex == 7

    def test_parse_with_sticker(self):
        item = parse_gen_code("!gen 7 941 2 0.22540508 0 0 0 0 7203 0 0 0 0 0")
        assert len(item.stickers) == 1
        assert item.stickers[0].slot == 2
        assert item.stickers[0].sticker_id == 7203

    def test_parse_with_sticker_and_keychain(self):
        item = parse_gen_code("!g 7 941 2 0.22540508 0 0 0 0 7203 0 0 0 0 0 36 0")
        assert len(item.stickers) == 1
        assert item.stickers[0].sticker_id == 7203
        assert len(item.keychains) == 1
        assert item.keychains[0].sticker_id == 36


class TestGenCodeFromLinkSlab:
    def test_mousesports_slab_url_ends_with_paint_kit(self):
        from cs2_inspect import gen_code_from_link
        slab_url = "steam://run/730//+csgo_econ_action_preview%20819181994A8BA181A982B189E981F181238086898191A4E1208698F309C9"
        code = gen_code_from_link(slab_url, prefix="")
        tokens = code.split()
        assert tokens[-3] == "37"
        assert tokens[-2] == "0"
        assert tokens[-1] == "929"


class TestGenCodeFromLink:
    def test_from_hex(self):
        from cs2_inspect import generate, gen_code_from_link
        url = generate(7, 474, 306, 0.22540508)
        hex_payload = url.split("csgo_econ_action_preview%20")[1]
        code = gen_code_from_link(hex_payload)
        assert code.startswith("!gen 7 474 306")

    def test_from_full_url(self):
        from cs2_inspect import generate, gen_code_from_link
        url = generate(7, 474, 306, 0.22540508)
        code = gen_code_from_link(url)
        assert code.startswith("!gen 7 474 306")


class TestGenerate:
    def test_returns_inspect_url(self):
        url = generate(7, 474, 306, 0.22540508)
        assert url.startswith(INSPECT_BASE)

    def test_roundtrip(self):
        from cs2_inspect import deserialize
        url = generate(7, 474, 306, 0.22540508)
        # Extract hex payload and deserialize
        hex_payload = url.split(INSPECT_BASE)[1]
        item = deserialize(hex_payload)
        assert item.defindex == 7
        assert item.paintindex == 474
        assert item.paintseed == 306
        assert item.paintwear is not None
        assert abs(item.paintwear - 0.22540508) < 1e-5

    def test_with_stickers(self):
        from cs2_inspect import deserialize
        stickers = [Sticker(slot=0, sticker_id=123, wear=0.1)]
        url = generate(7, 474, 306, 0.22540508, stickers=stickers)
        hex_payload = url.split(INSPECT_BASE)[1]
        item = deserialize(hex_payload)
        assert len(item.stickers) == 1
        assert item.stickers[0].sticker_id == 123
