"""RED-first tests for the Niles X32 OSC controller, against the X32 fake.
Fast (sub-second), no hardware. Run: python3 -m unittest test_niles_x32 -v
"""
import os
import tempfile
import time
import unittest

from x32_fake import X32Fake
from niles_x32 import NilesX32


class TestNilesX32(unittest.TestCase):
    def setUp(self):
        self.fake = X32Fake().start()
        self.n = NilesX32(self.fake.host, self.fake.port, timeout=1.0)

    def tearDown(self):
        self.n.close()
        self.fake.stop()

    def test_connect_xinfo(self):
        info = self.n.xinfo()
        self.assertIn("X32FAKE", info)

    def test_set_and_get_channel_name(self):
        self.n.set_channel_name(1, "Kick")
        time.sleep(0.02)
        self.assertEqual(self.n.get_channel_name(1), "Kick")

    def test_set_and_get_channel_color_by_code(self):
        self.n.set_channel_color(1, "RD")
        time.sleep(0.02)
        self.assertEqual(self.n.get_channel_color(1), "RD")

    def test_fader_and_iem_send_roundtrip(self):
        self.n.set_fader(3, 0.5)
        self.n.set_send(3, 1, 0.25)   # ch3 -> IEM bus 1
        time.sleep(0.02)
        self.assertAlmostEqual(self.n.query("/ch/03/mix/fader")[0], 0.5, places=4)
        self.assertAlmostEqual(self.n.query("/ch/03/mix/01/level")[0], 0.25, places=4)

    def test_headamp_resolver_local_and_stagebox(self):
        self.assertEqual(self.n.resolve_headamp("local", 1), 0)
        self.assertEqual(self.n.resolve_headamp("aes50a", 1), 32)   # DL16 input 1 over AES50-A
        self.assertEqual(self.n.resolve_headamp("aes50b", 1), 80)

    def test_headamp_gain_and_phantom_set(self):
        idx = self.n.resolve_headamp("aes50a", 1)
        self.n.set_headamp_gain(idx, 34.5)
        self.n.set_headamp_phantom(idx, True)
        time.sleep(0.02)
        self.assertAlmostEqual(self.n.query("/headamp/032/gain")[0], 34.5, places=3)
        self.assertEqual(self.n.query("/headamp/032/phantom")[0], 1)

    def test_load_scene_streams_lines(self):
        scn = ('#4.0# "T" "" %000000000 1\n'
               '/ch/01/config "Kick" 1 YE 1\n'
               '/ch/02/config "Snare" 1 RD 2\n')
        p = tempfile.mktemp(suffix=".scn")
        with open(p, "w") as f:
            f.write(scn)
        sent = self.n.load_scene(p)
        time.sleep(0.05)
        self.assertEqual(self.n.query("/ch/01/config")[0], "Kick")
        self.assertEqual(self.n.query("/ch/02/config")[0], "Snare")
        self.assertGreaterEqual(sent, 2)
        os.remove(p)

    def test_verify_readback_true_and_false(self):
        self.n.set_channel_name(5, "Vox")
        time.sleep(0.02)
        self.assertTrue(self.n.verify("/ch/05/config/name", ["Vox"]))
        self.assertFalse(self.n.verify("/ch/05/config/name", ["Wrong"]))


if __name__ == "__main__":
    unittest.main()
