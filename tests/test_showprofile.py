"""RED-first tests: email/stage-plot input-list -> X32 show profile (.scn).
Includes an end-to-end test through the already-built NilesX32 controller.
Run: python3 -m unittest test_showprofile -v
"""
import os
import tempfile
import time
import unittest
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The repo pytest sandbox blocks ALL socket.connect (guarded_socket_connect), so the
# X32 fake's UDP loopback cannot run under pytest here. These stay runnable directly
# (python3 tests/test_niles_x32.py) for fake/emulator/hardware verification.
_SANDBOX_ACTIVE = "guarded" in getattr(socket.socket.connect, "__name__", "")

from showprofile import parse_input_list, categorize, build_scene
from x32_fake import X32Fake
from niles_x32 import NilesX32


@unittest.skipIf(_SANDBOX_ACTIVE, "pytest sandbox blocks UDP; run this file directly for X32 fake verification")
class TestShowProfile(unittest.TestCase):
    def test_parse_numbered_list_variants(self):
        text = ("Input list:\n"
                "1. Kick\n"
                "2 - Snare Top\n"
                "3) Bass DI\n"
                "Ch 4: Gtr SM57\n"
                "5 Lead Vox\n"
                "\n")
        chans = parse_input_list(text)
        self.assertEqual([c["ch"] for c in chans], [1, 2, 3, 4, 5])
        self.assertEqual(chans[0]["name"], "Kick")
        self.assertEqual(chans[1]["name"], "Snare Top")
        self.assertEqual(chans[4]["name"], "Lead Vox")

    def test_categorize_assigns_color_and_icon_by_instrument(self):
        # categorize -> (category, color, icon) ; icons per the canonical X32 table
        self.assertEqual(categorize("Kick")[1:], ("RD", 2))        # kick-back
        self.assertEqual(categorize("Snare Top")[1:], ("RD", 4))   # snare-top
        self.assertEqual(categorize("Bass DI")[1:], ("BL", 17))    # elec-bass
        self.assertEqual(categorize("Gtr SM57")[1:], ("GN", 20))   # elec-guit
        self.assertEqual(categorize("Lead Vox")[1:], ("MG", 41))   # vocals = magenta/violet (best practice + his Vox Bus)
        self.assertEqual(categorize("Nord Keys")[1:], ("YEi", 29)) # elec-key

    def test_build_scene_is_valid_x32_format(self):
        chans = [{"ch": 1, "name": "Kick"}, {"ch": 2, "name": "Lead Vox"}]
        scn = build_scene(chans, "Reynolds Gig")
        lines = scn.splitlines()
        self.assertTrue(lines[0].startswith("#4.0#"))
        self.assertIn('/ch/01/config "Kick" 2 RD 1', scn)       # name + icon 2 + color + source
        self.assertIn('/ch/02/config "Lead Vox" 41 MG 2', scn)   # vocals -> magenta

    def test_scene_name_truncated_to_16(self):
        scn = build_scene([{"ch": 1, "name": "X"}], "A really long show name here")
        # X32 scene names cap at 16 chars
        header_name = scn.splitlines()[0].split('"')[1]
        self.assertLessEqual(len(header_name), 16)

    def test_end_to_end_email_to_desk(self):
        """Stage-plot text -> .scn -> streamed onto the (fake) desk -> verifiable."""
        email = "Stage plot\n1. Kick\n2. Bass DI\n3. Lead Vox\n"
        chans = parse_input_list(email)
        scn = build_scene(chans, "AutoShow")
        p = tempfile.mktemp(suffix=".scn")
        with open(p, "w") as f:
            f.write(scn)
        fake = X32Fake().start()
        n = NilesX32(fake.host, fake.port, timeout=1.0)
        try:
            n.load_scene(p)
            time.sleep(0.05)
            self.assertEqual(n.query("/ch/01/config")[0], "Kick")
            self.assertEqual(n.query("/ch/03/config")[0], "Lead Vox")
        finally:
            n.close()
            fake.stop()
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
