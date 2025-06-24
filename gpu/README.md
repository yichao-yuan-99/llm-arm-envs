```
docker run --rm -it --gpus all -v $(pwd):/additional-scripts rajesh550/gh200-vllm:0.9.0.1 bash
```

```
python scripts/benchmark_paged_attention.py --batch_size=5120
```

```
load plaggable allocator from ./custom-allocator/alloc.so
using custom allocator
Total number of blocks across all sequences: 1310720, relative to NUM_BLOCKS: 1.00
Key cache size: 40.00 GB
Value cache size: 40.00 GB
Data accessed by the kernel: 80.00 GB
Warming up...
[RESULT] Kernel time: 39.204 ms, Memory BW: 2040.634 GB/s
Start Benchmark...
[RESULT] Kernel time: 419.768 ms, Memory BW: 190.581 GB/s
Kernel running time: 419768.363 us
```