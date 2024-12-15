# Contributing Guide

This project was created using footing. For more information about footing, go to the [footing docs](https://github.com/AmbitionEng/footing).

## Setup

Set up your development environment with:

    git clone git@github.com:AmbitionEng/django-pgtrigger.git
    cd django-pgtrigger
    make docker-setup

`make docker-setup` will set up a development environment managed by Docker. Install docker [here](https://www.docker.com/get-started) and be sure it is running when executing any of the commands below.

If you prefer a native development environment, `make conda-setup` will set up a development environment managed by [Conda](https://conda.io). Dependent services, such as databases, must be ran manually.

## Testing and Validation

Run the tests on one Python version with:

    make test

Run the full test suite against all supported Python versions with:

    make full-test-suite

Validate the code with:

    make lint

If your code fails the linter checks, fix common errors with:

    make lint-fix

## Documentation

[Mkdocs Material](https://squidfunk.github.io/mkdocs-material/) documentation can be built with:

    make docs

A shortcut for serving them is:

    make docs-serve

## Releases and Versioning

The version number and release notes are manually updated by the maintainer during the release process. Do not edit these.