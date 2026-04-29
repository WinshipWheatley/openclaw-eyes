import sys


sys.path.insert(0, "/home/openclaw")


def test_cassandra_capability_context_names_gmail_draft_tier1_and_send_tier2():
    import cassandra_capability

    context = cassandra_capability.capability_context()
    lowered = context.lower()

    assert "email_draft: connected" in lowered
    assert "gmail draft" in lowered
    assert "tier 1" in lowered

    assert "email_send: not connected" in lowered
    assert "not direct or autonomous" in lowered
    assert "class c / tier 2" in lowered


def test_capability_registry_email_claims_match_google_broker_policy():
    import google_access_policy as policy
    from capability_registry import get_actor

    assert policy.get_class("cassandra", "google.gmail.read.body") == policy.CLASS_B
    assert policy.get_class("cassandra", "google.gmail.draft.create") == policy.CLASS_B
    assert policy.get_class("cassandra", "google.gmail.send") == policy.CLASS_C

    actor = get_actor("cassandra")
    caps = {cap.name: cap for cap in actor.capabilities}
    draft_caveat = caps["email_draft"].caveats.lower()
    send_caveat = caps["email_send"].caveats.lower()
    combined = f"{draft_caveat} {send_caveat}"

    assert "class b / tier 1" in draft_caveat
    assert "class c / tier 2" in send_caveat
    assert "direct or autonomous send" in send_caveat
    assert "class a" not in combined
