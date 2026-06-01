FRONTIER_MODELS = [
    "openai/gpt-5.5",  # $30.00 / 1M output tokens
    "openai/gpt-5.4",  # $15.00 / 1M output tokens
    "anthropic/claude-opus-4.8",  # $25.00 / 1M output tokens
    "anthropic/claude-opus-4.7",  # $25.00 / 1M output tokens
    "qwen/qwen3.7-max",  # $3.75 / 1M output tokens
    "google/gemini-3.5-flash",  # $9.00 / 1M output tokens
    "google/gemini-3.1-pro-preview",  # $12.00 / 1M output tokens
    "x-ai/grok-4.3",  # $2.50 / 1M output tokens
    "moonshotai/kimi-k2.6",  # $3.42 / 1M output tokens
]

CHEAP_MODELS = [
    "openai/gpt-5.4-mini",  # $4.50 / 1M output tokens
    "google/gemma-4-31b-it",  # $0.37 / 1M output tokens
    "google/gemma-4-26b-a4b-it",  # $0.33 / 1M output tokens
    "deepseek/deepseek-v4-flash",  # $0.20 / 1M output tokens
    "deepseek/deepseek-v3.2-exp",  # $0.41 / 1M output tokens
    "google/gemini-2.5-flash-lite-preview-09-2025",  # $0.40 / 1M output tokens
    "openai/gpt-5-nano",  # $0.40 / 1M output tokens
    "openai/gpt-4.1-nano",  # $0.40 / 1M output tokens
    "qwen/qwen3.5-flash-02-23",  # $0.26 / 1M output tokens
    "mistralai/mistral-small-3.2-24b-instruct",  # $0.20 / 1M output tokens
]

FREE_MODELS = [
    "openrouter/free",  # free
    "google/gemma-4-26b-a4b-it:free",  # free
    "google/gemma-4-31b-it:free",  # free
    "google/lyria-3-clip-preview",  # free
    "google/lyria-3-pro-preview",  # free
    "liquid/lfm-2.5-1.2b-instruct:free",  # free
    "liquid/lfm-2.5-1.2b-thinking:free",  # free
    "meta-llama/llama-3.2-3b-instruct:free",  # free
    "meta-llama/llama-3.3-70b-instruct:free",  # free
    "moonshotai/kimi-k2.6:free",  # free
    "nvidia/nemotron-3-nano-30b-a3b:free",  # free
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # free
    "nvidia/nemotron-3-super-120b-a12b:free",  # free
    "nvidia/nemotron-nano-12b-v2-vl:free",  # free
    "nvidia/nemotron-nano-9b-v2:free",  # free
    "nousresearch/hermes-3-llama-3.1-405b:free",  # free
    "openai/gpt-oss-120b:free",  # free
    "openai/gpt-oss-20b:free",  # free
    "openrouter/owl-alpha",  # free
    "poolside/laguna-m.1:free",  # free
    "poolside/laguna-xs.2:free",  # free
    "qwen/qwen3-coder:free",  # free
    "qwen/qwen3-next-80b-a3b-instruct:free",  # free
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # free
    "z-ai/glm-4.5-air:free",  # free
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
