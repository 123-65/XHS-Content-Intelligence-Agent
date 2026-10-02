FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir langchain-chatchat==0.3.1.3

ENTRYPOINT ["chatchat"]

