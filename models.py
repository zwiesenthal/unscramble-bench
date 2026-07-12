FRONTIER_MODELS = [
    "openai/gpt-5.5",
    "anthropic/claude-opus-4.8",
    "anthropic/claude-opus-4.7",
    "google/gemini-3.5-flash",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.3",
]

CHEAP_MODELS = [
    "moonshotai/kimi-k2.7-code",
    "moonshotai/kimi-k2.6",
    "deepseek/deepseek-v4-flash",
    "tencent/hy3-preview",
    "xiaomi/mimo-v2.5",
    "qwen/qwen3.7-plus",
    "z-ai/glm-4.7-flash",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-medium-3-5",
    "google/gemma-4-31b-it",
    "google/gemma-4-26b-a4b-it",
    "minimax/minimax-m3",
    "stepfun/step-3.7-flash",
    "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano",
]

FREE_MODELS = [
    "nex-agi/nex-n2-pro:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "openrouter/owl-alpha",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
]

MODEL_GROUPS = {
    "frontier": FRONTIER_MODELS,
    "cheap": CHEAP_MODELS,
    "free": FREE_MODELS,
}

ALL_MODELS = list(dict.fromkeys(model for group in MODEL_GROUPS.values() for model in group))


def resolve_models(value):
    if value == "all":
        return ALL_MODELS
    if value in MODEL_GROUPS:
        return MODEL_GROUPS[value]

    models = []
    for name in value.split(","):
        name = name.strip()
        models.extend(MODEL_GROUPS.get(name, [name]) if name else [])
    return list(dict.fromkeys(models))
