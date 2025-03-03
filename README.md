# Class to simplify the search for slow and suboptimal sql queries to the database in django projects.

<div align="center">

| Project   |     | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|-----------|:----|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| CI/CD     |     | [![Latest Release](https://github.com/Friskes/capture-db-queries/actions/workflows/publish-to-pypi.yml/badge.svg)](https://github.com/Friskes/capture-db-queries/actions/workflows/publish-to-pypi.yml)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| Quality   |     | [![Coverage](https://codecov.io/github/Friskes/capture-db-queries/graph/badge.svg?token=vKez4Pycrc)](https://codecov.io/github/Friskes/capture-db-queries)                                                                                                                                                                                                                                                                                                                               |
| Package   |     | [![PyPI - Version](https://img.shields.io/pypi/v/capture-db-queries?labelColor=202235&color=edb641&logo=python&logoColor=edb641)](https://badge.fury.io/py/capture-db-queries) ![PyPI - Support Python Versions](https://img.shields.io/pypi/pyversions/capture-db-queries?labelColor=202235&color=edb641&logo=python&logoColor=edb641) ![Project PyPI - Downloads](https://img.shields.io/pypi/dm/capture-db-queries?logo=python&label=downloads&labelColor=202235&color=edb641&logoColor=edb641)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Meta      |     | [![types - Mypy](https://img.shields.io/badge/types-Mypy-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://github.com/python/mypy) [![License - MIT](https://img.shields.io/badge/license-MIT-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://spdx.org/licenses/) [![code style - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/format.json&labelColor=202235)](https://github.com/astral-sh/ruff) |

</div>

## About class
- Class allows you to track any sql queries that are executed inside the body of a loop, a decorated function, or a context manager, the body can be executed a specified number of times to get the average query execution time.

- The class allows you to display formatted output data containing brief information about the current iteration of the measurement, display sql queries and explain information on them, as well as summary information containing data on all measurements.

> **Do not use the class inside the business logic of your application, this will greatly slow down the execution of the queries, the class is intended only for the test environment.**

## Install
1. Install package
    ```bash
    pip install capture-db-queries
    ```

## About class parameters
> *All parameters are purely optional.*

- Optional parameters:
    - `assert_q_count`: The expected number of database queries during all `number_runs`, otherwise an exception will be raised: **"AssertionError: `N` not less than or equal to `N` queries"**.
    - `number_runs`: The number of runs of the decorated function or test for loop.
    - `verbose`: Displaying the final results of test measurements within all `number_runs`.
    - `advanced_verb`: Displaying the result of each test measurement.
    - `auto_call_func`: Autorun of the decorated function. *(without passing arguments to the function, since the launch takes place inside the class)*.
    - `queries`: Displaying colored and formatted SQL queries to the database.
    - `explain`: Displaying explain information about each query. (has no effect on the original query).
    - `explain_opts`: Parameters for explain. *(for more information about the parameters for explain, see the documentation for your DBMS).*
    - `connection`: Connecting to your database, by default: django.db.connection


### > WARNING: If you use `pytest-xdist` and run the test with the `-n <workers>` flag, the results will not be reflected in the terminal. Remove the `-n <workers>` flag to display them or use `--capture=tee-sys -rP` parameters.


## Usage examples

```python
from capture_db_queries import CaptureQueries
```

```python
for ctx in CaptureQueries(number_runs=2, advanced_verb=True):
    response = self.client.get(url)

>>> Test №1 | Queries count: 10 | Execution time: 0.04s
>>> Test №2 | Queries count: 10 | Execution time: 0.04s
>>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite
```

#### OR

```python
@CaptureQueries(number_runs=2, advanced_verb=True)
def test_request():
    response = self.client.get(url)

>>> Test №1 | Queries count: 10 | Execution time: 0.04s
>>> Test №2 | Queries count: 10 | Execution time: 0.04s
>>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite
```

#### OR

```python
# NOTE: The with context manager does not support multi-launch number_runs > 1
# NOTE: Also you can use `async with` if you capture queries in async context.
with CaptureQueries(number_runs=1, advanced_verb=True) as ctx:
    response = self.client.get(url)

>>> Queries count: 10  |  Execution time: 0.04s  |  Vendor: sqlite
```

> ### Example of output when using queries and explain:

```python
for _ in CaptureQueries(advanced_verb=True, queries=True, explain=True):
    list(Reporter.objects.filter(pk=1))
    list(Article.objects.filter(pk=1))

>>> Test №1 | Queries count: 2 | Execution time: 0.22s
>>>
>>>
>>> №[1] time=[0.109] explain=['2 0 0 SEARCH TABLE tests_reporter USING INTEGER PRIMARY KEY (rowid=?)']
>>> SELECT "tests_reporter"."id",
>>>     "tests_reporter"."full_name"
>>> FROM "tests_reporter"
>>> WHERE "tests_reporter"."id" = 1
>>>
>>>
>>> №[2] time=[0.109] explain=['2 0 0 SEARCH TABLE tests_article USING INTEGER PRIMARY KEY (rowid=?)']
>>> SELECT "tests_article"."id",
>>>     "tests_article"."pub_date",
>>>     "tests_article"."headline",
>>>     "tests_article"."content",
>>>     "tests_article"."reporter_id"
>>> FROM "tests_article"
>>> WHERE "tests_article"."id" = 1
>>>
>>>
>>> Tests count: 1  |  Total queries count: 2  |  Total execution time: 0.22s  |  Median time one test is: 0.109s  |  Vendor: sqlite
```

### Customization of the display
> To customize the display of SQL queries, you can import a list with handlers and remove handlers from it or expand it with your own handlers.

```python
from capture_db_queries import settings, IHandler

# NOTE: The handler must comply with the specified interface.
class SomeHandler(IHandler):
    def handle(self, queries_log):
        for query in queries_log:
            query.sql = "Hello World!"
        return queries_log

settings.PRINTER_HANDLERS.remove("capture_db_queries.handlers.ColorizeSqlHandler")
settings.PRINTER_HANDLERS.append("path.to.your.handler.SomeHandler")
```

## TODO:
1. Add support for async loop and async func decorator, __call__, __aiter__, __anext__
2. Add support for other ORM's, SQLAlchemy, etc.
