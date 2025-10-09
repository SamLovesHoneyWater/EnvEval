FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /home/cc/EnvGym/data/facebook_zstd

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        python3 \
        python3-pip \
        git \
        ninja-build \
        make \
        g++ \
        libgtest-dev \
        liblz4-tool \
        brotli \
        zlib1g-dev \
        libsnappy-dev \
        liblzo2-dev \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files - this will be automatically modified by the evaluator
COPY . .

# Build zstd
RUN make

# Default command: print zstd version
CMD ["./zstd", "--version"]