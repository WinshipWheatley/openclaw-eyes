"""RED-first tests for the scene-corpus analyzer: turn all of Winship's legacy
.scn files into a foundational profile (naming/color/icon vocab + routing).
Run: python3 -m unittest test_scene_corpus -v
"""
import os
import tempfile
import unittest

from scene_corpus import parse_scene, analyze_corpus

SCENE_A = ('#4.0# "Gig A" "" %000000000 1\n'
           '/ch/01/config "Kick" 2 RD 1\n'
           '/ch/02/config "Snare" 4 RD 2\n'
           '/bus/01/config "Drum Bus" 71 RD\n'
           '/config/routing PLAY\n'
           '/config/routing/IN A1-8 A9-16 A17-24 A25-32 CARD1-2\n'
           '/config/routing/AES50A AN1-8 AN9-16 P161-8 P169-16 P161-8 P169-16\n'
           '/config/routing/CARD A1-8 A9-16 P161-8 P169-16\n')

SCENE_B = ('#4.0# "Gig B" "" %000000000 1\n'
           '/ch/01/config "Kick" 2 YE 1\n'
           '/ch/03/config "Bass" 17 BL 3\n'
           '/config/routing REC\n')


def _tmp(text):
    p = tempfile.mktemp(suffix=".scn")
    with open(p, "w") as f:
        f.write(text)
    return p


class TestSceneCorpus(unittest.TestCase):
    def test_parse_scene_channels_buses_routing(self):
        p = _tmp(SCENE_A)
        s = parse_scene(p)
        self.assertEqual(s["scene_name"], "Gig A")
        ch = {c["ch"]: c for c in s["channels"]}
        self.assertEqual(ch[1]["name"], "Kick")
        self.assertEqual(ch[1]["icon"], 2)
        self.assertEqual(ch[1]["color"], "RD")
        self.assertEqual(s["routing_mode"], "PLAY")
        self.assertIn("AN1-8", s["routing"]["AES50A"])
        self.assertTrue(any(b["name"] == "Drum Bus" for b in s["buses"]))
        os.remove(p)

    def test_analyze_corpus_builds_name_vocab(self):
        pa, pb = _tmp(SCENE_A), _tmp(SCENE_B)
        agg = analyze_corpus([pa, pb])
        kick = agg["name_vocab"]["Kick"]
        self.assertEqual(kick["count"], 2)          # Kick named in both scenes
        self.assertIn("RD", kick["colors"])         # color RD seen
        self.assertIn("YE", kick["colors"])         # and YE
        self.assertEqual(kick["icons"], {2: 2})     # icon 2 both times
        self.assertEqual(len(agg["scenes"]), 2)
        os.remove(pa)
        os.remove(pb)

    def test_analyze_corpus_dedupes_routing_profiles(self):
        pa, pb, pc = _tmp(SCENE_A), _tmp(SCENE_A), _tmp(SCENE_B)
        agg = analyze_corpus([pa, pb, pc])
        # SCENE_A's routing appears twice -> one profile with 2 members
        sizes = sorted(len(v) for v in agg["routing_profiles"].values())
        self.assertIn(2, sizes)
        for p in (pa, pb, pc):
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
