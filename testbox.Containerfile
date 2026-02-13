FROM python:3.10-slim as testbox

RUN pip install poetry==2.3.2

RUN mkdir -p /code
WORKDIR /code

COPY pyproject.toml poetry.lock ./
RUN poetry install --compile --no-root --with=dev --extras=elastic6
COPY ./ ./
RUN poetry install --compile --only-root

CMD ["poetry", "run", "tox"]
