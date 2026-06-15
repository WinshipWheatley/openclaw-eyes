import json
import sqlite3
from datetime import datetime
from pathlib import Path

import cassandra_telegram_delivery as delivery
from business_ops_ledger import init_business_ops_ledger


FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0)


def _seed_ledger(db_path: Path) -> None:
    init_business_ops_ledger(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_id, ts, event_type, actor, operator_visible_summary,
                raw_sensitive_data_stored, replay_safe
            )
            VALUES (?, ?, ?, ?, ?, 0, 1)
            """,
            (
                "evt-reynolds",
                "2026-06-15T11:58:00",
                "lane_b_packet",
                "codex",
                "Reynolds package and Cassandra recommendations are ready for operator review.",
            ),
        )
        conn.execute(
            """
            INSERT INTO packets (
                packet_id, event_id, intent_name, request_category, actor_name,
                execution_authority, approval_required, approval_tier,
                action_status, packet_json_safe
            )
            VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
            """,
            (
                "packet-reynolds",
                "evt-reynolds",
                "reynolds_package_review",
                "operator_review",
                "cassandra",
                "operator_final_send",
                "pending_approval",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO side_effects (
                packet_id, effect_type, status, approval_required,
                approval_tier, replay_safe, external_ref
            )
            VALUES (?, ?, ?, 1, ?, 0, NULL)
            """,
            (
                "packet-reynolds",
                "email_draft_candidate",
                "pending_approval",
                "operator_final_send",
            ),
        )
        conn.commit()


def _brief(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "# Operator Brief",
                "",
                "Lane B built Cassandra's actionable recommendation loop.",
                "Lane B also prepared the Reynolds reply watcher and Telegram delivery surface.",
                "Nothing external was sent.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _load_log(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_operator_brief_routes_through_failover_and_dry_runs_when_toggle_off(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _seed_ledger(db_path)
    log_path = tmp_path / "telegram_dryrun.jsonl"

    receipt = delivery.deliver_operator_brief_to_telegram(
        brief_path=_brief(tmp_path / "cassandra_operator_brief.md"),
        db_path=db_path,
        env={},
        toggle_path=tmp_path / "missing_toggle.flag",
        dry_run_log_path=log_path,
        now=FIXED_NOW,
    )

    assert receipt.status == "dry_run_logged_toggle_off"
    assert receipt.delivery_kind == "operator_brief"
    assert receipt.failover_provider == "cassandra"
    assert receipt.dry_run is True
    assert receipt.sent is False
    assert receipt.telegram_send_attempted is False
    assert receipt.telegram_sender_called is False
    assert receipt.external_client_send_performed is False
    assert receipt.email_send_performed is False
    assert receipt.send_hold_touched is False
    assert "Lane B built Cassandra's actionable recommendation loop" in receipt.message_text
    assert "open approval packets 1" in receipt.message_text

    logged = _load_log(log_path)
    assert logged["status"] == "dry_run_logged_toggle_off"
    assert logged["message_hash"] == receipt.message_hash
    assert "message_text" not in logged
    assert logged["external_client_send_performed"] is False
    assert logged["send_hold_touched"] is False


def test_operator_brief_sends_only_to_authorized_telegram_when_toggle_on(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _seed_ledger(db_path)
    toggle_path = tmp_path / "telegram_enabled.flag"
    toggle_path.write_text("enabled by test\n", encoding="utf-8")
    sent = []

    def fake_sender(text, *, chat_id):
        sent.append({"text": text, "chat_id": chat_id})

    receipt = delivery.deliver_operator_brief_to_telegram(
        brief_path=_brief(tmp_path / "cassandra_operator_brief.md"),
        db_path=db_path,
        env={delivery.AUTHORIZED_USER_ID_ENV_VAR: "123456"},
        toggle_path=toggle_path,
        dry_run_log_path=tmp_path / "telegram_dryrun.jsonl",
        telegram_sender=fake_sender,
        now=FIXED_NOW,
    )

    assert receipt.status == "sent_to_authorized_telegram"
    assert receipt.sent is True
    assert receipt.dry_run is False
    assert receipt.telegram_send_attempted is True
    assert receipt.telegram_sender_called is True
    assert receipt.target_ref == f"env:{delivery.AUTHORIZED_USER_ID_ENV_VAR}"
    assert receipt.authorized_telegram_only is True
    assert receipt.external_client_send_performed is False
    assert sent == [{"text": receipt.message_text, "chat_id": "123456"}]
    assert "123456" not in json.dumps(receipt.to_dict(), sort_keys=True)


def test_operator_brief_missing_artifact_falls_back_without_error(tmp_path):
    receipt = delivery.deliver_operator_brief_to_telegram(
        brief_path=tmp_path / "missing.md",
        db_path=tmp_path / "missing-ledger.sqlite",
        env={},
        toggle_path=tmp_path / "missing_toggle.flag",
        dry_run_log_path=tmp_path / "telegram_dryrun.jsonl",
        now=FIXED_NOW,
    )

    assert receipt.status == "dry_run_logged_toggle_off"
    assert receipt.failover_provider == "guardian"
    assert [attempt["provider"] for attempt in receipt.failover_attempts] == [
        "cassandra",
        "chief",
        "hermes",
        "guardian",
    ]
    assert receipt.sent is False
    assert "Guardian morning failover" in receipt.message_text


def test_reynolds_package_delivery_is_display_only_and_dry_run_by_default(tmp_path):
    receipt = delivery.deliver_reynolds_package_to_telegram(
        intro_email_summary="Intro email says the June 27 Reynolds set is ready for Sally to review.",
        invoice_pdf_path=tmp_path / "Winship_Reynolds_2026-06-27.pdf",
        package_ready=True,
        env={},
        toggle_path=tmp_path / "missing_toggle.flag",
        dry_run_log_path=tmp_path / "telegram_dryrun.jsonl",
    )

    assert receipt.status == "dry_run_logged_toggle_off"
    assert receipt.delivery_kind == "reynolds_package"
    assert receipt.sent is False
    assert receipt.telegram_send_attempted is False
    assert receipt.external_client_send_performed is False
    assert "Intro-email summary" in receipt.message_text
    assert "Winship_Reynolds_2026-06-27.pdf" in receipt.message_text
    assert "SEND_HOLD-bound" in receipt.message_text
