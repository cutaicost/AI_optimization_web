# Model Capability Evidence Audit

This audit separates catalog/pricing status from capability evidence. A listed model can have maintained pricing while still lacking defensible capability scores.

## Evidence entered

Exact first-party benchmark observations were entered for GPT-4.1, GPT-4o (2024-11-20), GPT-5, GPT-5.1, GPT-5.4, GPT-5.4 mini, GPT-5.6 Sol/Terra, Claude Haiku 4.5, Claude Sonnet 4.6/5, Claude Opus 5, Gemini 2.5 Pro/3.8 Flash, Command A+, and DeepSeek V4 Pro. Snapshot IDs inherit only from explicit aliases and do not duplicate evidence.

The evidence comes from provider publications: [GPT-4.1](https://openai.com/index/gpt-4-1/), [GPT-5](https://openai.com/index/introducing-gpt-5-for-developers/), [GPT-5.1](https://openai.com/index/gpt-5-1-for-developers/), [GPT-5.4](https://openai.com/index/introducing-gpt-5-4/), [GPT-5.4 mini](https://openai.com/index/introducing-gpt-5-4-mini-and-nano/), [GPT-5.6](https://openai.com/index/gpt-5-6/), [Claude Haiku 4.5](https://www.anthropic.com/claude/haiku), [Claude Sonnet 5](https://www.anthropic.com/research/claude-sonnet-5), [Gemini 2.5 Pro](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-model-thinking-updates-march-2025/), [Gemini 3.8 comparative evaluations](https://deepmind.google/models/gemini/), [Command A+](https://cohere.com/blog/command-a-plus), and [DeepSeek V4 updates](https://api-docs.deepseek.com/updates/).

No entered evidence is marked independent because these observations are reported on provider-controlled pages, even when the page compares competing models. Consequently, populated profiles are `BENCHMARK-INFORMED`, not `VERIFIED`.

## Catalog review list

| Provider | Model IDs | Issue | Pricing | Capability evidence | Recommended action |
|---|---|---|---|---|---|
| OpenAI | `gpt-6-astra`, `gpt-5.5`, `gpt-5.6-luna` | Current catalog entries but insufficient comparable numeric evidence entered | Maintained | None/partial | Obtain exact official tables plus an independent evaluation |
| OpenAI | `gpt-5-mini`, `gpt-5-nano`, dated snapshots, `gpt-5.2-chat-latest`, `gpt-5.2-codex`, `gpt-5.4-pro`, `o3`, `o3-mini`, `o4-mini` | Some official results exist, but snapshot/scaffold/effort comparability needs a dedicated review | Maintained | None or alias-only | Record evaluation configuration before scoring; add aliases only where release identity is documented |
| OpenAI | `gpt-4o`, three dated GPT-4o snapshots | Only the latest snapshot has comparable evidence in this seed | Maintained | Latest/alias only | Do not copy latest results to older snapshots without release-specific evidence |
| Anthropic | `claude-opus-5`, `claude-sonnet-5` | Very new; available evidence remains predominantly provider-reported | Maintained | Partial | Add system-card and independent benchmark records |
| Cohere | `command-a-03-2025`, `command-r-08-2024` | Strength claims exist, but no comparable numeric evidence was entered | Maintained | None | Add original technical-report benchmark rows mapped specifically to RAG/tool/multilingual skills |
| DeepSeek | `deepseek-v4-flash` | Official claims exist, but exact comparable rows were not entered | Maintained | None | Add version-specific official evaluation table |
| Google | `gemini-3.5-flash-lite` | Recent model card exists; exact relevant results require extraction | Maintained | None | Add model-card values with configuration metadata |
| Mistral | `codestral`, `mistral-large-3`, `mistral-medium-3-5`, `mistral-small-4` | No sufficiently comparable current evidence entered | Maintained | None | Verify official model IDs and add original benchmark/model-card evidence |
| Perplexity | all Sonar variants | Search/research positioning is clear, but cross-model benchmark methodology is too weak for `/100` | Maintained | None | Keep candidate ordering unscored until comparable research evaluations exist |
| xAI | `grok-4.20-0309-non-reasoning`, `grok-4.6` | Current IDs need provider-release verification and comparable benchmark records | Maintained | None | Verify naming and seed exact first-party plus independent results |

## Weak capability categories

Comparable evidence is currently weakest for Enterprise RAG, multilingual performance, web research/source synthesis, writing, debugging as distinct from general coding, long-context analysis across different context lengths, and document/data analysis. These categories remain unscored unless a benchmark measures the named capability directly.
