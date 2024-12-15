# Makefile for packaging and testing django-pgtrigger
#
# This Makefile has the following targets:
#
# setup - Sets up the development environment
# dependencies - Installs dependencies
# docs - Build documentation
# docs-serve - Serve documentation
# lint - Run code linting and static checks
# lint-fix - Fix common linting errors
# type-check - Run Pyright type-checking
# test - Run tests using pytest
# full-test-suite - Run full test suite using tox
# shell - Run a shell in a virtualenv
# docker-teardown - Spin down docker resources

OS = $(shell uname -s)

PACKAGE_NAME=django-pgtrigger
MODULE_NAME=pgtrigger
SHELL=bash

ifeq (${OS}, Linux)
	DOCKER_CMD?=sudo docker
	DOCKER_RUN_ARGS?=-v /home:/home -v $(shell pwd):/code -e EXEC_WRAPPER="" -u "$(shell id -u):$(shell id -g)"  -v /etc/passwd:/etc/passwd
	# The user can be passed to docker exec commands in Linux.
	# For example, "make shell user=root" for access to apt-get commands
	user?=$(shell id -u)
	group?=$(shell id ${user} -u)
	EXEC_WRAPPER?=$(DOCKER_CMD) exec --user="$(user):$(group)" -it $(PACKAGE_NAME)
else ifeq (${OS}, Darwin)
	DOCKER_CMD?=docker
	DOCKER_RUN_ARGS?=-v ~/:/home/circleci -v $(shell pwd):/code -e EXEC_WRAPPER=""
	EXEC_WRAPPER?=$(DOCKER_CMD) exec -it $(PACKAGE_NAME)
endif

# Docker run mounts the local code directory, SSH (for git), and global git config information
DOCKER_RUN_CMD?=$(DOCKER_CMD) compose run --name $(PACKAGE_NAME) $(DOCKER_RUN_ARGS) -d app

# Print usage of main targets when user types "make" or "make help"
.PHONY: help
help:
ifndef run
	@echo "Please choose one of the following targets: \n"\
	      "    docker-setup: Setup Docker development environment\n"\
	      "    conda-setup: Setup Conda development environment\n"\
	      "    lock: Lock dependencies\n"\
	      "    dependencies: Install dependencies\n"\
	      "    shell: Start a shell\n"\
	      "    test: Run tests\n"\
	      "    tox: Run tests against all versions of Python\n"\
	      "    lint: Run code linting and static checks\n"\
	      "    lint-fix: Fix common linting errors\n"\
	      "    type-check: Run Pyright type-checking\n"\
	      "    docs: Build documentation\n"\
	      "    docs-serve: Serve documentation\n"\
	      "    docker-teardown: Spin down docker resources\n"\
	      "\n"\
	      "View the Makefile for more documentation"
	@exit 2
else
	$(EXEC_WRAPPER) $(run)
endif


# Pull the latest container and start a detached run
.PHONY: docker-start
docker-start:
	$(DOCKER_CMD) compose pull
	$(DOCKER_RUN_CMD)


# Lock dependencies
.PHONY: lock
lock:
	$(EXEC_WRAPPER) poetry lock --no-update
	$(EXEC_WRAPPER) poetry export --with dev --without-hashes -f requirements.txt > docs/requirements.txt


# Install dependencies
.PHONY: dependencies
dependencies:
	$(EXEC_WRAPPER) poetry install --no-ansi


# Sets up the local database
.PHONY: db-setup
db-setup:
	-psql postgres -c "CREATE USER postgres;"
	-psql postgres -c "ALTER USER postgres SUPERUSER;"
	-psql postgres -c "CREATE DATABASE ${MODULE_NAME}_local OWNER postgres;"
	-psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE ${MODULE_NAME}_local to postgres;"
	$(EXEC_WRAPPER) python manage.py migrate


# Sets up a conda development environment
.PHONY: conda-create
conda-create:
	-conda env create -f environment.yml -y
	$(EXEC_WRAPPER) poetry config virtualenvs.create false --local


# Sets up a Conda development environment
.PHONY: conda-setup
conda-setup: EXEC_WRAPPER=conda run -n ${PACKAGE_NAME} --no-capture-output
conda-setup: conda-create lock dependencies db-setup


# Sets up a Docker development environment
.PHONY: docker-setup
docker-setup: docker-teardown docker-start lock dependencies


# Spin down docker resources
.PHONY: docker-teardown
docker-teardown:
	$(DOCKER_CMD) compose down --remove-orphans


# Run a shell
.PHONY: shell
shell:
	$(EXEC_WRAPPER) /bin/bash


# Run pytest
.PHONY: test
test:
	$(EXEC_WRAPPER) pytest


# Run full test suite
.PHONY: full-test-suite
full-test-suite:
	$(EXEC_WRAPPER) tox


# Build documentation
.PHONY: docs
docs:
	$(EXEC_WRAPPER) mkdocs build -s


# Serve documentation
.PHONY: docs-serve
docs-serve:
	$(EXEC_WRAPPER) mkdocs serve


# Run code linting and static analysis. Ensure docs can be built
.PHONY: lint
lint:
	$(EXEC_WRAPPER) ruff format . --check
	$(EXEC_WRAPPER) ruff check ${MODULE_NAME}
	$(EXEC_WRAPPER) bash -c 'make docs'
	$(EXEC_WRAPPER) diff <(poetry export --with dev --without-hashes -f requirements.txt) docs/requirements.txt >/dev/null 2>&1 || exit 1


# Fix common linting errors
.PHONY: lint-fix
lint-fix:
	$(EXEC_WRAPPER) ruff format .
	$(EXEC_WRAPPER) ruff check ${MODULE_NAME} --fix


# Run Pyright type-checking
.PHONY: type-check
type-check:
	$(EXEC_WRAPPER) pyright $(MODULE_NAME)
