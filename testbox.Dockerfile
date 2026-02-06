FROM python:3.11-slim as testbox

RUN pip install poetry==2.2.1

RUN mkdir -p /code
WORKDIR /code
RUN ls
COPY ./ /code
RUN poetry install --with dev

CMD ["poetry", "run", "tox"]
