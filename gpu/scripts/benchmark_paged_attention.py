# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project

import random
import time
from typing import Optional

import torch

from vllm import _custom_ops as ops
from vllm.logger import init_logger
from vllm.platforms import current_platform
from vllm.utils import (
    STR_DTYPE_TO_TORCH_DTYPE,
    FlexibleArgumentParser,
    create_kv_caches_with_random,
)

##### [use pinned memory]
from torch.cuda.memory import CUDAPluggableAllocator
from torch.cuda import MemPool, use_mem_pool
########################

logger = init_logger(__name__)

NUM_BLOCKS = 1280 * 1024
PARTITION_SIZE = 512
PARTITION_SIZE_ROCM = 256


@torch.inference_mode()
def main(
    version: str,
    num_seqs: int,
    seq_len: int,
    num_query_heads: int,
    num_kv_heads: int,
    head_size: int,
    use_alibi: bool,
    block_size: int,
    dtype: torch.dtype,
    seed: int,
    do_profile: bool,
    device: str = "cuda",
    kv_cache_dtype: Optional[str] = None,
) -> None:
    current_platform.seed_everything(seed)

    scale = float(1.0 / (head_size**0.5))
    query = torch.empty(
        num_seqs, num_query_heads, head_size, dtype=dtype, device=device
    )
    query.uniform_(-scale, scale)

    assert num_query_heads % num_kv_heads == 0
    alibi_slopes = None
    if use_alibi:
        alibi_slopes = torch.randn(num_query_heads, dtype=torch.float, device=device)

    seq_lens = [seq_len for _ in range(num_seqs)]
    max_seq_len = max(seq_lens)
    seq_lens = torch.tensor(seq_lens, dtype=torch.int, device=device)

    # number of blocks for all sequences
    seq_num_blocks = (seq_lens + block_size - 1) // block_size
    # sum of all blocks across sequences
    total_num_blocks = seq_num_blocks.sum().item()
    print( f"Total number of blocks across all sequences: {total_num_blocks}, relative to NUM_BLOCKS: {total_num_blocks / NUM_BLOCKS:.2f}")


    # Create the block tables.
    max_num_blocks_per_seq = (max_seq_len + block_size - 1) // block_size
    block_tables_lst: list[list[int]] = []
    for _ in range(num_seqs):
        block_table = [
            random.randint(0, NUM_BLOCKS - 1) for _ in range(max_num_blocks_per_seq)
        ]
        block_tables_lst.append(block_table)

    block_tables = torch.tensor(block_tables_lst, dtype=torch.int, device=device)

    

    # Create the KV cache.
    key_caches, value_caches = create_kv_caches_with_random(
        NUM_BLOCKS,
        block_size,
        1,
        num_kv_heads,
        head_size,
        kv_cache_dtype,
        dtype,
        device=device,
    )
    key_cache, value_cache = key_caches[0], value_caches[0]

    # print the size of the key and value caches
    print( f"Key cache size: {key_cache.numel() * key_cache.element_size() / (1024 ** 3):.2f} GB")
    print( f"Value cache size: {value_cache.numel() * value_cache.element_size() / (1024 ** 3):.2f} GB")

    # amount of data accessed by the kernel
    data_accessed = (total_num_blocks/ NUM_BLOCKS) * (
        key_cache.numel() * key_cache.element_size()
        + value_cache.numel() * value_cache.element_size()
    ) / (1024 ** 3)
    print(f"Data accessed by the kernel: {data_accessed:.2f} GB")

    # Prepare for the paged attention kernel.
    output = torch.empty_like(query)
    if version == "v2":
        if current_platform.is_rocm():
            global PARTITION_SIZE
            if not args.custom_paged_attn and not current_platform.is_navi():
                PARTITION_SIZE = 1024
            else:
                PARTITION_SIZE = PARTITION_SIZE_ROCM
        num_partitions = (max_seq_len + PARTITION_SIZE - 1) // PARTITION_SIZE
        tmp_output = torch.empty(
            size=(num_seqs, num_query_heads, num_partitions, head_size),
            dtype=output.dtype,
            device=output.device,
        )
        exp_sums = torch.empty(
            size=(num_seqs, num_query_heads, num_partitions),
            dtype=torch.float32,
            device=output.device,
        )
        max_logits = torch.empty_like(exp_sums)

    def run_cuda_benchmark(num_iters: int, profile: bool = False) -> float:
        if profile:
            torch.cuda.cudart().cudaProfilerStart()
        start_time = time.perf_counter()

        # Using default kv_scale
        k_scale = v_scale = torch.tensor(1.0, dtype=torch.float32, device=device)

        for _ in range(num_iters):
            if version == "v1":
                ops.paged_attention_v1(
                    output,
                    query,
                    key_cache,
                    value_cache,
                    num_kv_heads,
                    scale,
                    block_tables,
                    seq_lens,
                    block_size,
                    max_seq_len,
                    alibi_slopes,
                    kv_cache_dtype,
                    k_scale,
                    v_scale,
                )
            elif version == "v2":
                if not args.custom_paged_attn:
                    ops.paged_attention_v2(
                        output,
                        exp_sums,
                        max_logits,
                        tmp_output,
                        query,
                        key_cache,
                        value_cache,
                        num_kv_heads,
                        scale,
                        block_tables,
                        seq_lens,
                        block_size,
                        max_seq_len,
                        alibi_slopes,
                        kv_cache_dtype,
                        k_scale,
                        v_scale,
                    )
                else:
                    ops.paged_attention_rocm(
                        output,
                        exp_sums,
                        max_logits,
                        tmp_output,
                        query,
                        key_cache,
                        value_cache,
                        num_kv_heads,
                        scale,
                        block_tables,
                        seq_lens,
                        None,
                        block_size,
                        max_seq_len,
                        alibi_slopes,
                        kv_cache_dtype,
                        k_scale,
                        v_scale,
                    )
            else:
                raise ValueError(f"Invalid version: {version}")

        end_time = time.perf_counter()
        if profile:
            torch.cuda.cudart().cudaProfilerStop()
        
        kernel_time = (end_time - start_time) / num_iters
        mem_bw = data_accessed / kernel_time # GB/s
        print(f"[RESULT] Kernel time: {kernel_time * 1000:.3f} ms, Memory BW: {mem_bw:.3f} GB/s")
        return (end_time - start_time) / num_iters

    # Warmup.
    print("Warming up...")
    run_benchmark = run_cuda_benchmark
    run_benchmark(num_iters=3, profile=False)

    print("Start Benchmark...")
    # Benchmark.
    if do_profile:
        latency = run_benchmark(num_iters=1, profile=True)
    else:
        latency = run_benchmark(num_iters=10, profile=False)
    print(f"Kernel running time: {latency * 1000000:.3f} us")


