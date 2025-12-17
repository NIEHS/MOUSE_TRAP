# Use an official Python image
FROM python:3.13-slim

LABEL maintainer="Riley Harper <riley.harper@nih.gov>" \
      org.opencontainers.image.source="https://github.com/NIEHS/MOUSE_TRAP" \
      org.opencontainers.image.title="MOUSE_TRAP"

# Non-interactive apt; nicer Qt behavior
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# System dependencies:
# - ffmpeg: video conversion
# - pandoc: PDF/DOCX/TXT conversions via pypandoc
# - poppler-utils: pdftoppm, etc. for pdf2image
# - X/GL libs: for PyQt6 GUI
# - curl: to install uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        pandoc \
        poppler-utils \
        libgl1 \
        libegl1 \
        libglib2.0-0 \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libxkbcommon-x11-0 \
        libfontconfig1 \
        libxcb1 \
        libx11-xcb1 \
        libxcb-render0 \
        libxcb-shape0 \
        libxcb-xfixes0 \
        libxcb-cursor0 \
        libpipewire-0.3-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# NOTE: docx2pdf requires Microsoft Word and will NOT work inside this
# Linux container. DOCX→PDF conversions will be limited.

# App directory
WORKDIR /app

# Copy the repo into the image
COPY . /app

# Install MOUSE_TRAP + Python deps
RUN pip install --upgrade pip && \
    pip install --no-cache-dir .

# Create non-root user to run the GUI
RUN useradd -ms /bin/bash app && chown -R app:app /app
USER app

# Install uv for the app user and then install SLEAP via uv
# NOTE:
# - This command uses the CUDA 12.8 wheel index. It assumes your host
#   has an NVIDIA GPU and you run the container with `--gpus all`.
# - If you want CPU-only SLEAP, use:
#     uv tool install "sleap[nn]"
#   (without the extra --index).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /home/app/.local/bin/uv tool install "sleap[nn]" \
      --index https://download.pytorch.org/whl/cu128 \
      --index https://pypi.org/simple

# Make uv-installed tools (including sleap) available on PATH
ENV PATH="/home/app/.local/bin:${PATH}"

# A volume where users can mount data (videos, docs, etc.)
VOLUME ["/data"]
ENV MOUSE_TRAP_DATA=/data

# Default command: launch the GUI
ENTRYPOINT ["mouse-trap"]