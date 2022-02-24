# Makefile for packaging and testing django-pgtrigger
#
# This Makefile has the following targets:
#
# setup - Sets up the development environment
# dependencies - Installs dependencies
# clean-docs - Clean the documentation folder
# open-docs - Open any docs generated with "make docs"
# docs - Generated sphinx docs
# lint - Run code linting and static checks
# format - Format code using black
# test - Run tests using pytest
# full-test-suite - Run full test suite using tox
# shell - Run a shell in a virtualenv
# teardown - Spin down docker resources

OS = $(shell uname -s)

PACKAGE_NAME=django-pgtrigger
MODULE_NAME=pgtrigger
SHELL=bash

ifeq (${OS}, Linux)
	DOCKER_CMD?=sudo docker
	DOCKER_RUN_ARGS?=-v /home:/home -v $(shell pwd):/code -e DOCKER_EXEC_WRAPPER="" -u "$(shell id -u):$(shell id -g)"  -v /etc/passwd:/etc/passwd
	# The user can be passed to docker exec commands in Linux.
	# For example, "make shell user=root" for access to apt-get commands
	user?=$(shell id -u)
	group?=$(shell id ${user} -u)
	DOCKER_EXEC_WRAPPER?=$(DOCKER_CMD) exec --user="$(user):$(group)" -it $(PACKAGE_NAME)
else ifeq (${OS}, Darwin)
	DOCKER_CMD?=docker
	DOCKER_RUN_ARGS?=-v ~/:/home/circleci -v $(shell pwd):/code -e DOCKER_EXEC_WRAPPER=""
	DOCKER_EXEC_WRAPPER?=$(DOCKER_CMD) exec -it $(PACKAGE_NAME)
endif

# Docker run mounts the local code directory, SSH (for git), and global git config information
DOCKER_RUN_CMD?=$(DOCKER_CMD)-compose run --name $(PACKAGE_NAME) $(DOCKER_RUN_ARGS) -d app


# Print usage of main targets when user types "make" or "make help"
.PHONY: help
help:
ifndef run
	@echo "Please choose one of the following targets: \n"\
	      "    setup: Setup development environment\n"\
	      "    lock: Lock dependencies\n"\
	      "    dependencies: Install dependencies\n"\
	      "    shell: Start a shell\n"\
	      "    test: Run tests\n"\
	      "    tox: Run tests against all versions of Python\n"\
	      "    lint: Run code linting and static checks\n"\
	      "    format: Format code using Black\n"\
	      "    docs: Build Sphinx documentation\n"\
	      "    open-docs: Open built documentation\n"\
	      "    teardown: Spin down docker resources\n"\
	      "\n"\
	      "View the Makefile for more documentation"
	@exit 2
else
	$(DOCKER_EXEC_WRAPPER) $(run)
endif


# Ensure we are logged into the Gitlab docker registry and start a detached container
.PHONY: docker-start
docker-start:
	$(DOCKER_CMD) pull opus10/circleci-public-django-app
	$(DOCKER_RUN_CMD)


# Lock dependencies
.PHONY: lock
lock:
	$(DOCKER_EXEC_WRAPPER) poetry lock --no-update


# Install dependencies
.PHONY: dependencies
dependencies:
	$(DOCKER_EXEC_WRAPPER) poetry install


# Sets up development environment
.PHONY: setup
setup: teardown docker-start lock dependencies
	$(DOCKER_EXEC_WRAPPER) git tidy --template -o .gitcommit.tpl
	$(DOCKER_EXEC_WRAPPER) git config --local commit.template .gitcommit.tpl


# Run a shell
.PHONY: shell
shell:
	$(DOCKER_EXEC_WRAPPER) /bin/bash


# Run pytest
.PHONY: test
test:
	$(DOCKER_EXEC_WRAPPER) pytest


# Run full test suite
.PHONY: full-test-suite
full-test-suite:
	$(DOCKER_EXEC_WRAPPER) tox


# Clean the documentation folder
.PHONY: clean-docs
clean-docs:
	-$(DOCKER_EXEC_WRAPPER) bash -c 'cd docs && make clean'


# Open the build docs (only works on Mac)
.PHONY: open-docs
open-docs:
ifeq (${OS}, Darwin)
	open docs/_build/html/index.html
else ifeq (${OS}, Linux)
	xdg-open docs/_build/html/index.html
else
	@echo "Open 'docs/_build/html/index.html' to view docs"
endif


# Build Sphinx autodocs
.PHONY: docs
docs: clean-docs  # Ensure docs are clean, otherwise weird render errors can result
	$(DOCKER_EXEC_WRAPPER) bash -c 'cd docs && make html'


# Run code linting and static analysis. Ensure docs can be built
.PHONY: lint
lint:
	$(DOCKER_EXEC_WRAPPER) black . --check
	$(DOCKER_EXEC_WRAPPER) flake8 -v ${MODULE_NAME}
	$(DOCKER_EXEC_WRAPPER) temple update --check
	$(DOCKER_EXEC_WRAPPER) bash -c 'cd docs && make html'


# Lint commit messages
.PHONY: tidy-lint
tidy-lint:
	$(DOCKER_EXEC_WRAPPER) git tidy-lint origin/master..


# Perform a tidy commit
.PHONY: tidy-commit
tidy-commit:
	$(DOCKER_EXEC_WRAPPER) git tidy-commit


# Perform a tidy squash
.PHONY: tidy-squash
tidy-squash:
	$(DOCKER_EXEC_WRAPPER) git tidy-squash origin/master


# Format code with black
.PHONY: format
format:
	$(DOCKER_EXEC_WRAPPER) black .


# Spin down docker resources
.PHONY: teardown
teardown:
	$(DOCKER_CMD)-compose down
