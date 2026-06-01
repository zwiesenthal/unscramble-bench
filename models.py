FRONTIER_MODELS = [
    "openai/gpt-5.5",
    "openai/gpt-5.4",
    "anthropic/claude-opus-4.8",
    "anthropic/claude-opus-4.7",
    "qwen/qwen3.7-max",
    "google/gemini-3.5-flash",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.3",
    "moonshotai/kimi-k2.6",
]

CHEAP_MODELS = [
    "openai/gpt-5.4-mini",
    "google/gemma-4-31b-it",
    "google/gemma-4-26b-a4b-it",
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v3.2-exp",
    "google/gemini-2.5-flash-lite-preview-09-2025",
    "openai/gpt-5-nano",
    "openai/gpt-4.1-nano",
    "qwen/qwen3.5-flash-02-23",
    "mistralai/mistral-small-3.2-24b-instruct",
]

FREE_MODELS = [
    "openrouter/free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "google/lyria-3-clip-preview",
    "google/lyria-3-pro-preview",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "moonshotai/kimi-k2.6:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "openrouter/owl-alpha",
    "poolside/laguna-m.1:free",
    "poolside/laguna-xs.2:free",
    "qwen/qwen3-coder:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "z-ai/glm-4.5-air:free",
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