if __name__ == "__main__":
    logger.warning(
        "This script benchmarks the paged attention kernel. "
        "By default this is no longer used in vLLM inference."
    )

    parser = FlexibleArgumentParser(description="Benchmark the paged attention kernel.")
    parser.add_argument("--version", type=str, choices=["v1", "v2"], default="v2")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seq-len", type=int, default=4096)
    parser.add_argument("--num-query-heads", type=int, default=64)
    parser.add_argument("--num-kv-heads", type=int, default=8)
    parser.add_argument(
        "--head-size",
        type=int,
        choices=[64, 80, 96, 112, 120, 128, 192, 256],
        default=128,
    )
    parser.add_argument("--block-size", type=int, choices=[16, 32], default=16)
    parser.add_argument("--use-alibi", action="store_true")
    parser.add_argument(
        "--dtype", type=str, choices=["half", "bfloat16", "float"], default="half"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--kv-cache-dtype",
        type=str,
        choices=["auto", "fp8", "fp8_e5m2", "fp8_e4m3"],
        default="auto",
        help="Data type for kv cache storage. If 'auto', will use model "
        "data type. CUDA 11.8+ supports fp8 (=fp8_e4m3) and fp8_e5m2. "
        "ROCm (AMD GPU) supports fp8 (=fp8_e4m3)",
    )
    parser.add_argument(
        "--custom-paged-attn", action="store_true", help="Use custom paged attention"
    )
    args = parser.parse_args()
    print(args)

    if args.num_query_heads % args.num_kv_heads != 0:
        raise ValueError("num_query_heads must be divisible by num_kv_heads")

    ##### [use pinned memory]
    print("load plaggable allocator from ./custom-allocator/alloc.so")
    alloc = CUDAPluggableAllocator("./custom-allocator/alloc.so", alloc_fn_name='my_alloc', free_fn_name='my_free')
    print("using custom allocator")
    pool = MemPool(allocator=alloc.allocator())
    ctx = use_mem_pool(pool)

    with ctx:
    ########################

        main(
            version=args.version,
            num_seqs=args.batch_size,
            seq_len=args.seq_len,
            num_query_heads=args.num_query_heads,
            num_kv_heads=args.num_kv_heads,
            head_size=args.head_size,
            block_size=args.block_size,
            use_alibi=args.use_alibi,
            dtype=STR_DTYPE_TO_TORCH_DTYPE[args.dtype],
            seed=args.seed,
            do_profile=args.profile,
            kv_cache_dtype=args.kv_cache_dtype,
        )