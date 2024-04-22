# Decorator for measuring the time and number of database queries


> Provides a decorator for measuring the time and number of database queries


## Requirements
- django>=4.2.11


## Install
1. `pip install capture-db-queries`


## About decorator
capture_db_queries `capture_queries` it can call the body of the decorated function the specified number of times for multiple measurements, it can validate the total number of queries.

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

Direct usage

```python
from capture_db_queries.decorators import capture_queries


@capture_queries(number_runs=2, advanced_verb=True)
def _():
    response = self.client.get(url)

>>> Test №1 | Queries count: 10 | Execution time: 0.04s
>>> Test №2 | Queries count: 10 | Execution time: 0.04s
>>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s


with ExtCaptureQueriesContext():
    response = self.client.get(url)

>>> Queries count: 164  |  Execution time: 0.923s
```
