# Trading knowledge schema

Defined in `src/xau_edge/video_intel/knowledge.py` (pydantic, `extra="forbid"`, so unknown fields and invalid statuses are rejected). Stored as `data/video_knowledge/<video_id>/knowledge.json`, a plain file store written atomically; no second database was created. One committed example: `docs/video-intelligence/knowledge/d34e96f7f2e6.json`.

| Model | Fields (summary) |
|---|---|
| `VideoRecord` | id, source_url, platform, title, author, access_status, access_code, processing_status, duration_s, width, height, has_audio, file_sha256, processed_at, provenance |
| `TranscriptSegment` | video_id, start_ms, end_ms, text (untrusted), language, low_confidence |
| `VisualEvidence` | video_id, timestamp_ms, frame_reference, ocr_text, observations, status, uncertain |
| `Claim` | claim_id, video_id, evidence_refs, assertion, status, verification, citations (only sources actually read) |
| `TradingConcept` | concept_id, name, alt_names, rules, configurable_disagreements, invalidation, entry, stop_loss, target, repaint_risk, failure_modes, validation_status |
| `ImplementationLink` | concept_id, requirement_id, source_file, test_file, implementation_status (IMPLEMENTED, PLANNED, BLOCKED) |
| `VideoKnowledge` | one video: record, transcript, transcript_note, visual, claims, concepts, links |

Evidence statuses: OBSERVED (seen or heard with a timestamp), CLAIMED (author asserts), INFERRED (ours), VALIDATED (independent evidence we opened or ran), UNVERIFIED, DISPROVEN.

Query: `uv run python scripts/video_intel.py ask d34e96f7f2e6 wolf wave` returns the concept, its evidence-labelled claims and the code and test links. Alternative names match case-insensitively.

Not in the schema (PLANNED): speaker segments, per-frame OCR boxes, cross-video concept merging.
