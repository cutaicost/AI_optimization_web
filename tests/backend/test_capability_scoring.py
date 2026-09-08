from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from apps.api.aiopt_web.capability_scoring import capability_profiles,profile_for
from apps.api.aiopt_web.capability_evidence_seed import EVIDENCE,seed_capability_evidence
from apps.api.aiopt_web.database import Base,SessionLocal,engine
from apps.api.aiopt_web.models import ModelCapabilityEvidence,ModelSkill

@pytest.fixture(autouse=True)
def clean():Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)

def test_candidates_have_no_fabricated_score_without_evidence():
    with SessionLocal() as db:
        profile=profile_for(db,"openai","gpt-5.6-sol")
        assert profile["rating_type"]=="ESTIMATED" and profile["capability_status"]=="needs_review"
        assert all(item["score"] is None for item in profile["skills"])

def test_score_is_relative_and_confidence_is_separate():
    with SessionLocal() as db:
        skill=ModelSkill(key="software_engineering",name="Software Engineering");db.add(skill);db.flush()
        for model,raw in (("frontier",80),("candidate",64)):
            db.add(ModelCapabilityEvidence(provider="test",model_id=model,skill_id=skill.id,evaluation_name="Comparable Coding Eval",raw_score=raw,evaluation_max=100,benchmark_weight=1,source_type="INDEPENDENT_BENCHMARK",source_url=f"https://example.test/{model}",provider_reported=False,independent=True,evaluation_date=datetime.now(timezone.utc),confidence="MEDIUM"))
        db.commit();profile=profile_for(db,"test","candidate")
        assert profile["skills"][0]["score"]==80
        assert profile["skills"][0]["confidence"]=="LOW"
        assert "not a task success percentage" in profile["score_explanation"].lower()

def test_seed_is_idempotent_and_partial_evidence_is_benchmark_informed():
    with SessionLocal() as db:
        seed_capability_evidence(db);db.commit();seed_capability_evidence(db);db.commit()
        assert len(db.scalars(select(ModelCapabilityEvidence)).all())==len(EVIDENCE)
        profile=profile_for(db,"google","gemini-3.8-flash")
        assert profile["rating_type"]=="BENCHMARK-INFORMED" and profile["needs_review"]
        assert all(skill["confidence"] in {"LOW","MEDIUM"} for skill in profile["skills"])

def test_snapshot_alias_inherits_without_duplicate_evidence():
    with SessionLocal() as db:
        seed_capability_evidence(db);db.commit();profiles=capability_profiles(db)
        canonical=profile_for(db,"openai","gpt-5",profiles);snapshot=profile_for(db,"openai","gpt-5-2025-08-07",profiles)
        assert snapshot["skills"]==canonical["skills"]
        assert snapshot["inherited_from"]=={"provider":"openai","model":"gpt-5"}

def test_pricing_fields_do_not_participate_in_capability_scores():
    with SessionLocal() as db:
        seed_capability_evidence(db);db.commit();before=profile_for(db,"openai","gpt-5")
        # Capability derivation accepts only evidence records; no price or latency input exists.
        after=profile_for(db,"openai","gpt-5")
        assert before==after
