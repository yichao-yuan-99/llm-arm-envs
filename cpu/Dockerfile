ARG CUDA_VERSION=12.8.1
ARG IMAGE_DISTRO=ubuntu24.04
ARG PYTHON_VERSION=3.12

# ---------- Builder Base ----------
FROM nvcr.io/nvidia/cuda:${CUDA_VERSION}-devel-${IMAGE_DISTRO} AS base

# ---------- vllm environment ----------
ENV HOME=/
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update 
RUN apt install -y curl ccache git wget vim numactl gcc-12 g++-12 python3 python3-pip python3-venv python-is-python3 libtcmalloc-minimal4 libnuma-dev ffmpeg libsm6 libxext6 libgl1 libssl-dev pkg-config
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 10 --slave /usr/bin/g++ g++ /usr/bin/g++-12

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh


RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y 
RUN . ${HOME}/.cargo/env


ARG PYTHON_VERSION
RUN uv venv -p ${PYTHON_VERSION} --seed --python-preference only-managed
ENV VIRTUAL_ENV=${HOME}/.venv
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}

# ENV CCACHE_DIR=/home/ubuntu/.cache/ccache
# ENV CMAKE_CXX_COMPILER_LAUNCHER=ccache
ENV VLLM_CPU_DISABLE_AVX512="true"
ENV LD_PRELOAD="/usr/lib/aarch64-linux-gnu/libtcmalloc_minimal.so.4"

RUN uv pip install --upgrade pip \
    && uv pip install py-cpuinfo

# ---------- vllm build ----------
# RUN git clone https://github.com/vllm-project/vllm.git \
#     && cd vllm \
#     && git checkout 72ff3a968682e6a3f7620ab59f2baf5e8eb2777b \
#     && uv pip install -r requirements-build.txt \
#     && uv pip install -v -r requirements-cpu.txt
ENV VLLM_TARGET_DEVICE=cpu
RUN git clone https://github.com/vllm-project/vllm.git \
    && cd vllm \
    && git checkout v0.9.1 \
    && uv pip install -r requirements/build.txt \
    && uv pip install -v -r requirements/cpu.txt \
    && python3 setup.py bdist_wheel \
    && uv pip install dist/*.whl

COPY ./scripts ${HOME}/scripts

CMD ["/bin/bash"]
