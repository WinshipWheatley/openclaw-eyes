"""
Business Ops Packet v0.

Formalized Context/Capability Packet layer for the OpenClaw Business Ops Spine.
This module defines the structured handoff between intent classification and
capability execution.

Spine flow:
1. Operator Prompt
2. Deterministic Intent
3. Context/Capability Packet  <-- This module
4. Permitted Retrieval
5. Response/Draft
6. Chief/Guardian Approval
7. Logged Receipt
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence

from backend_knowledge_packet import AgentContextExportPacket
from capability_registry import Capability, Actor, get_actor
from business_ops_intent import IntentFrame, classify_business_ops_intent


@dataclass(frozen=True)
class BusinessOpsPacket:
    """
    A policy-checked, deterministic packet containing only what is permitted
    for a specific operator request.
    """

    packet_id: str
    query: str
    intent_name: str
    request_category: str
    actor_name: str
    
    # Bounded context (data)
    context: Optional[AgentContextExportPacket] = None
    
    # Permitted capabilities (tools)
    permitted_capabilities: tuple[Capability, ...] = field(default_factory=tuple)
    
    # Safety posture
    safety_covenant_required: bool = True
    execution_authority: bool = False
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "query": self.query,
            "intent_name": self.intent_name,
            "request_category": self.request_category,
            "actor_name": self.actor_name,
            "has_context": self.context is not None,
            "permitted_capability_names": [c.name for c in self.permitted_capabilities],
            "safety_covenant_required": self.safety_covenant_required,
            "execution_authority": self.execution_authority,
            "created_at": self.created_at,
        }


def assemble_business_ops_packet(
    query: str,
    actor_name: str,
    intent: Optional[IntentFrame] = None,
    context: Optional[AgentContextExportPacket] = None,
) -> BusinessOpsPacket:
    """
    Factory for BusinessOpsPacket. 
    Filters capabilities based on intent and actor trust.
    """
    if intent is None:
        intent = classify_business_ops_intent(query)

    actor = get_actor(actor_name)
    if not actor:
        # Fallback to empty packet if actor is unknown
        return BusinessOpsPacket(
            packet_id=str(uuid.uuid4()),
            query=query,
            intent_name=intent.intent_name,
            request_category=intent.request_category,
            actor_name=actor_name,
            context=context,
            permitted_capabilities=(),
        )

    # Filter capabilities based on intent domain
    permitted = []
    
    target_domain = intent.domain
    
    for cap in actor.capabilities:
        if not cap.connected:
            continue
            
        # If we have a specific target domain, only allow that + logging
        if target_domain != "none":
            if cap.domain == target_domain or cap.domain == "logging":
                permitted.append(cap)
        else:
            # If no specific domain (e.g. general query), only allow read-only status
            if "read" in cap.scope and cap.domain in ("logging", "notes"):
                permitted.append(cap)

    return BusinessOpsPacket(
        packet_id=str(uuid.uuid4()),
        query=query,
        intent_name=intent.intent_name,
        request_category=intent.request_category,
        actor_name=actor_name,
        context=context,
        permitted_capabilities=tuple(permitted),
    )
