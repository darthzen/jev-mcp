# Base image policy: openSUSE / SUSE BCI only.
# registry.suse.com/bci/python:3.13 carries linux/amd64; the openSUSE
# registry.opensuse.org/opensuse/bci/python:3.13 manifest does not (2026-07).
#
#   builder : self-contained venv with pinned wheels
#   runtime : copies the venv, drops privileges, no compilers on the final image

FROM registry.suse.com/bci/python:3.13 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /build
RUN python3 -m venv "$VIRTUAL_ENV"

COPY pyproject.toml README.md ./
COPY src ./src
RUN python3 -m pip install --upgrade pip setuptools wheel \
 && python3 -m pip install .

# ------------------------------------------------------------------------------
FROM registry.suse.com/bci/python:3.13 AS runtime

LABEL org.opencontainers.image.title="jev-mcp" \
      org.opencontainers.image.description="MCP server for TypeSafe Jev (System One)" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/darthzen/jev-mcp" \
      org.opencontainers.image.base.name="registry.suse.com/bci/python:3.13"

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JEV_BIND_HOST=0.0.0.0 \
    JEV_BIND_PORT=8080

COPY --from=builder /opt/venv /opt/venv

# Fixed uid/gid so a PodSecurity "restricted" namespace can pin runAsUser.
RUN groupadd --gid 10001 jevmcp \
 && useradd  --uid 10001 --gid 10001 --home-dir /home/jevmcp --create-home --shell /sbin/nologin jevmcp \
 && chown -R 10001:10001 /opt/venv

USER 10001:10001
WORKDIR /home/jevmcp
EXPOSE 8080

ENTRYPOINT ["jev-mcp"]
