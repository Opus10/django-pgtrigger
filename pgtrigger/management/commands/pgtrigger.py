import logging

from django.core.management.base import BaseCommand

from pgtrigger import core


def _setup_logging():
    core.LOGGER.addHandler(logging.StreamHandler())
    core.LOGGER.setLevel(logging.INFO)


class SubCommands(BaseCommand):  # pragma: no cover
    """
    Subcommand class vendored in from
    https://github.com/andrewp-as-is/django-subcommands.py
    because of installation issues
    """

    argv = []
    subcommands = {}

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest='subcommand', title='subcommands', description=''
        )
        subparsers.required = True

        for command_name, command_class in self.subcommands.items():
            command = command_class()

            subparser = subparsers.add_parser(
                command_name, help=command_class.help
            )
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


class LsCommand(BaseCommand):
    help = 'List triggers and their installation state.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database', help='Only list triggers for this database',
        )

    def handle(self, *args, **options):
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

        for model, trigger in core.get(*uris, database=options['database']):
            uri = trigger.get_uri(model)
            database = core._get_database(model)
            status = trigger.get_installation_status(model)
            print(f'{uri}\t{database}\t{_get_colored_status(*status)}')

        if not uris:
            for trigger in core.get_prune_list(database=options['database']):
                print(
                    f'{trigger[0]}:{trigger[1]}\t{trigger[3]}\t'
                    f'{_get_colored_status("PRUNE", trigger[2])}'
                )


class InstallCommand(BaseCommand):
    help = 'Install triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database', help='Only install triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        core.install(*options['uris'], database=options['database'])


class UninstallCommand(BaseCommand):
    help = 'Uninstall triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database', help='Only install triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        core.uninstall(*options['uris'], database=options['database'])


class EnableCommand(BaseCommand):
    help = 'Enable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database', help='Only enable triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        core.enable(*options['uris'], database=options['database'])


class DisableCommand(BaseCommand):
    help = 'Disable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database', help='Only enable triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        core.disable(*options['uris'], database=options['database'])


class PruneCommand(BaseCommand):
    help = 'Prune installed triggers that are no longer in the codebase.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database', help='Only prune triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        core.prune(database=options['database'])


class Command(SubCommands):
    help = """
     pgtrigger must be followed by a subcommand:\n
     - 'ls': List the project triggers and their installation state\n
    """
    subcommands = {
        'ls': LsCommand,
        'install': InstallCommand,
        'uninstall': UninstallCommand,
        'enable': EnableCommand,
        'disable': DisableCommand,
        'prune': PruneCommand,
    }
