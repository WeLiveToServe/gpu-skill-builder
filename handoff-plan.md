# GPU Builder Skill - Handoff Plan

This document provides a comprehensive handoff plan for the GPU Builder Skill project, summarizing all relevant work and research conducted to date.

## Project Overview

The GPU Builder Skill project aims to automate the deployment and management of GPU instances for running large language models (LLMs), with a focus on Qwen models. The project encompasses several cloud providers and various GPU hardware configurations.

## Completed Work

### 1. DigitalOcean GPU Instance Setup

#### CPU Droplet Creation and Testing
- Successfully created a CPU droplet on DigitalOcean for baseline testing
- IP Address: 167.172.151.253
- Installed Ollama and Qwen2.5 model for initial testing
- Configured Ollama to listen on all interfaces (`--host 0.0.0.0`)
- Tested API connectivity from Qwen Code

#### Transition to GPU Instance Plan
- Destroyed the CPU droplet after successful testing
- Planning to create an H200 GPU droplet with optimized configuration
- Script created: `create-h200-droplet.ps1`

### 2. Qwen3.6 Model Optimization

#### H200 Optimization Configuration
- Created detailed optimization file for Qwen3.6 35B-A3B model on H200 GPU
- File: `h200-Qwen3.6-35B-A3B-text-only-droplet-optimization.txt`
- Includes:
  - vLLM configuration flags for optimal performance
  - ACP (Automatic Compression Pooling) settings
  - KV cache optimization parameters
  - Performance monitoring guidance
  - Agent-centric comments for implementation

#### vLLM Optimization Parameters
- Memory management flags: `VLLM_ENABLE_AIC`, `VLLM_KV_CACHE_FREEING`, etc.
- KV cache quantization: `--kv-cache-dtype fp8`
- Performance monitoring commands for GPU utilization tracking
- Health check procedures for ensuring service stability

### 3. Cloud Provider Research and Setup

#### Thunder Compute Investigation
- Researched Thunder Compute as an alternative GPU provider
- Account created with API token: `6c337c4f4a8808b554c853ecf942d5ef457d117ecc24d68035de02071834b951`
- CLI installed: `tnr` (Thunder Compute CLI)
- Authentication configured with API token
- Attempted to create H100 instance but encountered interactive prompts

#### Vast.ai Setup
- Installed Vast.ai CLI tool using `pip install vastai`
- API token added to `.env` file: `42624b9191a1ab226688309513610de97431bfe7ba043fb2e983f07f59fc0268`
- CLI verified with `vastai --help` command

#### OpenRouter Integration
- Researched OpenRouter for Qwen model access
- Identified Qwen 3.6B model availability on OpenRouter
- Pricing comparison between Qwen 3.6 and 2.5 models
- Qwen 3.6 Plus: $0.325 per million input tokens, $1.95 per million output tokens

### 4. Hardware and Model Compatibility Research

#### Qwen Model Hardware Requirements
- Qwen3.6 35B model requires approximately 62-65 GB VRAM (H100/H200 compatible)
- With FP8 quantization: ~31-33 GB VRAM requirement
- System RAM requirements: 64-128 GB recommended
- CPU requirements: 16-32 vCPUs for optimal performance

#### GPU Performance Comparison
- H200 (141GB) vs 2x H100 (2x80GB): H200 generally offers better performance
- Thunder Compute H100 with 16 vCPUs and 128GB RAM is sufficient for Qwen3.6 35B
- Storage recommendation: 150GB primary + 150GB ephemeral for optimal performance

### 5. Cloud Provider Account Status

#### DigitalOcean
- Account with AMD credits available but GPU entitlement issues
- Unable to create MI300X droplets due to account entitlement restrictions
- H200 droplets also unavailable due to regional restrictions

#### Thunder Compute
- Account successfully created and authenticated
- H100 GPU instances available
- CLI installed but requires manual instance creation through web console

#### Vast.ai
- CLI installed and configured
- Ready for GPU instance provisioning
- API token in place for automated operations

## Next Steps for Implementation

### 1. Instance Creation and Model Deployment
1. Create GPU instance on Thunder Compute or Vast.ai
2. Install required dependencies (Python, vLLM, etc.)
3. Deploy Qwen3.6 35B model with optimized configuration
4. Configure API endpoint with vLLM settings from optimization file

### 2. Performance Testing
1. Benchmark Qwen3.6 35B performance on selected GPU instance
2. Monitor GPU utilization and memory usage
3. Test with various context lengths and batch sizes
4. Compare performance against DigitalOcean H200 (when available)

### 3. Integration with GPU Builder Skill
1. Add Thunder Compute and Vast.ai as supported providers
2. Implement instance creation and management functions
3. Add model deployment and optimization scripts
4. Integrate performance monitoring features

## Files and Resources

### Key Files in This Repository
- `h200-Qwen3.6-35B-A3B-text-only-droplet-optimization.txt`: Detailed vLLM optimization flags
- `create-h200-droplet.ps1`: PowerShell script for H200 droplet creation
- `catalog.py`: Hardware catalog with GPU specifications
- `skill.py`: Main skill implementation file

### External Resources
- `.env` file in `C:\Users\keith\dev` with API tokens:
  - Thunder Compute: `TNR_API_TOKEN`
  - Vast.ai: `VAST_AI_API_KEY`
- Qwen Code settings configured for OpenRouter with Qwen 3.5 as default model

## Troubleshooting Notes

### DigitalOcean GPU Issues
- Account has AMD credits but GPU entitlement is not fully enabled
- Contact DigitalOcean support to resolve GPU provisiong issues
- Error Code: 422 "Size is not available in this region"

### Thunder Compute CLI Limitations
- CLI requires interactive input for storage configuration even with parameters
- Workaround: Manual instance creation through web console
- CLI still useful for instance management after creation

## Agent Instructions

The next agent working on this project should:

1. Review the optimization file for vLLM configuration flags
2. Use the API tokens in the `.env` file for cloud provider authentication
3. Consider Thunder Compute or Vast.ai as primary providers due to DigitalOcean issues
4. Implement the performance monitoring commands from the optimization file
5. Follow the hardware recommendations for optimal Qwen3.6 35B performance
6. Reference the existing scripts and configuration files for implementation consistency

This handoff plan encompasses all research, setup, and configuration work completed to date, providing a solid foundation for continued development of the GPU Builder Skill.