"""Manually verified, versioned first-party catalog and normalized pricing rules.

All token prices are USD per one million tokens. Non-token charges retain their
native unit in ``rules``. Entries are deliberately explicit: an open-weight
model hosted by another company must use that hosting company as ``provider``.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

MILLION = Decimal("1000000")
VERIFIED_AT = datetime(2026, 9, 8, tzinfo=timezone.utc)


@dataclass(frozen=True)
class CatalogEntry:
    provider: str
    model: str
    display_name: str
    family: str
    input_price: str | None
    output_price: str | None
    cached_input_price: str | None = None
    capabilities: tuple[str, ...] = ("GENERAL_PURPOSE",)
    quality_tier: int = 3
    context_window: int | None = None
    max_output_tokens: int | None = None
    source: str = ""
    model_creator: str | None = None
    hosting_provider: str | None = None
    deprecated: bool = False
    preview: bool = False
    rules: dict = field(default_factory=dict)

    @property
    def pricing_available(self):
        return self.input_price is not None and self.output_price is not None

    def public(self):
        value = asdict(self)
        value.update({
            "input": float(self.input_price) if self.input_price is not None else None,
            "output": float(self.output_price) if self.output_price is not None else None,
            "cached_input": float(self.cached_input_price) if self.cached_input_price is not None else None,
            "verified_at": VERIFIED_AT,
            "pricing_unit": "USD_PER_MILLION_TOKENS",
            "pricing_available": self.pricing_available,
        })
        for key in ("input_price", "output_price", "cached_input_price"):
            value.pop(key)
        value["capabilities"] = list(self.capabilities)
        return value


ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
GEMINI = "https://ai.google.dev/gemini-api/docs/pricing"
XAI = "https://docs.x.ai/developers/models"
MISTRAL = "https://docs.mistral.ai/inference/pricing"
DEEPSEEK = "https://api-docs.deepseek.com/quick_start/pricing"
COHERE = "https://cohere.com/pricing"
PERPLEXITY = "https://docs.perplexity.ai/docs/getting-started/pricing"

# Capability labels are suitability filters, not benchmark or quality claims.
CATALOG_ENTRIES = (
    CatalogEntry("openai", "gpt-6-astra", "GPT-6 Astra", "GPT", "10", "50", "1", ("FRONTIER", "ADVANCED_REASONING", "CODING", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 1, source="https://developers.openai.com/api/docs/models/gpt-6-astra", model_creator="OpenAI"),
    CatalogEntry("openai", "gpt-5.6-sol", "GPT-5.6 Sol", "GPT", "4", "20", "0.4", ("FRONTIER", "ADVANCED_REASONING", "CODING", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 1, source="https://developers.openai.com/api/docs/models/gpt-5.6-sol", model_creator="OpenAI"),
    CatalogEntry("openai", "gpt-5.6-terra", "GPT-5.6 Terra", "GPT", "2", "12", "0.2", ("ADVANCED_REASONING", "GENERAL_PURPOSE", "CODING", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, source="https://developers.openai.com/api/docs/models/gpt-5.6-terra", model_creator="OpenAI"),
    CatalogEntry("openai", "gpt-5.6-luna", "GPT-5.6 Luna", "GPT", "0.2", "1.2", "0.02", ("FAST_ECONOMY", "GENERAL_PURPOSE", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 4, source="https://developers.openai.com/api/docs/models/gpt-5.6-luna", model_creator="OpenAI"),
    CatalogEntry("anthropic", "claude-opus-5", "Claude Opus 5", "Claude Opus", "5", "25", "0.5", ("FRONTIER", "ADVANCED_REASONING", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 1, 1_000_000, source=ANTHROPIC, model_creator="Anthropic", rules={"cache_write_5m": "6.25", "cache_write_1h": "10", "batch_multiplier": "0.5", "us_inference_multiplier": "1.1"}),
    CatalogEntry("anthropic", "claude-sonnet-5", "Claude Sonnet 5", "Claude Sonnet", "2", "10", "0.2", ("ADVANCED_REASONING", "GENERAL_PURPOSE", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 1_000_000, source=ANTHROPIC, model_creator="Anthropic", rules={"cache_write_5m": "2.5", "cache_write_1h": "4", "batch_multiplier": "0.5", "us_inference_multiplier": "1.1"}),
    CatalogEntry("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", "Claude Sonnet", "3", "15", "0.3", ("ADVANCED_REASONING", "GENERAL_PURPOSE", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 1_000_000, source=ANTHROPIC, model_creator="Anthropic", rules={"cache_write_5m": "3.75", "cache_write_1h": "6", "batch_multiplier": "0.5", "us_inference_multiplier": "1.1"}),
    CatalogEntry("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", "Claude Haiku", "1", "5", "0.1", ("FAST_ECONOMY", "GENERAL_PURPOSE", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 4, source=ANTHROPIC, model_creator="Anthropic", rules={"cache_write_5m": "1.25", "cache_write_1h": "2", "batch_multiplier": "0.5"}),
    CatalogEntry("google", "gemini-3.8-flash", "Gemini 3.8 Flash", "Gemini Flash", "0.75", "3.75", "0.075", ("ADVANCED_REASONING", "GENERAL_PURPOSE", "CODING", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, source=GEMINI, model_creator="Google", rules={"batch_input": "0.375", "batch_output": "1.875", "batch_cached_input": "0.0375", "cache_storage_per_1m_token_hour": "0.5", "search_per_1000_after_free_tier": "14", "introductory_price_ends": "2026-12-31"}),
    CatalogEntry("google", "gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", "Gemini Flash-Lite", "0.30", "2.50", "0.03", ("FAST_ECONOMY", "GENERAL_PURPOSE", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 4, source=GEMINI, model_creator="Google", rules={"batch_input": "0.15", "batch_output": "1.25", "batch_cached_input": "0.02", "cache_storage_per_1m_token_hour": "1", "search_per_1000_after_free_tier": "14"}),
    CatalogEntry("google", "gemini-2.5-pro", "Gemini 2.5 Pro", "Gemini Pro", "1.25", "10", "0.125", ("ADVANCED_REASONING", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 1_000_000, source=GEMINI, model_creator="Google", rules={"long_context_threshold": 200_000, "long_context_pricing": {"input": "2.50", "output": "15", "cached_input": "0.25"}, "batch_input": "0.625", "batch_output": "5", "batch_cached_input": "0.125", "batch_long_context_pricing": {"input": "1.25", "output": "7.50", "cached_input": "0.25"}, "cache_storage_per_1m_token_hour": "4.5", "search_per_1000_after_free_tier": "35"}),
    CatalogEntry("xai", "grok-4.6", "Grok 4.6", "Grok", "2", "6", None, ("FRONTIER", "ADVANCED_REASONING", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 1, 500_000, source=XAI, model_creator="xAI"),
    CatalogEntry("xai", "grok-4.20-0309-non-reasoning", "Grok 4.20 Non-Reasoning", "Grok", "1.25", "2.50", "0.20", ("GENERAL_PURPOSE", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 1_000_000, source="https://docs.x.ai/developers/models/grok-4.20-0309-non-reasoning", model_creator="xAI", rules={"long_context_threshold": 200_000, "long_context_pricing": "PROVIDER_DOCUMENTED_NOT_CAPTURED"}),
    CatalogEntry("mistral", "mistral-medium-3-5", "Mistral Medium 3.5", "Mistral Medium", "1.5", "7.5", "0.15", ("FRONTIER", "GENERAL_PURPOSE", "CODING", "MULTIMODAL", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 256_000, source=MISTRAL, model_creator="Mistral AI"),
    CatalogEntry("mistral", "mistral-large-3", "Mistral Large 3", "Mistral Large", "0.5", "1.5", "0.05", ("GENERAL_PURPOSE", "MULTIMODAL", "OPEN_MODEL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 3, source=MISTRAL, model_creator="Mistral AI"),
    CatalogEntry("mistral", "mistral-small-4", "Mistral Small 4", "Mistral Small", "0.15", "0.6", "0.015", ("ADVANCED_REASONING", "GENERAL_PURPOSE", "FAST_ECONOMY", "CODING", "OPEN_MODEL", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 3, source=MISTRAL, model_creator="Mistral AI"),
    CatalogEntry("mistral", "codestral", "Codestral", "Codestral", "0.3", "0.9", "0.03", ("CODING", "FAST_ECONOMY"), 3, source=MISTRAL, model_creator="Mistral AI"),
    CatalogEntry("deepseek", "deepseek-v4-pro", "DeepSeek V4 Pro", "DeepSeek V4", "0.435", "0.87", "0.003625", ("FRONTIER", "ADVANCED_REASONING", "CODING", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT", "OPEN_MODEL"), 2, 1_000_000, 384_000, DEEPSEEK, "DeepSeek"),
    CatalogEntry("deepseek", "deepseek-v4-flash", "DeepSeek V4 Flash", "DeepSeek V4", "0.14", "0.28", "0.0028", ("ADVANCED_REASONING", "FAST_ECONOMY", "CODING", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT", "OPEN_MODEL"), 3, 1_000_000, 384_000, DEEPSEEK, "DeepSeek"),
    CatalogEntry("cohere", "command-a-03-2025", "Command A", "Command A", "2.5", "10", None, ("ADVANCED_REASONING", "GENERAL_PURPOSE", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 2, 256_000, 8_000, "https://docs.cohere.com/docs/command-a", "Cohere"),
    CatalogEntry("cohere", "command-r-08-2024", "Command R", "Command R", "0.15", "0.6", None, ("GENERAL_PURPOSE", "FAST_ECONOMY", "LONG_CONTEXT", "TOOL_CALLING", "STRUCTURED_OUTPUT"), 4, 128_000, 4_000, "https://docs.cohere.com/docs/command-r", "Cohere"),
    CatalogEntry("cohere", "command-a-plus-05-2026", "Command A+", "Command A", None, None, None, ("FRONTIER", "ADVANCED_REASONING", "MULTIMODAL", "TOOL_CALLING", "STRUCTURED_OUTPUT", "OPEN_MODEL"), 1, 128_000, 64_000, "https://docs.cohere.com/docs/command-a-plus", "Cohere", rules={"pricing_note": "No public production pay-as-you-go token price; contact Cohere for Model Vault terms."}),
    CatalogEntry("perplexity", "sonar", "Sonar", "Sonar", "1", "1", None, ("GENERAL_PURPOSE", "SEARCH_GROUNDED"), 3, source=PERPLEXITY, model_creator="Perplexity", rules={"request_fee_per_1000": {"low": "5", "medium": "8", "high": "12"}}),
    CatalogEntry("perplexity", "sonar-pro", "Sonar Pro", "Sonar", "3", "15", None, ("ADVANCED_REASONING", "SEARCH_GROUNDED"), 2, source=PERPLEXITY, model_creator="Perplexity", rules={"request_fee_per_1000": {"low": "6", "medium": "10", "high": "14"}}),
    CatalogEntry("perplexity", "sonar-reasoning-pro", "Sonar Reasoning Pro", "Sonar", "2", "8", None, ("ADVANCED_REASONING", "SEARCH_GROUNDED"), 2, source=PERPLEXITY, model_creator="Perplexity", rules={"request_fee_per_1000": {"low": "6", "medium": "10", "high": "14"}}),
    CatalogEntry("perplexity", "sonar-deep-research", "Sonar Deep Research", "Sonar", "2", "8", None, ("ADVANCED_REASONING", "SEARCH_GROUNDED", "LONG_CONTEXT"), 2, source=PERPLEXITY, model_creator="Perplexity", rules={"citation_tokens": "2", "reasoning_tokens": "3", "search_queries_per_1000": "5"}),
)

BY_KEY = {(entry.provider, entry.model): entry for entry in CATALOG_ENTRIES}


@dataclass(frozen=True)
class Workload:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    requests: int = 0
    searches: int = 0
    citation_tokens: int = 0
    reasoning_tokens: int = 0
    context_length: int | None = None
    batch: bool = False
    search_context: str = "low"
    region: str | None = None


def calculate_entry(entry: CatalogEntry, workload: Workload):
    """Apply normalized catalog rules and return a transparent cost breakdown."""
    if not entry.pricing_available:
        return None
    if min(workload.input_tokens, workload.output_tokens, workload.cached_input_tokens, workload.cache_write_tokens, workload.requests, workload.searches, workload.citation_tokens, workload.reasoning_tokens) < 0:
        raise ValueError("Workload values cannot be negative")
    if workload.cached_input_tokens + workload.cache_write_tokens > workload.input_tokens:
        raise ValueError("Cached and cache-write tokens cannot exceed input tokens")
    if workload.context_length and entry.context_window and workload.context_length > entry.context_window:
        return None
    rules = entry.rules
    if workload.context_length and rules.get("long_context_threshold") and workload.context_length > rules["long_context_threshold"] and not isinstance(rules.get("long_context_pricing"), dict):
        return None
    batch_multiplier = Decimal(rules.get("batch_multiplier", "1")) if workload.batch else Decimal("1")
    input_rate = Decimal(rules.get("batch_input", entry.input_price)) * (batch_multiplier if "batch_input" not in rules else 1) if workload.batch else Decimal(entry.input_price)
    output_rate = Decimal(rules.get("batch_output", entry.output_price)) * (batch_multiplier if "batch_output" not in rules else 1) if workload.batch else Decimal(entry.output_price)
    cached_rate_value = rules.get("batch_cached_input", entry.cached_input_price) if workload.batch else entry.cached_input_price
    if workload.context_length and rules.get("long_context_threshold") and workload.context_length > rules["long_context_threshold"]:
        tier=rules.get("batch_long_context_pricing" if workload.batch else "long_context_pricing",{})
        input_rate=Decimal(tier.get("input",input_rate));output_rate=Decimal(tier.get("output",output_rate));cached_rate_value=tier.get("cached_input",cached_rate_value)
    if workload.cached_input_tokens and cached_rate_value is None:
        return None
    write_rate = rules.get("cache_write_5m")
    if workload.cache_write_tokens and write_rate is None:
        return None
    ordinary = workload.input_tokens - workload.cached_input_tokens - workload.cache_write_tokens
    components = {
        "input": Decimal(ordinary) * input_rate / MILLION,
        "cached_input": Decimal(workload.cached_input_tokens) * Decimal(cached_rate_value or 0) * (batch_multiplier if workload.batch and "batch_cached_input" not in rules else 1) / MILLION,
        "cache_write": Decimal(workload.cache_write_tokens) * Decimal(write_rate or 0) * batch_multiplier / MILLION,
        "output": Decimal(workload.output_tokens) * output_rate / MILLION,
        "request_fees": Decimal("0"), "search_fees": Decimal("0"),
        "citation_tokens": Decimal("0"), "reasoning_tokens": Decimal("0"),
    }
    request_fees = rules.get("request_fee_per_1000")
    if request_fees:
        components["request_fees"] = Decimal(workload.requests) * Decimal(request_fees.get(workload.search_context, request_fees["low"])) / Decimal("1000")
    components["search_fees"] = Decimal(workload.searches) * Decimal(rules.get("search_queries_per_1000", 0)) / Decimal("1000")
    components["citation_tokens"] = Decimal(workload.citation_tokens) * Decimal(rules.get("citation_tokens", 0)) / MILLION
    components["reasoning_tokens"] = Decimal(workload.reasoning_tokens) * Decimal(rules.get("reasoning_tokens", 0)) / MILLION
    multiplier = Decimal("1.1") if workload.region == "us" and rules.get("us_inference_multiplier") else Decimal("1")
    components = {key: value * multiplier for key, value in components.items()}
    return {"components": components, "total": sum(components.values(), Decimal("0")), "pricing_mode": "CURRENT_REPRICING_SIMULATION"}


def comparable_models(provider: str, model: str, *, capabilities=(), context_length=None, include_deprecated=False):
    current = BY_KEY.get((provider.casefold(), model))
    if not current:
        return []
    required = set(capabilities)
    candidates = []
    for entry in CATALOG_ENTRIES:
        if entry.provider == current.provider or not entry.pricing_available or (entry.deprecated and not include_deprecated):
            continue
        if abs(entry.quality_tier - current.quality_tier) > 1 or not required.issubset(entry.capabilities):
            continue
        if context_length and (not entry.context_window or entry.context_window < context_length):
            continue
        candidates.append(entry)
    return sorted(candidates, key=lambda entry: (abs(entry.quality_tier-current.quality_tier), Decimal(entry.input_price), entry.provider))
