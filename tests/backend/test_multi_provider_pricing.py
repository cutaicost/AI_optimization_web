from decimal import Decimal
import pytest
from apps.api.aiopt_web.multi_provider_catalog import BY_KEY,CATALOG_ENTRIES,Workload,calculate_entry,comparable_models

def cost(provider,model,**workload):return calculate_entry(BY_KEY[(provider,model)],Workload(**workload))

def test_required_providers_and_normalized_units_load():
    assert {x.provider for x in CATALOG_ENTRIES}>={"openai","anthropic","google","xai","mistral","deepseek","cohere","perplexity"}
    assert all(x.source.startswith("https://") and x.quality_tier in {1,2,3,4} for x in CATALOG_ENTRIES)

@pytest.mark.parametrize(("provider","model","expected"),[("openai","gpt-5.6-sol",Decimal("24")),("google","gemini-3.8-flash",Decimal("4.5")),("xai","grok-4.6",Decimal("8")),("mistral","mistral-medium-3-5",Decimal("9")),("deepseek","deepseek-v4-pro",Decimal("1.305")),("cohere","command-a-03-2025",Decimal("12.5"))])
def test_provider_standard_one_million_each(provider,model,expected):assert cost(provider,model,input_tokens=1_000_000,output_tokens=1_000_000)["total"]==expected

def test_anthropic_cache_write_read_and_batch_are_distinct():
    regular=cost("anthropic","claude-sonnet-5",input_tokens=1_000_000,output_tokens=100_000,cached_input_tokens=400_000,cache_write_tokens=100_000)
    assert regular["components"]["cached_input"]==Decimal("0.08");assert regular["components"]["cache_write"]==Decimal("0.25")
    assert cost("anthropic","claude-sonnet-5",input_tokens=1_000_000,output_tokens=1_000_000,batch=True)["total"]==Decimal("6")

def test_gemini_batch_and_cache_price_are_applied():
    assert cost("google","gemini-3.8-flash",input_tokens=1_000_000,output_tokens=1_000_000,cached_input_tokens=500_000,batch=True)["total"]==Decimal("2.08125")

def test_gemini_context_threshold_selects_the_correct_complete_tier():
    assert cost("google","gemini-2.5-pro",input_tokens=1_000_000,output_tokens=1_000_000,context_length=200_000)["total"]==Decimal("11.25")
    assert cost("google","gemini-2.5-pro",input_tokens=1_000_000,output_tokens=1_000_000,context_length=200_001)["total"]==Decimal("17.5")
    assert cost("google","gemini-2.5-pro",input_tokens=1_000_000,output_tokens=1_000_000,context_length=200_001,batch=True)["total"]==Decimal("8.75")

def test_deepseek_cache_hit_is_not_collapsed_into_cache_miss():
    result=cost("deepseek","deepseek-v4-flash",input_tokens=1_000_000,output_tokens=0,cached_input_tokens=900_000)
    assert result["components"]["input"]==Decimal("0.014");assert result["components"]["cached_input"]==Decimal("0.00252")

def test_perplexity_request_search_reasoning_and_citation_fees():
    assert cost("perplexity","sonar",input_tokens=500,output_tokens=200,requests=1,search_context="high")["total"]==Decimal("0.0127")
    assert cost("perplexity","sonar-deep-research",input_tokens=0,output_tokens=0,searches=18,citation_tokens=20_000,reasoning_tokens=74_000)["total"]==Decimal("0.352")

def test_unknown_rules_and_unpriced_models_never_guess():
    assert cost("xai","grok-4.20-0309-non-reasoning",input_tokens=1,output_tokens=1,context_length=200_001) is None
    assert cost("cohere","command-a-plus-05-2026",input_tokens=1,output_tokens=1) is None
    assert ("unknown","model") not in BY_KEY

def test_comparisons_preserve_capability_tier_and_context():
    candidates=comparable_models("anthropic","claude-sonnet-5",capabilities={"CODING","TOOL_CALLING"},context_length=200_000)
    assert candidates and all(x.provider!="anthropic" and "CODING" in x.capabilities and abs(x.quality_tier-2)<=1 for x in candidates)

def test_invalid_workload_is_rejected():
    with pytest.raises(ValueError):cost("openai","gpt-5.6-sol",input_tokens=10,output_tokens=0,cached_input_tokens=11)
