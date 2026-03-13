FROM python:3.11-slim

# System deps for Playwright + general tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget gnupg ca-certificates \
    # Playwright Chromium dependencies
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | sh 2>/dev/null || \
    npm install -g @anthropic-ai/claude-code 2>/dev/null || \
    echo "Claude Code CLI will need manual install"

# Install Node.js (needed for Claude Code if not bundled)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /toolkit

# Copy toolkit source
COPY pyproject.toml .
COPY scripts/ scripts/
COPY tests/ tests/
COPY templates/ templates/
COPY hooks/ hooks/
COPY README.md LICENSE ./

# Install toolkit with all extras (tests deps auto-install)
RUN pip install --no-cache-dir -e ".[dev,screenshots]"

# Install Playwright Chromium browser
RUN python -m playwright install chromium

# Create a test workspace to simulate real usage
RUN mkdir -p /workspace/.preset-toolkit/.secrets && \
    mkdir -p /workspace/sync/assets/dashboards && \
    mkdir -p /workspace/sync/assets/charts && \
    mkdir -p /workspace/sync/assets/datasets/db

# Copy config template into test workspace
COPY templates/config.yaml /workspace/.preset-toolkit/config.yaml
COPY templates/ownership.yaml /workspace/.preset-toolkit/ownership.yaml
COPY templates/markers.txt /workspace/.preset-toolkit/markers.txt

WORKDIR /workspace

# Verify installation on build
RUN python -c "from scripts.config import ToolkitConfig; print('config: OK')" && \
    python -c "from scripts.sync import pull, push; print('sync: OK')" && \
    python -c "from scripts.screenshot import capture_sync; print('screenshot: OK')" && \
    python -c "from scripts.visual_diff import compare_images; print('visual_diff: OK')" && \
    python -c "from scripts.telemetry import get_telemetry; print('telemetry: OK')" && \
    echo "All modules loaded successfully"

CMD ["bash"]
