FROM continuumio/miniconda3 as build
COPY environment.yaml /tmp/env.yaml
RUN conda env create -f /tmp/env.yaml

FROM python:3.11
COPY --from=build /opt/conda /opt/conda

ENV PATH /opt/conda/envs/tides/bin:$PATH
ENTRYPOINT ["/bin/bash"]
WORKDIR /app
COPY ./tide_api /app/tide_api
COPY ./tide_tools /app/tide_tools

EXPOSE 80

ENTRYPOINT ["uvicorn", "tide_api.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
