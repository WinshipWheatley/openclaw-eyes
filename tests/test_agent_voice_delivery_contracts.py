"""
Voice delivery contracts: verify AGENT_KOKORO_VOICES map is consistent with
agent_voice_profiles speaker_refs, and that each agent's voice is stable
across module reloads.
"""
import importlib
import sys
import types


# ── Expected contracts ────────────────────────────────────────────────────────

EXPECTED_VOICES = {
    "maestro":   "am_michael",
    "cassandra": "af_heart",
    "chief":     "bm_george",
    "guardian":  "am_onyx",
    "niles":     "am_puck",
    "hermes":    "am_echo",
}

# Piper model path suffix used as sentinel — voice assignment must NOT be a path
_PIPER_PATH_SENTINEL = ".onnx"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _load_kokoro_voice_module():
    if "agent_kokoro_voice" in sys.modules:
        del sys.modules["agent_kokoro_voice"]
    # Stub kokoro so the module loads without the package installed
    if "kokoro" not in sys.modules:
        sys.modules["kokoro"] = types.ModuleType("kokoro")
    import agent_kokoro_voice
    return agent_kokoro_voice


def _load_voice_profiles_module():
    if "agent_voice_profiles" in sys.modules:
        del sys.modules["agent_voice_profiles"]
    import agent_voice_profiles
    return agent_voice_profiles


# ── Voice map correctness ─────────────────────────────────────────────────────

def test_maestro_voice_is_am_michael():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("maestro") == "am_michael"


def test_cassandra_voice_is_af_heart():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("cassandra") == "af_heart"


def test_chief_voice_is_bm_george():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("chief") == "bm_george"


def test_guardian_voice_is_am_onyx():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("guardian") == "am_onyx"


def test_niles_voice_is_am_puck():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("niles") == "am_puck"


def test_hermes_voice_is_am_echo():
    import agent_kokoro_voice as akv
    assert akv.voice_for_agent("hermes") == "am_echo"


# ── Voice IDs are Kokoro IDs, not piper model paths ──────────────────────────

def test_no_agent_voice_is_a_piper_path():
    import agent_kokoro_voice as akv
    for agent, voice_id in akv.AGENT_KOKORO_VOICES.items():
        assert _PIPER_PATH_SENTINEL not in voice_id, (
            f"{agent} voice_id '{voice_id}' looks like a Piper model path"
        )


# ── Stability across module reload ───────────────────────────────────────────

def test_voice_map_stable_across_reload():
    akv = _load_kokoro_voice_module()
    voices_before = dict(akv.AGENT_KOKORO_VOICES)
    importlib.reload(akv)
    voices_after = dict(akv.AGENT_KOKORO_VOICES)
    assert voices_before == voices_after


def test_voice_for_agent_stable_across_reload():
    akv = _load_kokoro_voice_module()
    before = {a: akv.voice_for_agent(a) for a in EXPECTED_VOICES}
    importlib.reload(akv)
    after = {a: akv.voice_for_agent(a) for a in EXPECTED_VOICES}
    assert before == after == EXPECTED_VOICES


# ── Cross-check: profiles speaker_refs are covered by voice map ───────────────

def test_every_profile_speaker_ref_has_voice_map_entry():
    import agent_kokoro_voice as akv
    import agent_voice_profiles as avp
    read_model = avp.build_read_model()
    for profile in read_model["profiles"]:
        ref = profile.get("speaker_ref", "")
        if ref in ("clara", "openclaw"):
            continue  # utility profiles, not first-class voice agents
        assert ref in akv.AGENT_KOKORO_VOICES, (
            f"speaker_ref '{ref}' has no entry in AGENT_KOKORO_VOICES"
        )


def test_expected_agents_all_covered_by_profiles():
    import agent_voice_profiles as avp
    read_model = avp.build_read_model()
    profile_refs = {p["speaker_ref"] for p in read_model["profiles"]}
    for agent in EXPECTED_VOICES:
        assert agent in profile_refs, f"Agent '{agent}' missing from voice profiles"


def test_clara_is_cassandra_external_register_not_separate_agent():
    import agent_voice_profiles as avp
    read_model = avp.build_read_model()
    profiles = {p["speaker_ref"]: p for p in read_model["profiles"]}

    cassandra = profiles["cassandra"]
    clara = profiles["clara"]

    assert clara["agent_id"] == "cassandra"
    assert clara["register_ref"] == "clara_reid_external"
    assert clara["register_kind"] == "external_client_facing"
    assert clara["internal_register_ref"] == "cassandra_internal"
    assert clara["authority_boundary"] == cassandra["authority_boundary"]


def test_frontdoor_clara_alias_speaks_as_cassandra_external_register():
    import frontdoor_prompt

    persona = frontdoor_prompt._conversational_persona("clara")

    assert "Cassandra" in persona
    assert "Clara Reid" in persona
    assert "external" in persona.lower()


def test_no_clara_reed_typo_in_canonical_doctrine():
    import json
    import canonical_doctrine_facts as facts

    payload = json.dumps(facts.SHARED_DOCTRINE_FACTS, sort_keys=True)

    stale_spelling = "Clara " + "Reed"
    assert stale_spelling not in payload
    assert "Clara Reid" in payload
