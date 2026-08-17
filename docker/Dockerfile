# Generic qualification image. It is deliberately candidate-agnostic: the
# candidate is a runtime argument, never baked in, so a successor needs no
# Dockerfile of its own.
#
# Pinned by digest so the container environment is reproducible.
FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134

# The pipeline is standard-library only by design: no pip install step exists,
# so there is no dependency resolution inside the image and nothing to pin
# beyond the interpreter itself.
WORKDIR /work
COPY src/wexp_ref /work/wexp_ref

# Run as a module so the package's own imports resolve.
ENV PYTHONPATH=/work
ENTRYPOINT ["python3", "-m", "wexp_ref.core01.harness.orchestrate"]
CMD ["--help"]
