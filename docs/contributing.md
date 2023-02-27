# Contributions

The easiest way to contribute is to post an issue on the [issue tracker](https://github.com/dunkyl/SlyAPI-Python/issues)!

To install a local development instance:

```sh
git clone https://github.com/dunkyl/SlyAPI-Python
cd SlyAPI-Python
pip install -e .[dev]
```

The `[dev]` option will install the additional dependencies for running tests and building the documentaion.

## Testing

Tests are run using pytest. Some tests are skipped by default and are configured to run only when debugging the tests, which enables normal tests to be run without aquiring credentials.

## Documentation

Documentation is built using sphinx. On windows, run `make.bat`. On Linux or MacOS, it requires and uses `make`.