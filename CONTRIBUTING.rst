Contributing Guide
==================

This project was created using temple.
For more information about temple, go to the
`Temple docs <https://github.com/CloverHealth/temple>`_.

Setup
~~~~~

Set up your development environment with::

    git clone git@github.com:Opus10/django-pgtrigger.git
    cd django-pgtrigger
    make setup

``make setup`` will setup python managed by
`pyenv <https://github.com/yyuu/pyenv>`_ and install dependencies using
`poetry <https://poetry.eustace.io/>`_.

Testing and Validation
~~~~~~~~~~~~~~~~~~~~~~

Run the tests with::

    make test

Validate the code with::

    make lint

Run automated code formatting with::

    make format

Documentation
~~~~~~~~~~~~~

`Sphinx <http://www.sphinx-doc.org/>`_ documentation can be built with::

    make docs

The static HTML files are stored in the ``docs/_build/html`` directory.
A shortcut for opening them (on OSX) is::

    make open_docs

Releases and Versioning
~~~~~~~~~~~~~~~~~~~~~~~

Anything that is merged into the master branch will be automatically deployed
to PyPI. Documentation will be published to a ReadTheDocs website at
``https://django-pgtrigger.readthedocs.io/``.

The following files will be generated and should *not* be edited by a user:

* ``CHANGELOG.md`` - Contains an automatically-generated change log for
  each release.

This project uses `Semantic Versioning <http://semver.org>`_ by analyzing
``Type:`` trailers on git commit messages (trailers are added when using
``git tidy-commit``). In order to bump the minor
version, use "feature" or "bug" as the type.
In order to bump the major version, use "api-break". The patch version
will be updated automatically if none of these tags are present.
