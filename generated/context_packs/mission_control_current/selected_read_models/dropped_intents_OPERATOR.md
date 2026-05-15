# Dropped Intent Registry Read-Model v0

What this is:
- A generated read-model over `dropped_intent_*` SQLite rows.
- It surfaces old unresolved, deferred, built, or unknown-review directions so Chief can later ask whether they still matter.

What this is not:
- It is not autonomous prompting, notification, action creation, approval, execution, model calling, agent activation, or file reorganization.

Summary:
- Total dropped-intent candidates: 9.
- Unresolved: 2.
- Deferred: 6.
- Built: 1.
- Superseded: 0.
- Unknown review: 0.
- By agent: chief=7, niles=1, report_bridge=1.
- By world: build=1, business_development=1, communications=1, music_art=1, operations=5.

Top unresolved:
- Mission Control action request writing: Do you want Mission Control to draft action request files into the E-drive inbox next?
- Recent File Context Resolver: Do you want to build recent-file context resolution over File Event Queue metadata?

Deferred / built samples:
- deferred: Automatic file watcher daemon
- deferred: Legacy GitHub Repo Intake v0.1
- deferred: Niles / Producer Telegram lane
- deferred: Project Capsule v0.1 / Real Template Workflow
- deferred: Report Bridge Sample Package v0
- built: Mission Control read-model refresh

Authority boundary:
- notification_allowed=false; autonomous_prompting_allowed=false.
- action_auto_create_allowed=false; action_auto_approve_allowed=false; action_auto_execute_allowed=false.
- agent_activation_allowed=false; network_authority=false; model_call_allowed=false.
- raw_private_scan_allowed=false; file_move_allowed=false; file_delete_allowed=false.

Next safe move:
- Surface this read-model as Chief planning context; ask before turning any item into a lane or action request.
