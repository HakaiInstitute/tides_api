FROM mambaorg/micromamba:focal-cuda-12.3.1 as build
COPY environment.yaml /tmp/env.yaml
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yaml /tmp/env.yaml
RUN micromamba install -y -n base -f /tmp/env.yaml && \
    micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
EXPOSE 80

WORKDIR /app
COPY ./tide_api /app/tide_api

CMD ["uvicorn", "tide_api.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
