# Data Room Clean Load Dry Run Plan

## Summary

| Field | Value |
| --- | --- |
| Source | `/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md` |
| Source hash | `2c7533b6eeab2fcdaf62a2aac97d02bd90d94952f09cfd3bf74ec6608c9c02a9` |
| Source revision for planned rows | `source_sha256:2c7533b6eeab2fcd` |
| Target table | `canonical_facts` |
| Dry run only | `true` |
| Planned writes | `40` |
| DB check | `checked` |

## Planned Key Value Writes

| Key | Value | Fact ID | Hash | Sensitivity | Actors |
| --- | --- | --- | --- | --- | --- |
| `business_config.services.live_music_performance` | Live music performance (solo, or band-fronted) | `dataroom_confirmed_reference:services:live_music_performance` | `f59a13430229` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.services.sound_engineering_audio_engineer` | Sound engineering / audio engineer | `dataroom_confirmed_reference:services:sound_engineering_audio_engineer` | `9d03bfb70374` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.services.a_v_technician` | A/V technician | `dataroom_confirmed_reference:services:a_v_technician` | `2937c63b0bfd` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.services.systems_engineering` | Systems engineering - sound-system tuning | `dataroom_confirmed_reference:services:systems_engineering` | `d839234edfa7` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.rate_card.corporate_dc_baltimore_annapolis` | Corporate (DC / Baltimore / Annapolis): from $2,000 | `dataroom_confirmed_reference:rate_card:corporate_dc_baltimore_annapolis` | `bc7152157a96` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.rate_card.corporate_ocean_city_md` | Corporate (Ocean City, MD): from $2,500 | `dataroom_confirmed_reference:rate_card:corporate_ocean_city_md` | `dccef8c562d9` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.rate_card.one_off_local_e_g_reynolds_3_hr` | One-off local (e.g. Reynolds, ~3 hr): ~$250 | `dataroom_confirmed_reference:rate_card:one_off_local_e_g_reynolds_3_hr` | `f20e9e8fe707` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.rate_card.weekly_recurring_restaurant_hotel` | Weekly / recurring (restaurant/hotel): discounted - e.g. Capital Hilton $400/week (happy with it because weekly) | `dataroom_confirmed_reference:rate_card:weekly_recurring_restaurant_hotel` | `f3f13d1ff8c8` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.rate_card.tech_work` | Tech work (audio/AV/systems): rate TBD - pending Draper's email on how Live Arts pays him as a tech | `dataroom_confirmed_reference:rate_card:tech_work` | `f12393984d49` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.rate_card.rule` | Rule: recurring/weekly earns a break; one-offs and corporate at full rate. | `dataroom_confirmed_reference:rate_card:rule` | `7d59398edef5` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.clients_payers_contacts.capital_hilton_dc` | Capital Hilton (DC) - pays via Coupa (check on the 1st of the month). Contacts: Annette (finance/AP lead), Chyna (finance, under Annette), Will (got him the gig), Sam (bar manager). Flow: send invoice from his "Capital Hilton" Excel workbook -> follow up w/ Annette to expedite. Service: live music, weekly, $400/wk. | `dataroom_confirmed_reference:clients_payers_contacts:capital_hilton_dc` | `9b67f0da6628` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.clients_payers_contacts.reynolds_tavern_annapolis` | Reynolds Tavern (Annapolis) - Sally (owner), reservations@reynoldstavern.com. NEW client. Service: live music. Identity: Winship Wheatley. Terms: TBD (see open items). | `dataroom_confirmed_reference:clients_payers_contacts:reynolds_tavern_annapolis` | `fc93321c5a86` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.clients_payers_contacts.live_arts_md` | Live Arts MD! - pays via a new accountant (name TBD - lookup once system reads email). Service: audio engineering. | `dataroom_confirmed_reference:clients_payers_contacts:live_arts_md` | `ba8f8e1bb955` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.clients_payers_contacts.st_annes` | St. Annes - Service: A/V tech. Payment routes: Winship -> Draper (sends his dates/events) -> Draper emails Glenn Mortoro (St. Annes Treasurer) -> Glenn pays. | `dataroom_confirmed_reference:clients_payers_contacts:st_annes` | `6545d5a78b19` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.clients_payers_contacts.key_intermediary` | Key intermediary: Draper - routes St. Annes pay + holds the Live Arts tech-pay email. Also Dane re: Live Arts pay. | `dataroom_confirmed_reference:clients_payers_contacts:key_intermediary` | `c00c467cedcc` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_terms.default` | Default: due upon receipt (everyone). | `dataroom_confirmed_reference:payment_terms:default` | `39825d9086c7` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_terms.capital_hilton` | Capital Hilton: Coupa monthly (check 1st); chased via invoice + Annette to expedite. | `dataroom_confirmed_reference:payment_terms:capital_hilton` | `2c23df15e125` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_terms.reynolds` | Reynolds: new - state terms (see open items). | `dataroom_confirmed_reference:payment_terms:reynolds` | `e0fe060e8c53` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_methods_remit_by_trust_tier.default_new_forming` | Default (new/forming): cash, check. | `dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:default_new_forming` | `2e2bd61b4eff` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_methods_remit_by_trust_tier.semi_trusted` | Semi-trusted: Zelle (cautious - doesn't want personal # handed out widely). | `dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:semi_trusted` | `250001b44a31` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_methods_remit_by_trust_tier.fully_trusted_recurring_multi_payment` | Fully trusted + recurring multi-payment: direct deposit (bank) + home address. | `dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:fully_trusted_recurring_multi_payment` | `e8988dd24af3` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.payment_methods_remit_by_trust_tier.trust_gated_hidden_by_default` | Trust-gated (hidden by default): bank details and home address - same tier, revealed together only to trusted payers. | `dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:trust_gated_hidden_by_default` | `978a3c15f9e5` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.legal_name` | Legal name: Henry Winship Wheatley IV | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:legal_name` | `79691326cd88` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.business_sole_prop` | Business (sole prop): Winship Live | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:business_sole_prop` | `9068f7472022` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.solo_artist_casual` | Solo artist, casual: "Winship" | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:solo_artist_casual` | `3b86ca097f88` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.band_event_he_fronts_corporate_gig` | Band event he fronts / corporate gig: "Winship Live" | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:band_event_he_fronts_corporate_gig` | `3eadb55ca033` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.church_low_key_local` | Church / low-key / local: "Winship Wheatley" | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:church_low_key_local` | `abc6fb9e5cf6` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.reynolds_winship_wheatley` | Reynolds -> Winship Wheatley (local, low-key) | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:reynolds_winship_wheatley` | `4347bd334bca` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.identity_from_name_sliding_scale_by_formality.default_invoice_identity` | Default invoice identity: Winship Wheatley OR Winship Live (proposed rule: Winship Live for corporate, Winship Wheatley for local/church/low-key) | `dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:default_invoice_identity` | `db52bd57617b` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.personas.cassandra` | Cassandra = internal/inner-circle name. Clara Reid = her public-facing name (for clients still forming a relationship). Inner circle may use either. | `dataroom_confirmed_reference:personas:cassandra` | `43ed821d44e1` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.personas.fundo` | Fundo = dormant concept only. No capability, no agent. Possible future alt-persona (costume + perform) if a non-Winship track ever takes off. Build nothing for it now. | `dataroom_confirmed_reference:personas:fundo` | `868ab6e2f1af` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.personas.persona_review` | Persona review: all persona choices reviewed during setup. | `dataroom_confirmed_reference:personas:persona_review` | `5330f8970858` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.expense_categories.source` | Source: his tax workbook in iCloud -> "Taxes 2025." System should ingest it for labels (Q11-14). Not done yet. | `dataroom_confirmed_reference:expense_categories:source` | `ab76a527cdaa` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.open_items_actions.time_sensitive_live_arts_md_payment_chase` | TIME-SENSITIVE - Live Arts MD! payment chase: if no response from Dane / Draper by this Thursday, reach back out. (Winship wants Cassandra as the money-chaser.) Draft ready, send on hold-lift. | `dataroom_confirmed_reference:open_items_actions:time_sensitive_live_arts_md_payment_chase` | `87c8fb250c59` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.open_items_actions.expense_labels` | Expense labels: ingest the iCloud "Taxes 2025" workbook -> fills Q11-14. | `dataroom_confirmed_reference:open_items_actions:expense_labels` | `5f1a7ed2959c` | `public_canonical` | `["cassandra","chief","guardian","hermes"]` |
| `business_config.open_items_actions.reynolds_terms` | Reynolds terms: decide + state them. (Recommendation below.) | `dataroom_confirmed_reference:open_items_actions:reynolds_terms` | `1535d7030725` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.open_items_actions.tech_work_rate` | Tech-work rate: pending Draper's email on Live Arts tech pay. | `dataroom_confirmed_reference:open_items_actions:tech_work_rate` | `c4870f526108` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.open_items_actions.live_arts_accountant_name` | Live Arts accountant name: look up once system can read email. | `dataroom_confirmed_reference:open_items_actions:live_arts_accountant_name` | `3a31f154851f` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.open_items_actions.capital_hilton_contacts` | Capital Hilton contacts: confirm Annette/Chyna/Will/Sam exist in the system; billing -> Annette/Chyna. | `dataroom_confirmed_reference:open_items_actions:capital_hilton_contacts` | `c81c13b14843` | `operational_canonical` | `["cassandra","chief","guardian"]` |
| `business_config.open_items_actions.new_capability` | New capability: Cassandra = "money chaser" (AR / payment follow-up). Queue it. | `dataroom_confirmed_reference:open_items_actions:new_capability` | `cce39901eb50` | `operational_canonical` | `["cassandra","chief","guardian"]` |

## Exact canonical_facts Rows

These are the exact fields the reviewed live load would write.

```json
[
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "f59a13430229f97dd47d81e523b2f3e8fedb194b380883d4e27aea24292abb49",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:services:live_music_performance",
    "fact_text": "Live music performance (solo, or band-fronted)",
    "section_heading": "Services",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "9d03bfb70374ca84bf9316d696609cb8b29b79827b2a69ca9b91215ad69b41d2",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:services:sound_engineering_audio_engineer",
    "fact_text": "Sound engineering / audio engineer",
    "section_heading": "Services",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "2937c63b0bfdbee00e3c15b5ee0dd288165d8be2650f44753b2666a9fb3a29fa",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:services:a_v_technician",
    "fact_text": "A/V technician",
    "section_heading": "Services",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "d839234edfa7a33bf857accbc1b609bb3d8ac3c1325a2c06d8f11033fb52d45c",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:services:systems_engineering",
    "fact_text": "Systems engineering - sound-system tuning",
    "section_heading": "Services",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "bc7152157a965a21583379f16cc4f019e18ac412d1f9e6b5ab4d5244da86febe",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:corporate_dc_baltimore_annapolis",
    "fact_text": "Corporate (DC / Baltimore / Annapolis): from $2,000",
    "section_heading": "Rate card",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "dccef8c562d9169c469b9b0a59c559067290204f1a9a8f95711124873cde6b2b",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:corporate_ocean_city_md",
    "fact_text": "Corporate (Ocean City, MD): from $2,500",
    "section_heading": "Rate card",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "f20e9e8fe707f2d6eb5a2cff325def18f9c35d3d640a73c1b2ea3697f93c7163",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:one_off_local_e_g_reynolds_3_hr",
    "fact_text": "One-off local (e.g. Reynolds, ~3 hr): ~$250",
    "section_heading": "Rate card",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "f3f13d1ff8c8767079794b22940809b69e6f02150394b7a768338323b8964cc8",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:weekly_recurring_restaurant_hotel",
    "fact_text": "Weekly / recurring (restaurant/hotel): discounted - e.g. Capital Hilton $400/week (happy with it because weekly)",
    "section_heading": "Rate card",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "f12393984d49db1d498abeb52c6dea3c76b46d09efed9b85f4173cd6327bc1cb",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:tech_work",
    "fact_text": "Tech work (audio/AV/systems): rate TBD - pending Draper's email on how Live Arts pays him as a tech",
    "section_heading": "Rate card",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "7d59398edef5d63e7553f9fe4ef351c6c0bb73ff5408d598cf976f9b85e96f5f",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:rate_card:rule",
    "fact_text": "Rule: recurring/weekly earns a break; one-offs and corporate at full rate.",
    "section_heading": "Rate card",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "9b67f0da6628a2828f22caaa569158e5ec32c41fb931b23a8316e7c88f460a94",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:clients_payers_contacts:capital_hilton_dc",
    "fact_text": "Capital Hilton (DC) - pays via Coupa (check on the 1st of the month). Contacts: Annette (finance/AP lead), Chyna (finance, under Annette), Will (got him the gig), Sam (bar manager). Flow: send invoice from his \"Capital Hilton\" Excel workbook -> follow up w/ Annette to expedite. Service: live music, weekly, $400/wk.",
    "section_heading": "Clients / payers (+ contacts)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "fc93321c5a8686b442b2bf5706cb38adc9f5e3313b69d866f64bf0da7a3e1bec",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:clients_payers_contacts:reynolds_tavern_annapolis",
    "fact_text": "Reynolds Tavern (Annapolis) - Sally (owner), reservations@reynoldstavern.com. NEW client. Service: live music. Identity: Winship Wheatley. Terms: TBD (see open items).",
    "section_heading": "Clients / payers (+ contacts)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "ba8f8e1bb955ca02bbb08a0645305da4eac6617290920794e2fa73c3c1fe69a2",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:clients_payers_contacts:live_arts_md",
    "fact_text": "Live Arts MD! - pays via a new accountant (name TBD - lookup once system reads email). Service: audio engineering.",
    "section_heading": "Clients / payers (+ contacts)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "6545d5a78b19c416e47fe0a49982b5722916fd97c187681465aba0140be0bbb8",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:clients_payers_contacts:st_annes",
    "fact_text": "St. Annes - Service: A/V tech. Payment routes: Winship -> Draper (sends his dates/events) -> Draper emails Glenn Mortoro (St. Annes Treasurer) -> Glenn pays.",
    "section_heading": "Clients / payers (+ contacts)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "c00c467cedcc25a828ffd54319049a088859f203cc66fd2f284f7097767d4a4c",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:clients_payers_contacts:key_intermediary",
    "fact_text": "Key intermediary: Draper - routes St. Annes pay + holds the Live Arts tech-pay email. Also Dane re: Live Arts pay.",
    "section_heading": "Clients / payers (+ contacts)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "39825d9086c7c877a3cd7433cd0095e4100005c5d400439d8907aa1b734dc9a1",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_terms:default",
    "fact_text": "Default: due upon receipt (everyone).",
    "section_heading": "Payment terms",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "2c23df15e125625d42adef3cb2b79941a859788b62a91127e0fc255af75d6836",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_terms:capital_hilton",
    "fact_text": "Capital Hilton: Coupa monthly (check 1st); chased via invoice + Annette to expedite.",
    "section_heading": "Payment terms",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "e0fe060e8c538d87900a5e15be7e03df62bbeecd184676540220bf1088ad7d06",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_terms:reynolds",
    "fact_text": "Reynolds: new - state terms (see open items).",
    "section_heading": "Payment terms",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "2e2bd61b4eff1b08a6b40bc422edc7c3378bc45b70f8913660cbb69694757a8b",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:default_new_forming",
    "fact_text": "Default (new/forming): cash, check.",
    "section_heading": "Payment methods (remit) - by trust tier",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "250001b44a3167dab829a7bf4308401a1f2c7cbee42dc68cc4a0a3dd862aba43",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:semi_trusted",
    "fact_text": "Semi-trusted: Zelle (cautious - doesn't want personal # handed out widely).",
    "section_heading": "Payment methods (remit) - by trust tier",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "e8988dd24af333c154c3a527a75f0dd86c5b4f34da9e795e3619c9213d390e3a",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:fully_trusted_recurring_multi_payment",
    "fact_text": "Fully trusted + recurring multi-payment: direct deposit (bank) + home address.",
    "section_heading": "Payment methods (remit) - by trust tier",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "978a3c15f9e52fd01b62c33f7803b9c08a28f3475e2b51ac3bacaf5235dea6a6",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:payment_methods_remit_by_trust_tier:trust_gated_hidden_by_default",
    "fact_text": "Trust-gated (hidden by default): bank details and home address - same tier, revealed together only to trusted payers.",
    "section_heading": "Payment methods (remit) - by trust tier",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "79691326cd8826b08eb2e7fac491844ac47acd921db3385057ddb0d648e581c5",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:legal_name",
    "fact_text": "Legal name: Henry Winship Wheatley IV",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "9068f74720223d0b89a881b936277a0230b4ed4611e300f12aa72a1f8c9116de",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:business_sole_prop",
    "fact_text": "Business (sole prop): Winship Live",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "3b86ca097f88249cebeb0595998e9606fb323e1387606fb5c516f2bde3a9beea",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:solo_artist_casual",
    "fact_text": "Solo artist, casual: \"Winship\"",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "3eadb55ca033a3e5b4619997840016816aa1d0ab00d0d950a5ed206268db4156",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:band_event_he_fronts_corporate_gig",
    "fact_text": "Band event he fronts / corporate gig: \"Winship Live\"",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "abc6fb9e5cf6020512b11350b53e83f95b3182d2be0b66b3ae1c2d95dd9f09f8",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:church_low_key_local",
    "fact_text": "Church / low-key / local: \"Winship Wheatley\"",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "4347bd334bca2b2a75605a757e5a3f1107d8c21aea73676c14fe31cf36b8ae9e",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:reynolds_winship_wheatley",
    "fact_text": "Reynolds -> Winship Wheatley (local, low-key)",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "db52bd57617b76b10402322ff4c92789fcd6b5efdb277cd480f81c295b195031",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:identity_from_name_sliding_scale_by_formality:default_invoice_identity",
    "fact_text": "Default invoice identity: Winship Wheatley OR Winship Live (proposed rule: Winship Live for corporate, Winship Wheatley for local/church/low-key)",
    "section_heading": "Identity / from-name - sliding scale (by formality)",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "43ed821d44e1b578e0b91f12f9d43c413a2060a790b35b12e298d1f8b4a0ebb1",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:personas:cassandra",
    "fact_text": "Cassandra = internal/inner-circle name. Clara Reid = her public-facing name (for clients still forming a relationship). Inner circle may use either.",
    "section_heading": "Personas",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "868ab6e2f1af2694b116a6758b6cede07beabcf676b2fc62b889ae593a8ce11d",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:personas:fundo",
    "fact_text": "Fundo = dormant concept only. No capability, no agent. Possible future alt-persona (costume + perform) if a non-Winship track ever takes off. Build nothing for it now.",
    "section_heading": "Personas",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "5330f89708581a6c341c73e29b8479c664d21eb9403fbc2ef74721c9a8836a4d",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:personas:persona_review",
    "fact_text": "Persona review: all persona choices reviewed during setup.",
    "section_heading": "Personas",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "ab76a527cdaa97bd4f1c449da445e2a097133ef573e5be58f96e127b55b589f2",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:expense_categories:source",
    "fact_text": "Source: his tax workbook in iCloud -> \"Taxes 2025.\" System should ingest it for labels (Q11-14). Not done yet.",
    "section_heading": "Expense categories",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "87c8fb250c594065c268d6c6ddd8c288800c06f1d143a02c7bc30d1df8c4dd2a",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:time_sensitive_live_arts_md_payment_chase",
    "fact_text": "TIME-SENSITIVE - Live Arts MD! payment chase: if no response from Dane / Draper by this Thursday, reach back out. (Winship wants Cassandra as the money-chaser.) Draft ready, send on hold-lift.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\",\"hermes\"]",
    "content_hash": "5f1a7ed2959c3e4becf1040e051ee78493afa20beef690c6a5b8e34e63cc86a6",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:expense_labels",
    "fact_text": "Expense labels: ingest the iCloud \"Taxes 2025\" workbook -> fills Q11-14.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "public_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "1535d7030725c37c6079cbac48448de83258f94285ed41bd65b60a38dd53f38c",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:reynolds_terms",
    "fact_text": "Reynolds terms: decide + state them. (Recommendation below.)",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "c4870f52610810aeb7e9aa67720a852383973ba87335662eae709ca140f0a9b0",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:tech_work_rate",
    "fact_text": "Tech-work rate: pending Draper's email on Live Arts tech pay.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "3a31f154851f18b299892c57818e18126aac12938c63eb254211c178d1a60ac0",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:live_arts_accountant_name",
    "fact_text": "Live Arts accountant name: look up once system can read email.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "c81c13b148431b7e4c836cda4125d1c427a52f6140da0aa4a98a5de15e29f763",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:capital_hilton_contacts",
    "fact_text": "Capital Hilton contacts: confirm Annette/Chyna/Will/Sam exist in the system; billing -> Annette/Chyna.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  },
  {
    "allowed_actors": "[\"cassandra\",\"chief\",\"guardian\"]",
    "content_hash": "cce39901eb505aff3900beec71cd9fb92235a48440dadd17e2c61199b4777a50",
    "doc_category": "business_config",
    "fact_id": "dataroom_confirmed_reference:open_items_actions:new_capability",
    "fact_text": "New capability: Cassandra = \"money chaser\" (AR / payment follow-up). Queue it.",
    "section_heading": "OPEN ITEMS / ACTIONS",
    "sensitivity_class": "operational_canonical",
    "source_commit": "source_sha256:2c7533b6eeab2fcd",
    "source_description": "Winship confirmed Data Room reference dry-run source",
    "source_file": "/mnt/e/openclaw/orchestration/artifacts/dataroom/confirmed_reference.md",
    "temporal_or_doctrine": "declared_reference",
    "truth_source_id": "dataroom_confirmed_reference",
    "truth_status": "declared",
    "verification_evidence_id": null,
    "verification_required": 1
  }
]
```

## Conflicts

- None found.

## Idempotent Existing Rows

- None.

## Gaps And Ambiguities

| Key | Section | Reason | Value |
| --- | --- | --- | --- |
| `business_config.rate_card.tech_work` | Rate card | TBD value needs Winship or source confirmation. | Tech work (audio/AV/systems): rate TBD - pending Draper's email on how Live Arts pays him as a tech |
| `business_config.clients_payers_contacts.reynolds_tavern_annapolis` | Clients / payers (+ contacts) | TBD value needs Winship or source confirmation. | Reynolds Tavern (Annapolis) - Sally (owner), reservations@reynoldstavern.com. NEW client. Service: live music. Identity: Winship Wheatley. Terms: TBD (see open items). |
| `business_config.clients_payers_contacts.live_arts_md` | Clients / payers (+ contacts) | TBD value needs Winship or source confirmation. | Live Arts MD! - pays via a new accountant (name TBD - lookup once system reads email). Service: audio engineering. |
| `business_config.payment_terms.reynolds` | Payment terms | Payment terms need to be decided before live load. | Reynolds: new - state terms (see open items). |
| `business_config.identity_from_name_sliding_scale_by_formality.default_invoice_identity` | Identity / from-name - sliding scale (by formality) | Proposed rule needs review before live load. | Default invoice identity: Winship Wheatley OR Winship Live (proposed rule: Winship Live for corporate, Winship Wheatley for local/church/low-key) |
| `business_config.expense_categories.source` | Expense categories | Source ingestion is not complete. | Source: his tax workbook in iCloud -> "Taxes 2025." System should ingest it for labels (Q11-14). Not done yet. |
| `business_config.open_items_actions.time_sensitive_live_arts_md_payment_chase` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | TIME-SENSITIVE - Live Arts MD! payment chase: if no response from Dane / Draper by this Thursday, reach back out. (Winship wants Cassandra as the money-chaser.) Draft ready, send on hold-lift. |
| `business_config.open_items_actions.expense_labels` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | Expense labels: ingest the iCloud "Taxes 2025" workbook -> fills Q11-14. |
| `business_config.open_items_actions.reynolds_terms` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | Reynolds terms: decide + state them. (Recommendation below.) |
| `business_config.open_items_actions.tech_work_rate` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | Tech-work rate: pending Draper's email on Live Arts tech pay. |
| `business_config.open_items_actions.live_arts_accountant_name` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | Live Arts accountant name: look up once system can read email. |
| `business_config.open_items_actions.capital_hilton_contacts` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | Capital Hilton contacts: confirm Annette/Chyna/Will/Sam exist in the system; billing -> Annette/Chyna. |
| `business_config.open_items_actions.new_capability` | OPEN ITEMS / ACTIONS | Open action item; keep out of final business config until resolved or explicitly accepted. | New capability: Cassandra = "money chaser" (AR / payment follow-up). Queue it. |

## Safety Notes

- This plan does not write the live ledger.
- DB access, when requested, is read-only conflict detection.
- Trust-gated payment and home-address policy facts remain policy references only; no bank details or home address values are present in the staged source.
