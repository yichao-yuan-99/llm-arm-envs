// alloc.cu
#include <cuda_runtime_api.h>
#include <cstddef>

extern "C" {
  // Allocate “size” bytes of host memory, mapped into the device’s address space
  void* my_alloc(ssize_t size, int device, cudaStream_t stream) {
    void* ptr = nullptr;
    // Make sure we’re on the right GPU
    cudaSetDevice(device);
    // Allocate pinned host memory that’s MAPPED into the CUDA UVA space
    cudaHostAlloc(&ptr, size,
                  cudaHostAllocMapped    // maps it into device VA space
                | cudaHostAllocPortable // visible to all contexts
                );
    return ptr;
  }

  // Free it when PyTorch asks
  void my_free(void* ptr, size_t size, cudaStream_t stream) {
    cudaFreeHost(ptr);
  }
}