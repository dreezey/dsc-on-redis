FROM tiangolo/meinheld-gunicorn-flask:python3.7

RUN pip install redis

COPY ./app /app
