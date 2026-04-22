from profile_registry import load_profile_registry
from remote_vllm import render_vllm_command_args, render_vllm_service_unit


def test_single_gpu_profile_renders_expected_vllm_flags():
    registry = load_profile_registry()
    model = registry.model_profiles["openai-gpt-oss-120b"]
    deployment = registry.deployment_profiles["digitalocean-gpt-oss-120b-h200x1"]

    args = render_vllm_command_args(model_profile=model, deployment_profile=deployment)
    service = render_vllm_service_unit(model_profile=model, deployment_profile=deployment)

    assert "--served-model-name" in args
    assert args[args.index("--served-model-name") + 1] == "gpt-oss-120b"
    assert args[args.index("--gpu-memory-utilization") + 1] == "0.80"
    assert "--enable-prefix-caching" in args
    assert "--enable-chunked-prefill" in args
    assert "--enable-expert-parallel" not in args
    assert "gpt-oss-120b" in service


def test_multi_gpu_moe_profile_renders_parallel_and_expert_flags():
    registry = load_profile_registry()
    model = registry.model_profiles["deepseek-v3-1"]
    deployment = registry.deployment_profiles["digitalocean-deepseek-v3-1-h200x8"]

    args = render_vllm_command_args(model_profile=model, deployment_profile=deployment)

    assert args[args.index("--tensor-parallel-size") + 1] == "8"
    assert args[args.index("--pipeline-parallel-size") + 1] == "1"
    assert "--enable-expert-parallel" in args
    assert "--enable-eplb" in args
    assert "--enable-prefix-caching" not in args
    assert "--enable-chunked-prefill" in args
