from launch_ladder_contract_check import (
    OMITTED_CURRENT_PRODUCT_SPEC_FILES,
    UPLOADED_CURRENT_PRODUCT_SPEC,
    UPLOAD_AUTHORITY_COMMIT,
    check_contract,
    freshness_warnings,
    load_corpus,
)


def test_launch_ladder_static_contract_is_present():
    report = check_contract()
    assert report.failures == ()


def test_current_product_spec_source_set_warnings_are_preserved():
    corpus = load_corpus()
    warnings = freshness_warnings(corpus)
    joined = "\n".join(warnings)

    assert UPLOADED_CURRENT_PRODUCT_SPEC in joined
    assert UPLOAD_AUTHORITY_COMMIT in joined
    assert "generated MANIFEST.md" in joined
    assert "upload authority" in joined
    assert "package-level freshness markers" in joined
    assert OMITTED_CURRENT_PRODUCT_SPEC_FILES[0] in joined
    assert "do not generate Mac/iOS app-build prompts" in joined
    assert "Freshness normalization TODO" in joined


def test_source_set_ladder_delta_bridge_contract_is_present():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text.lower()

    assert "CHAT_STAY_UP_TO_DATE.md" in corpus.launch_ladder_text
    assert "Source-Set Ladder" in corpus.launch_ladder_text
    assert "source-set folders are not launch ladder steps" in launch_text
    assert "DELTA_BRIDGE_NAME" in corpus.script_text
    assert "counted_in_24=false" in corpus.script_text
