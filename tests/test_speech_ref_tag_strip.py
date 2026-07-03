"""Voice strips machine-ref/provenance tags; the text the operator reads keeps them.

Operator ask 2026-07-03: the "[Maestro-native reply - ref 734:573e5b]" tag is fine in the
text reply but is noise when spoken aloud.
"""

from speech_render import to_speech_text


def test_strips_native_reply_ref_tag():
    text = "Because it wanted to get to the other side, duh.\n\n[Maestro-native reply - ref 734:573e5b]"
    spoken = to_speech_text(text)
    assert "ref" not in spoken.lower()
    assert "573e5b" not in spoken
    assert "native reply" not in spoken.lower()
    assert "other side" in spoken.lower()


def test_strips_generic_ref_bracket():
    for tag in ("[Cassandra-native reply - ref 12:abc123]",
                "[ref 999:deadbe]",
                "[Niles reply - ref 55:0f0f0f]"):
        spoken = to_speech_text(f"Here is the answer. {tag}")
        assert "ref" not in spoken.lower()
        assert "answer" in spoken.lower()


def test_keeps_ordinary_brackets_and_words():
    # 'reference' the word and a non-machine bracket must survive.
    spoken = to_speech_text("Check the [studio] and reference the setlist.")
    assert "studio" in spoken.lower()
    assert "reference" in spoken.lower()


def test_empty_after_strip_is_safe():
    spoken = to_speech_text("[Maestro-native reply - ref 1:aaaaaa]")
    assert spoken == "" or "ref" not in spoken.lower()
