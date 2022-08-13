import contextlib
import logging

from django.core.management.base import BaseCommand

from pgtrigger import api
from pgtrigger import core
from pgtrigger import utils


def _setup_logging():  # pragma: no cover
    api.LOGGER.addHandler(logging.StreamHandler())
    api.LOGGER.setLevel(logging.INFO)


class SubCommands(BaseCommand):  # pragma: no cover
    """
    Subcommand class vendored in from
    https://github.com/andrewp-as-is/django-subcommands.py
    because of installation issues
    """

    argv = []
    subcommands = {}

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='subcommand', title='subcommands', description='')
        subparsers.required = True

        for command_name, command_class in self.subcommands.items():
            command = command_class()

            subparser = subparsers.add_parser(command_name, help=command_class.help)
            command.add_arguments(subparser)
            prog_name = subcommand = ''
            if self.argv:
                prog_name = self.argv[0]
                subcommand = self.argv[1]

            command_parser = command.create_parser(prog_name, subcommand)
            subparser._actions = command_parser._actions

    def run_from_argv(self, argv):
        self.argv = argv
        return super().run_from_argv(argv)

    def handle(self, *args, **options):
        command_name = options['subcommand']
        self.subcommands.get(command_name)
        command_class = self.subcommands[command_name]

        if self.argv:
            args = [self.argv[0]] + self.argv[2:]
            return command_class().run_from_argv(args)
        else:
            return command_class().execute(*args, **options)


class BaseSchemaCommand(BaseCommand):
    """Sets the search path based on any "schema" option that's found"""

    def handle(self, *args, **options):
        databases = options.get("database", [])
        schemas = options.get("schema", [])

        if schemas:
            context = api.schema(*schemas, database=databases)
        else:
            context = contextlib.nullcontext()

        with context:
            return self.handle_with_schema(*args, **options)


class LsCommand(BaseSchemaCommand):
    help = 'List triggers and their installation state.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only list triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        uris = options['uris']

        def _get_colored_status(status, enabled):
            if enabled:
                enabled_display = '\t\033[92mENABLED\033[0m'
            else:
                enabled_display = '\t\033[91mDISABLED\033[0m'

            if status == core.UNINSTALLED:
                return '\033[91mUNINSTALLED\033[0m'
            elif status == core.INSTALLED:
                return f'\033[92mINSTALLED\033[0m{enabled_display}'
            elif status == core.OUTDATED:
                return f'\033[93mOUTDATED\033[0m{enabled_display}'
            elif status == core.PRUNE:
                return f'\033[96mPRUNE\033[0m{enabled_display}'
            else:
                raise AssertionError

        for model, trigger in api.get(*uris, database=options['database']):
            uri = trigger.get_uri(model)
            database = utils.database(model)
            status = trigger.get_installation_status(model)
            print(f'{uri}\t{database}\t{_get_colored_status(*status)}')

        if not uris:
            for trigger in api.prunable(database=options['database']):
                print(
                    f'{trigger[0]}:{trigger[1]}\t{trigger[3]}\t'
                    f'{_get_colored_status("PRUNE", trigger[2])}'
                )


class InstallCommand(BaseSchemaCommand):
    help = 'Install triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only install triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        api.install(*options['uris'], database=options['database'])


class UninstallCommand(BaseSchemaCommand):
    help = 'Uninstall triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only install triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        api.uninstall(*options['uris'], database=options['database'])


class EnableCommand(BaseSchemaCommand):
    help = 'Enable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only enable triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        api.enable(*options['uris'], database=options['database'])


class DisableCommand(BaseSchemaCommand):
    help = 'Disable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only enable triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        api.disable(*options['uris'], database=options['database'])


class PruneCommand(BaseSchemaCommand):
    help = 'Prune installed triggers that are no longer in the codebase.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--database',
            action='append',
            help='Only prune triggers for this database',
        )
        parser.add_argument(
            '-s',
            '--schema',
            action='append',
            help='Set the search path to this schema',
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        api.prune(database=options['database'])


class Command(SubCommands):
    help = 'Core django-pgtrigger subcommands.'

    subcommands = {
        'ls': LsCommand,
        'install': InstallCommand,
        'uninstall': UninstallCommand,
        'enable': EnableCommand,
        'disable': DisableCommand,
        'prune': PruneCommand,
    }
