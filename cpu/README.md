```
sudo docker buildx build --platform linux/arm64 --memory=300g -t yicyua01/vllm-cpu:0.9.1 .
sudo docker run --rm -it  --privileged --ulimit memlock=-1:-1 yicyua01/vllm-cpu:0.9.1 bash
```

```
VLLM_CPU_OMP_THREADS_BIND="0-63" python scripts/batch.py
VLLM_CPU_OMP_THREADS_BIND="0-63" python scripts/benchmark_paged_attention.py --batch_size=5120
```