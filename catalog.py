"""
Curated model catalog keyed by VRAM tier (GB).
All selections are deterministic — no LLM involvement.
Each entry lists models that fit comfortably within the available VRAM.
"""

from models import ModelRecommendation

# fmt: off
_CATALOG: dict[int, list[ModelRecommendation]] = {
    16: [  # NVIDIA T4
        ModelRecommendation(repo_id="meta-llama/Llama-3.2-1B-Instruct",       display_name="Llama 3.2 1B Instruct",    size_params="1B",    vram_required_gb=4),
        ModelRecommendation(repo_id="meta-llama/Llama-3.2-3B-Instruct",       display_name="Llama 3.2 3B Instruct",    size_params="3B",    vram_required_gb=8),
        ModelRecommendation(repo_id="google/gemma-2-2b-it",                   display_name="Gemma 2 2B Instruct",      size_params="2B",    vram_required_gb=6),
        ModelRecommendation(repo_id="microsoft/Phi-3-mini-4k-instruct",       display_name="Phi-3 Mini 4K",            size_params="3.8B",  vram_required_gb=8),
        ModelRecommendation(repo_id="mistralai/Mistral-7B-Instruct-v0.3",     display_name="Mistral 7B Instruct",      size_params="7B",    vram_required_gb=14, notes="fp16 only"),
    ],
    24: [  # NVIDIA A10G
        ModelRecommendation(repo_id="meta-llama/Meta-Llama-3.1-8B-Instruct",  display_name="Llama 3.1 8B Instruct",   size_params="8B",    vram_required_gb=16),
        ModelRecommendation(repo_id="meta-llama/Llama-3.2-11B-Vision-Instruct",display_name="Llama 3.2 11B Vision",   size_params="11B",   vram_required_gb=22),
        ModelRecommendation(repo_id="google/gemma-2-9b-it",                   display_name="Gemma 2 9B Instruct",     size_params="9B",    vram_required_gb=18),
        ModelRecommendation(repo_id="mistralai/Mistral-7B-Instruct-v0.3",     display_name="Mistral 7B Instruct",     size_params="7B",    vram_required_gb=14),
        ModelRecommendation(repo_id="Qwen/Qwen2.5-7B-Instruct",               display_name="Qwen 2.5 7B Instruct",   size_params="7B",    vram_required_gb=14),
    ],
    80: [  # NVIDIA A100 80GB
        ModelRecommendation(repo_id="meta-llama/Meta-Llama-3.1-70B-Instruct", display_name="Llama 3.1 70B Instruct",  size_params="70B",   vram_required_gb=70),
        ModelRecommendation(repo_id="meta-llama/Llama-3.3-70B-Instruct",      display_name="Llama 3.3 70B Instruct",  size_params="70B",   vram_required_gb=70),
        ModelRecommendation(repo_id="Qwen/Qwen2.5-72B-Instruct",              display_name="Qwen 2.5 72B Instruct",   size_params="72B",   vram_required_gb=72, notes="tight; use fp8"),
        ModelRecommendation(repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",   display_name="Mixtral 8×7B MoE",        size_params="~46B",  vram_required_gb=60),
        ModelRecommendation(repo_id="google/gemma-2-27b-it",                  display_name="Gemma 2 27B Instruct",    size_params="27B",   vram_required_gb=54),
    ],
    96: [  # 4× NVIDIA A10G
        ModelRecommendation(repo_id="meta-llama/Meta-Llama-3.1-70B-Instruct", display_name="Llama 3.1 70B Instruct",  size_params="70B",   vram_required_gb=70),
        ModelRecommendation(repo_id="Qwen/Qwen2.5-72B-Instruct",              display_name="Qwen 2.5 72B Instruct",   size_params="72B",   vram_required_gb=72),
        ModelRecommendation(repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",   display_name="Mixtral 8×7B MoE",        size_params="~46B",  vram_required_gb=60),
        ModelRecommendation(repo_id="google/gemma-2-27b-it",                  display_name="Gemma 2 27B Instruct",    size_params="27B",   vram_required_gb=54),
    ],
    320: [  # 4× NVIDIA A100
        ModelRecommendation(repo_id="meta-llama/Meta-Llama-3.1-405B-Instruct-FP8", display_name="Llama 3.1 405B FP8", size_params="405B", vram_required_gb=280),
        ModelRecommendation(repo_id="meta-llama/Llama-3.3-70B-Instruct",      display_name="Llama 3.3 70B Instruct",  size_params="70B",   vram_required_gb=70),
        ModelRecommendation(repo_id="Qwen/Qwen2.5-72B-Instruct",              display_name="Qwen 2.5 72B Instruct",   size_params="72B",   vram_required_gb=72),
    ],
}
# fmt: on

_TIERS = sorted(_CATALOG.keys())


def get_compatible_models(vram_gb: int) -> list[ModelRecommendation]:
    """Return the model list for the smallest catalog tier >= vram_gb."""
    for tier in _TIERS:
        if vram_gb <= tier:
            return _CATALOG[tier]
    return _CATALOG[_TIERS[-1]]
