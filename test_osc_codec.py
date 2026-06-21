"""RED-first tests for the OSC 1.0 codec used by Niles' X32 controller + the X32 fake.
Run: python3 -m unittest test_osc_codec -v
"""
import unittest

from osc_codec import encode, decode


class TestOscCodec(unittest.TestCase):
    def test_roundtrip_string_arg(self):
        addr, args = decode(encode("/ch/01/config/name", "Kick"))
        self.assertEqual(addr, "/ch/01/config/name")
        self.assertEqual(args, ["Kick"])

    def test_roundtrip_int_arg(self):
        addr, args = decode(encode("/ch/01/config/color", 4))
        self.assertEqual(addr, "/ch/01/config/color")
        self.assertEqual(args, [4])

    def test_roundtrip_float_arg(self):
        addr, args = decode(encode("/ch/01/mix/fader", 0.75))
        self.assertEqual(addr, "/ch/01/mix/fader")
        self.assertAlmostEqual(args[0], 0.75, places=5)

    def test_address_only_is_a_query_with_no_args(self):
        # X32 semantics: sending an address with no args = query current value
        addr, args = decode(encode("/xinfo"))
        self.assertEqual(addr, "/xinfo")
        self.assertEqual(args, [])

    def test_encoding_is_4byte_aligned(self):
        self.assertEqual(len(encode("/ch/01/config/name", "Kick")) % 4, 0)
        self.assertEqual(len(encode("/headamp/000/gain", 0.5)) % 4, 0)

    def test_multiple_args_mixed_types(self):
        addr, args = decode(encode("/ch/01/config", "Kick", 1, 4))
        self.assertEqual(addr, "/ch/01/config")
        self.assertEqual(args, ["Kick", 1, 4])


if __name__ == "__main__":
    unittest.main()
