FROM texlive/texlive:latest

# Install extras you may need for LaTeX + Python tooling
RUN apt-get update && \
    apt-get install -y \
        fonts-noto-cjk \
        git \
        make \
        curl \
        python3 \
        python3-pip \
        python3-dev \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        python3-lxml \
        inkscape \
        zlib1g-dev && \
        pip install --no-cache-dir --break-system-packages svgpathtools && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# environment setup
WORKDIR /workspace
CMD ["/bin/bash"]
