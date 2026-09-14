FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY /requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --force-reinstall

COPY / /usr/local/template

CMD ["python", "/usr/local/template/main.py"]