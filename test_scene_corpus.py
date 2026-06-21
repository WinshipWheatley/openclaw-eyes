"""RED-first tests for the scene-corpus analyzer: turn all of Winship's legacy
.scn files into a foundational profile (naming/color/icon vocab + routing).
Run: python3 -m unittest test_scene_corpus -v
"""
import os
import tempfile
import unittest

from scene_corpus import parse_scene, analyze_corpus, to_markdown

SCENE_ABLETON = ('#4.0# "Ableton Session" "" %000000000 1\n'
                 '/ch/01/config "Synth L" 2 BL 1\n'
                 '/config/routing REC\n'
                 '/config/routing/CARD A1-8 A9-16\n')

SCENE_LOGIC = ('#4.0# "Logic Mix" "" %000000000 1\n'
               '/ch/01/config "Strings" 2 GN 1\n'
               '/config/routing REC\n')

SCENE_PLAIN_CARD = ('#4.0# "Studio Gig" "" %000000000 1\n'
                    '/ch/01/config "Guitar" 3 YE 1\n'
                    '/config/routing/CARD A1-8 A9-16\n')

SCENE_NO_PRODUCER = ('#4.0# "Live Show" "" %000000000 1\n'
                     '/ch/01/config "Kick" 2 RD 1\n'
                     '/config/routing PLAY\n')

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


class TestProducerMetadata(unittest.TestCase):
    def test_ableton_scene_name_tagged_producer_intent(self):
        p = _tmp(SCENE_ABLETON)
        s = parse_scene(p)
        self.assertTrue(s["producer_intent"])
        self.assertEqual(s["daw_hint"], "ableton")
        os.remove(p)

    def test_logic_scene_name_tagged_producer_intent(self):
        p = _tmp(SCENE_LOGIC)
        s = parse_scene(p)
        self.assertTrue(s["producer_intent"])
        self.assertEqual(s["daw_hint"], "logic")
        os.remove(p)

    def test_card_routing_tagged_producer_intent_no_daw(self):
        p = _tmp(SCENE_PLAIN_CARD)
        s = parse_scene(p)
        self.assertTrue(s["producer_intent"])
        self.assertTrue(s["has_card_routing"])
        self.assertIsNone(s["daw_hint"])
        os.remove(p)

    def test_plain_live_scene_not_producer_intent(self):
        p = _tmp(SCENE_NO_PRODUCER)
        s = parse_scene(p)
        self.assertFalse(s["producer_intent"])
        self.assertIsNone(s["daw_hint"])
        self.assertFalse(s["has_card_routing"])
        os.remove(p)

    def test_producer_osc_namespace_tagged(self):
        scn = ('#4.0# "Session" "" %000000000 1\n'
               '/_producer/track/1 "Synth" 0.8\n')
        p = _tmp(scn)
        s = parse_scene(p)
        self.assertTrue(s["has_producer_osc"])
        self.assertTrue(s["producer_intent"])
        os.remove(p)

    def test_analyze_corpus_producer_scenes_populated(self):
        pa = _tmp(SCENE_ABLETON)
        pb = _tmp(SCENE_NO_PRODUCER)
        agg = analyze_corpus([pa, pb])
        self.assertEqual(len(agg["producer_scenes"]), 1)
        self.assertEqual(agg["producer_scenes"][0]["daw_hint"], "ableton")
        self.assertEqual(len(agg["production_routing_profiles"]), 1)
        os.remove(pa)
        os.remove(pb)

    def test_to_markdown_includes_producer_section(self):
        pa = _tmp(SCENE_ABLETON)
        pb = _tmp(SCENE_NO_PRODUCER)
        agg = analyze_corpus([pa, pb])
        md = to_markdown(agg)
        self.assertIn("Producer Routing Profiles", md)
        self.assertIn("ableton", md.lower())
        os.remove(pa)
        os.remove(pb)

    def test_to_markdown_no_producer_scenes_shows_none_message(self):
        p = _tmp(SCENE_NO_PRODUCER)
        agg = analyze_corpus([p])
        md = to_markdown(agg)
        self.assertIn("No producer-intent scenes detected", md)
        os.remove(p)


if __name__ == "__main__":
    unittest.main()
