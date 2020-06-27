# Makefile for packaging and testing django-pgtrigger
#
# This Makefile has the following targets:
#
# package_managers - Sets up python managers and python package managers
# clean_env - Removes the virtuale env
# dependencies - Installs all dependencies for a project
# setup - Sets up the entire development environment and installs dependencies
# clean_docs - Clean the documentation folder
# clean - Clean any generated files (including documentation)
# open_docs - Open any docs generated with "make docs"
# docs - Generated sphinx docs
# lint - Run code linting and static checks
# format - Format code using black
# test - Run tests using pytest

OS = $(shell uname -s)

PACKAGE_NAME=django-pgtrigger
MODULE_NAME=pgtrigger

PY36_VERSION=3.6.5
PY37_VERSION=3.7.6
PY38_VERSION=3.8.2

# Print usage of main targets when user types "make" or "make help"
help:
	@echo "Please choose one of the following targets: \n"\
	      "    setup: Setup development environment and install dependencies\n"\
	      "    test: Run tests\n"\
	      "    lint: Run code linting and static checks\n"\
	      "    docs: Build Sphinx documentation\n"\
	      "    open_docs: Open built documentation\n"\
	      "\n"\
	      "View the Makefile for more documentation"
	@exit 2


# Utility to verify we arent in a virtualenv
.PHONY: check_not_inside_venv
check_not_inside_venv:
ifeq (${OS}, Darwin)
	which pip | grep -q ".pyenv" || (echo "Please deactivate your virtualenv and try again" && exit 1)
endif


# Sets up pyenv, poetry, and any other package/language managers (e.g. NPM)
.PHONY: package_managers
package_managers: check_not_inside_venv
ifeq (${OS}, Darwin)
# Install pyenv and ensure we remain up to date with pyenv so that new python
# versions are available for installation
	-brew install pyenv 2> /dev/null
	-brew upgrade pyenv 2> /dev/null
	-pyenv rehash
	pyenv install -s ${PY36_VERSION}
	pyenv install -s ${PY37_VERSION}
	pyenv install -s ${PY38_VERSION}
	pyenv local ${PY36_VERSION} ${PY37_VERSION} ${PY38_VERSION}
endif
# Conditionally install pipx so that we can globally install poetry
	pip install --user --upgrade --force-reinstall pipx
	pipx ensurepath
	-pipx install --force poetry --pip-args="--upgrade"


# Remove the virtual environment
.PHONY: clean_env
clean_env:
	-poetry env remove ${PYTHON_VERSION}


# Builds all dependencies for a project
.PHONY: dependencies
dependencies:
	poetry install


.PHONY: git_tidy
git_tidy:
	-pipx install --force git-tidy --pip-args="--upgrade"
	git tidy --template -o .gitcommit.tpl
	git config --local commit.template .gitcommit.tpl


.PHONY: pre_commit
pre_commit:
	poetry run pre-commit install


# Sets up the database and the environment files for the first time
.PHONY: db_and_env_setup
db_and_env_setup:
ifeq (${OS}, Darwin)
	-brew install postgresql 2> /dev/null
	brew services start postgresql
endif
	-psql postgres -c "CREATE USER postgres;"
	-psql postgres -c "ALTER USER postgres SUPERUSER;"
	-psql postgres -c "CREATE DATABASE ${MODULE_NAME}_local OWNER postgres;"
	-psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE ${MODULE_NAME}_local to postgres;"
	-cp -n .env.template .env


.PHONY: ci_setup
ci_setup: package_managers git_tidy db_and_env_setup dependencies


# Sets up environment and installs dependencies
.PHONY: setup
setup: check_not_inside_venv package_managers git_tidy db_and_env_setup dependencies pre_commit


# Clean the documentation folder
.PHONY: clean_docs
clean_docs:
	-cd docs && poetry run make clean


# Clean any auto-generated files
.PHONY: clean
clean: clean_docs clean_env
	rm -rf dist/*
	rm -rf coverage .coverage .coverage*
	rm -rf .venv


# Open the build docs (only works on Mac)
.PHONY: open_docs
open_docs:
ifeq (${OS}, Darwin)
	open docs/_build/html/index.html
else
	@echo "Open 'docs/_build/html/index.html' to view docs"
endif


# Build Sphinx autodocs
.PHONY: docs
docs: clean_docs  # Ensure docs are clean, otherwise weird render errors can result
	cd docs && poetry run make html


# Run code linting and static analysis
.PHONY: lint
lint:
	poetry run black . --check
	poetry run flake8 -v ${MODULE_NAME}/
	poetry run temple update --check
	poetry run make docs  # Ensure docs can be built during validation


# Lint commit messages and show changelog when on circleci
check_changelog:
ifdef CIRCLECI
	git tidy-log origin/master..
endif
	git tidy-lint origin/master


# Format code
format:
	poetry run black .


# Run tests
.PHONY: test
test:
	poetry run tox


# Show the version and name of the project
.PHONY: version
version:
	-@poetry version | rev | cut -f 1 -d' ' | rev


.PHONY: project_name
project_name:
	-@poetry version | cut -d' ' -f1
