from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from apps.api.aiopt_web.capability_scoring import profile_for
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
