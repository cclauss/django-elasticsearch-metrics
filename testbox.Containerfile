FROM python:3.11-slim as testbox

RUN pip install poetry==2.2.1

RUN mkdir -p /code
WORKDIR /code

COPY pyproject.toml poetry.lock ./
RUN poetry install --compile --no-root --with=dev --extras=elastic6 --extras=elastic8
COPY ./ ./
RUN poetry install --compile --only-root

CMD ["poetry", "run", "tox"]
