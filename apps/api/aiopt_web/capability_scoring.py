"""Capability scores derived only from comparable evaluation evidence."""
from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import select
from .models import ModelCapabilityEvidence, ModelSkill

SCORE_EXPLANATION="CutAICost Capability Score. Relative model capability derived from available evaluations and normalized against models in the current catalog. This is not a task success percentage."

CANDIDATES={
 ("openai","gpt-6-astra"):("Advanced Reasoning","Mathematics","Software Engineering","Computer / Agentic Work"),
 ("openai","gpt-5.6-sol"):("Software Engineering","Cybersecurity","Scientific Reasoning","Computer / Tool Use"),
 ("openai","gpt-5.6-terra"):("Software Engineering","Tool / Computer Use","Scientific Reasoning","Cybersecurity"),
 ("openai","gpt-5.6-luna"):("Software Engineering","Tool Use","General Reasoning","Cybersecurity"),
 ("anthropic","claude-sonnet-5"):("Agentic Tasks","Software Engineering","Tool Use","Logical Reasoning"),
 ("anthropic","claude-haiku-4-5"):("Coding","Agentic Tasks","Computer Use","Tool Use"),
 ("cohere","command-a-03-2025"):("Enterprise RAG","Tool Use","Agentic Tasks","Multilingual"),
 ("cohere","command-a-plus-05-2026"):("Agentic Tasks","Multimodal Reasoning","Enterprise RAG","Multilingual"),
 ("deepseek","deepseek-v4-flash"):("Software Engineering","Agentic Tasks","Tool Use","Coding"),
 ("deepseek","deepseek-v4-pro"):("Agentic Tasks","Software Engineering","Tool Use","Scientific Reasoning"),
 ("google","gemini-3.8-flash"):("Software Engineering","Agentic Tasks","Logical Reasoning","Multimodal Reasoning"),
 ("google","gemini-2.5-pro"):("Multimodal Reasoning","Long-Context Analysis","Coding","Advanced Reasoning"),
 ("xai","grok-4.6"):("Agentic Tasks","Software Engineering","Knowledge Work","Research / Information Analysis"),
 ("perplexity","sonar"):("Web Research","Information Retrieval","Current Information","Summarization"),
 ("perplexity","sonar-pro"):("Web Research","Information Retrieval","Current Information","Source Synthesis"),
 ("perplexity","sonar-deep-research"):("Deep Research","Source Synthesis","Web Research","Report Generation"),
 ("perplexity","sonar-reasoning-pro"):("Research Reasoning","Web Research","Logical Reasoning","Source Synthesis"),
}

def capability_profiles(db):
    evidence=db.scalars(select(ModelCapabilityEvidence)).all();skills={x.id:x.name for x in db.scalars(select(ModelSkill)).all()}
    maxima=defaultdict(float)
    for row in evidence:
        if row.raw_score is not None and row.evaluation_max and row.evaluation_max>0:maxima[(row.skill_id,row.evaluation_name)]=max(maxima[(row.skill_id,row.evaluation_name)],row.raw_score/row.evaluation_max)
    grouped=defaultdict(list)
    for row in evidence:
        own=row.raw_score/row.evaluation_max if row.raw_score is not None and row.evaluation_max and row.evaluation_max>0 else None;frontier=maxima[(row.skill_id,row.evaluation_name)]
        if own is not None and frontier>0:
            age=max(0,(datetime.now(timezone.utc)-(row.evaluation_date if row.evaluation_date.tzinfo else row.evaluation_date.replace(tzinfo=timezone.utc))).days);recency=max(.5,1-age/1095);quality=1.25 if row.independent else .85 if row.provider_reported else 1;grouped[(row.provider,row.model_id,row.skill_id)].append((100*own/frontier,row.benchmark_weight*recency*quality,row))
    result=defaultdict(list)
    for (provider,model,skill_id),rows in grouped.items():
        total=sum(weight for _,weight,_ in rows);score=round(sum(value*weight for value,weight,_ in rows)/total) if total else None;independent=sum(row.independent for _,_,row in rows);state="VERIFIED" if len(rows)>=3 and independent else "BENCHMARK-INFORMED";confidence="HIGH" if state=="VERIFIED" else "MEDIUM" if len(rows)>=2 else "LOW";result[(provider,model)].append({"skill":skills.get(skill_id,"Unknown"),"score":score,"rating_type":state,"confidence":confidence,"evidence_count":len(rows)})
    return result

def profile_for(db,provider,model,profiles=None):
    profiles=profiles if profiles is not None else capability_profiles(db);scored=sorted(profiles.get((provider,model),[]),key=lambda x:x["score"],reverse=True)[:4]
    if scored:return {"capability_status":"scored","rating_type":min((x["rating_type"] for x in scored),key=lambda x:("ESTIMATED","BENCHMARK-INFORMED","VERIFIED").index(x)),"skills":scored,"score_explanation":SCORE_EXPLANATION}
    candidates=CANDIDATES.get((provider,model),())
    return {"capability_status":"needs_review","rating_type":"ESTIMATED","skills":[{"skill":name,"score":None,"rating_type":"ESTIMATED","confidence":"LOW","evidence_count":0} for name in candidates],"score_explanation":SCORE_EXPLANATION}
