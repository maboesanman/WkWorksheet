# =============================================================================
# Stage 1: Base image with system dependencies (used by dev container)
# =============================================================================
FROM texlive/texlive:latest AS base

# Install system packages needed for LaTeX + Python tooling
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
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

WORKDIR /workspace
CMD ["/bin/bash"]

# =============================================================================
# Stage 2: Runtime image with cron job for production
# =============================================================================
FROM base AS runtime

# Install cron
RUN apt-get update && \
    apt-get install -y cron tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set timezone to Chicago
ENV TZ=America/Chicago
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Python dependencies
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir --break-system-packages --ignore-installed -r /workspace/requirements.txt

# Copy the application source
COPY . /workspace


# Create the cron job: run at 2am Chicago time every day
# Output is logged to /var/log/wkworksheet.log
RUN echo "0 2 * * * cd /workspace && python -m wkworksheet.generate >> /var/log/wkworksheet.log 2>&1" > /etc/cron.d/wkworksheet && \
    chmod 0644 /etc/cron.d/wkworksheet && \
    crontab /etc/cron.d/wkworksheet && \
    touch /var/log/wkworksheet.log

# Declare volumes for persistent data
VOLUME /workspace/out
VOLUME /workspace/cache
VOLUME /workspace/fonts

# Start cron in foreground
CMD ["cron", "-f"]
