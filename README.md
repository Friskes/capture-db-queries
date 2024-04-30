# Decorator for measuring the time and number of database queries

<div align="center">

| Project   |     | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|-----------|:----|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| CI/CD     |     | [![Latest Release](https://github.com/Friskes/capture-db-queries/actions/workflows/publish-to-pypi.yml/badge.svg)](https://github.com/Friskes/capture-db-queries/actions/workflows/publish-to-pypi.yml)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Quality   |     | [![Coverage](https://codecov.io/github/Friskes/capture-db-queries/graph/badge.svg?token=vKez4Pycrc)](https://codecov.io/github/Friskes/capture-db-queries)                                                                                                                                                                                                                                                                                                                               |
| Package   |     | [![PyPI - Version](https://img.shields.io/pypi/v/capture-db-queries?labelColor=202235&color=edb641&logo=python&logoColor=edb641)](https://badge.fury.io/py/capture-db-queries) ![PyPI - Support Python Versions](https://img.shields.io/pypi/pyversions/capture-db-queries?labelColor=202235&color=edb641&logo=python&logoColor=edb641) ![Project PyPI - Downloads](https://img.shields.io/pypi/dm/capture-db-queries?logo=python&label=downloads&labelColor=202235&color=edb641&logoColor=edb641)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Meta      |     | [![types - Mypy](https://img.shields.io/badge/types-Mypy-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://github.com/python/mypy) [![License - MIT](https://img.shields.io/badge/license-MIT-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://spdx.org/licenses/) [![code style - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/format.json&labelColor=202235)](https://github.com/astral-sh/ruff) |

</div>

> Provides a decorator for measuring the time and number of database queries

## Install
1. Install package
    ```bash
    pip install capture-db-queries
    ```

## About decorator
`capture_queries` decorator it can call the body of the decorated function the specified number of times for multiple measurements, it can validate the total number of queries.

- Optional parameters:
    - `assert_q_count`: The expected number of database requests is otherwise "AssertionError: N not less than or equal to N queries"
    - `number_runs`: The number of runs of the test function `_`
    - `verbose`: Displaying the final results of the test measurements
    - `advanced_verb`: Displaying the result of each test measurement
    - `queries`: Displaying raw SQL queries to the database

## About context manager
`ExtCaptureQueriesContext`

- Optional parameters:
    - `assert_q_count`: The expected number of database requests is otherwise "AssertionError: N not less than or equal to N queries"
    - `verbose`: Displaying the final results of the test measurements
    - `queries`: Displaying raw SQL queries to the database


## Usage example

```python
from capture_db_queries.decorators import capture_queries


@capture_queries(number_runs=2, advanced_verb=True)
def _():
    response = self.client.get(url)

>>> Test №1 | Queries count: 10 | Execution time: 0.04s
>>> Test №2 | Queries count: 10 | Execution time: 0.04s
>>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s
```

```python
from capture_db_queries.decorators import ExtCaptureQueriesContext


with ExtCaptureQueriesContext():
    response = self.client.get(url)

>>> Queries count: 164  |  Execution time: 0.923s
```
