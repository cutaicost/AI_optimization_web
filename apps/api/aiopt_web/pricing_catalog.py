"""Reviewable OpenAI official-documentation pricing snapshot and exact aliases."""
from datetime import datetime,timezone
REVIEWED_AT=datetime(2026,9,8,tzinfo=timezone.utc)
def source(model):return f"https://developers.openai.com/api/docs/models/{model}"
# provider, canonical model, input/1M, output/1M, cached input/1M
CATALOG=(
 ("openai","gpt-6-astra","10","50","1"),("openai","gpt-5.6-sol","4","20","0.4"),("openai","gpt-5.6-terra","2","12","0.2"),("openai","gpt-5.6-luna","0.2","1.2","0.02"),
 ("openai","gpt-5.5","5","30","0.5"),("openai","gpt-5.4","2.5","15","0.25"),("openai","gpt-5.4-pro","30","180",None),("openai","gpt-5.4-mini","0.75","4.5","0.075"),
 ("openai","gpt-5.2-codex","1.75","14","0.175"),("openai","gpt-5.2-chat-latest","1.75","14","0.175"),("openai","gpt-5.1","1.25","10","0.125"),("openai","gpt-5.1-chat-latest","1.25","10","0.125"),
 ("openai","gpt-5","1.25","10","0.125"),("openai","gpt-5-mini","0.25","2","0.025"),("openai","gpt-5-nano","0.05","0.4","0.005"),
 ("openai","gpt-4.1","2","8","0.5"),("openai","gpt-4o","2.5","10","1.25"),("openai","o3","2","8","0.5"),("openai","o4-mini","1.1","4.4","0.275"),("openai","o3-mini","1.1","4.4","0.55"),
)
# Only relationships explicitly listed by official model pages.
ALIASES={
 "gpt-5.6":"gpt-5.6-sol","gpt-5.4-2026-03-05":"gpt-5.4","gpt-5.4-mini-2026-03-17":"gpt-5.4-mini",
 "gpt-5-2025-08-07":"gpt-5","gpt-5-mini-2025-08-07":"gpt-5-mini","gpt-5-nano-2025-08-07":"gpt-5-nano",
 "gpt-4o-2024-08-06":"gpt-4o","gpt-4o-2024-11-20":"gpt-4o","gpt-4o-2024-05-13":"gpt-4o","o3-2025-04-16":"o3",
}
CURRENT={"gpt-6-astra","gpt-5.6-sol","gpt-5.6-terra","gpt-5.6-luna","gpt-5.5","gpt-5.4","gpt-5.4-pro","gpt-5.4-mini"}
LEGACY_PREFIXES=("gpt-4","gpt-3","o1","o3","o4","babbage","davinci","text-moderation","computer-use-preview")
def canonical(model):return ALIASES.get(model,model)
def category(model):
    value=model.casefold()
    if "realtime" in value:return "REALTIME"
    if any(x in value for x in ("transcribe","tts","audio","whisper")):return "AUDIO"
    if "image" in value or "dall-e" in value:return "IMAGE"
    if "embedding" in value:return "EMBEDDINGS"
    if "sora" in value or "video" in value:return "VIDEO"
    if canonical(model) in {x[1] for x in CATALOG}:return "TEXT_REASONING"
    return "UNKNOWN"
def lifecycle(model):
    base=canonical(model)
    if base in CURRENT:return "CURRENT"
    if base in {x[1] for x in CATALOG} or model.casefold().startswith(LEGACY_PREFIXES):return "LEGACY"
    return "UNKNOWN"
