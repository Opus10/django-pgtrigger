# Contributing Guide

This project was created using footing. For more information about footing, go to the [footing docs](https://github.com/Opus10/footing).

## Setup

Set up your development environment with:

    git clone git@github.com:Opus10/django-pgtrigger.git
    cd django-pgtrigger
    make docker-setup

`make docker-setup` will set up a development environment managed by Docker. Install docker [here](https://www.docker.com/get-started) and be sure it is running when executing any of the commands below.

If you prefer a native development environment, `make conda-setup` will set up a development environment managed by [Conda](https://conda.io). The database must be ran manually.

## Testing and Validation

Run the tests on one Python version with:

    make test

Run the full test suite against all supported Python versions with:

    make full-test-suite

Validate the code with:

    make lint

If your code fails the linter checks, fix common errors with:

    make lint-fix

Run type checking with:

    make type-check

## Committing

This project uses [git-tidy](https://github.com/Opus10/git-tidy) to produce structured commits with git trailers. Information from commit messages is used to generate release notes and bump the version properly.

To do a structured commit with `git-tidy`, do:

    make tidy-commit

All commits in a pull request must be tidy commits that encapsulate a change. Ideally entire features or bug fixes are encapsulated in a single commit. Squash all of your commits into a tidy commit with:

    make tidy-squash

To check if your commits pass linting, do:

    make tidy-lint

Note, the above command lints every commit since branching from main. You can also run `make shell` and run `git tidy` commands inside the docker environment to do other flavors of `git tidy` commands.

## Documentation

[Mkdocs Material](https://squidfunk.github.io/mkdocs-material/) documentation can be built with:

    make docs

A shortcut for serving them is:

    make docs-serve

## Releases and Versioning

Anything that is merged into the main branch will be automatically deployed to PyPI. Documentation will be published to a ReadTheDocs at `https://django-pgtrigger.readthedocs.io/`.

The following files will be generated and should *not* be edited by a user:

- `CHANGELOG.md` - Contains an automatically-generated change log for each release.

This project uses [Semantic Versioning](http://semver.org) by analyzing `Type:` trailers on git commit messages (trailers are added when using `git tidy-commit`). In order to bump the minor version, use "feature" or "bug" as the type. In order to bump the major version, use "api-break". The patch version will be updated automatically if none of these tags are present.
