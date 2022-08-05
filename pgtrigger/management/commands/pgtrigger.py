import logging

import django
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management.commands import makemigrations
from django.db.migrations import Migration
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import AddConstraint, RemoveConstraint
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState

import pgtrigger
import pgtrigger.core
import pgtrigger.migrations


def _setup_logging():
    pgtrigger.core.LOGGER.addHandler(logging.StreamHandler())
    pgtrigger.core.LOGGER.setLevel(logging.INFO)


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


class LsCommand(BaseCommand):
    help = 'List triggers and their installation state.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database',
            help='Only list triggers for this database',
        )

    def handle(self, *args, **options):
        uris = options['uris']

        def _get_colored_status(status, enabled):
            if enabled:
                enabled_display = '\t\033[92mENABLED\033[0m'
            else:
                enabled_display = '\t\033[91mDISABLED\033[0m'

            if status == pgtrigger.core.UNINSTALLED:
                return '\033[91mUNINSTALLED\033[0m'
            elif status == pgtrigger.core.INSTALLED:
                return f'\033[92mINSTALLED\033[0m{enabled_display}'
            elif status == pgtrigger.core.OUTDATED:
                return f'\033[93mOUTDATED\033[0m{enabled_display}'
            elif status == pgtrigger.core.PRUNE:
                return f'\033[96mPRUNE\033[0m{enabled_display}'
            else:
                raise AssertionError

        for model, trigger in pgtrigger.core.get(*uris, database=options['database']):
            uri = trigger.get_uri(model)
            database = pgtrigger.core._get_database(model)
            status = trigger.get_installation_status(model)
            print(f'{uri}\t{database}\t{_get_colored_status(*status)}')

        if not uris:
            for trigger in pgtrigger.core.get_prune_list(database=options['database']):
                print(
                    f'{trigger[0]}:{trigger[1]}\t{trigger[3]}\t'
                    f'{_get_colored_status("PRUNE", trigger[2])}'
                )


class InstallCommand(BaseCommand):
    help = 'Install triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database',
            help='Only install triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        pgtrigger.core.install(*options['uris'], database=options['database'])


class UninstallCommand(BaseCommand):
    help = 'Uninstall triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database',
            help='Only install triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        pgtrigger.core.uninstall(*options['uris'], database=options['database'])


class EnableCommand(BaseCommand):
    help = 'Enable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database',
            help='Only enable triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        pgtrigger.core.enable(*options['uris'], database=options['database'])


class DisableCommand(BaseCommand):
    help = 'Disable triggers.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', type=str)
        parser.add_argument(
            '--database',
            help='Only enable triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        pgtrigger.core.disable(*options['uris'], database=options['database'])


class PruneCommand(BaseCommand):
    help = 'Prune installed triggers that are no longer in the codebase.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            help='Only prune triggers for this database',
        )

    def handle(self, *args, **options):
        _setup_logging()
        pgtrigger.core.prune(database=options['database'])


def _convert_pgtrigger_operation(operation, app_label):
    """
    Given a normal migration constraint operation, convert it
    to a pgtrigger constraint migration.
    """
    if isinstance(operation, AddConstraint):
        return pgtrigger.migrations.AddConstraint(
            model_name=operation.model_name, constraint=operation.constraint, app_label=app_label
        )
    elif isinstance(operation, RemoveConstraint):
        return pgtrigger.migrations.RemoveConstraint(
            model_name=operation.model_name, name=operation.name, app_label=app_label
        )
    else:
        raise AssertionError


def _is_pgtrigger_operation(operation, source_app_label, from_state):
    """
    Given a migration operation, return True if it is
    an operation for pgtrigger
    """
    # This function assumes we are migrating third party models that already exist.
    model = from_state.models[(source_app_label, operation.model_name)]
    constraint_names = [constraint.name for constraint in model.options.get("constraints", [])]

    if (
        isinstance(operation, AddConstraint)
        and isinstance(operation.constraint, pgtrigger.Trigger)
    ) or (isinstance(operation, RemoveConstraint) and operation.name in constraint_names):
        return True

    # In practice, all operations of third party models are going to be pgtrigger additions
    # unless another app does this or the author forgot to add migrations. This case shouldn't
    # happen much in practice
    return False  # pragma: no cover


class MakeMigrationsCommand(makemigrations.Command):
    help = 'Make trigger migrations for a third-party app.'

    def add_arguments(self, parser):
        parser.add_argument('source_app_label', type=str)
        parser.add_argument('dest_app_label', type=str)
        parser.add_argument(
            "-n",
            "--name",
            help="Use this name for migration file(s).",
        )
        parser.add_argument(
            "--no-header",
            action="store_false",
            dest="include_header",
            help="Do not add header comments to new migration file(s).",
        )

        if django.VERSION >= (4, 2):  # pragma: no cover
            parser.add_argument(
                "--update",
                action="store_true",
                dest="update",
                help=(
                    "Merge model changes into the latest migration and optimize the "
                    "resulting operations."
                ),
            )

    def handle(self, *args, **options):
        self.written_files = []
        self.verbosity = options["verbosity"]
        self.migration_name = options["name"]
        self.include_header = options["include_header"]
        self.update = options["update"] if django.VERSION >= (4, 2) else False
        self.dry_run = False
        self.scriptable = False

        source_app_label = options["source_app_label"]
        dest_app_label = options["dest_app_label"]

        loader = MigrationLoader(None, ignore_no_migrations=True)
        from_state = loader.project_state()
        questioner = NonInteractiveMigrationQuestioner()
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )

        # Detect changes
        from_changes = autodetector.changes(
            graph=loader.graph,
            trim_to_apps=[source_app_label],
            convert_apps=[source_app_label],
            migration_name=self.migration_name,
        )
        if source_app_label in from_changes:
            to_migration = Migration("custom", dest_app_label)
            to_migration.dependencies += [
                dependency
                for migration in from_changes[source_app_label]
                for dependency in migration.dependencies
            ]
            to_migration.operations = [
                _convert_pgtrigger_operation(operation, source_app_label)
                for migration in from_changes[source_app_label]
                for operation in migration.operations
                if _is_pgtrigger_operation(operation, source_app_label, from_state)
            ]
            changes = autodetector.arrange_for_graph(
                changes={dest_app_label: [to_migration]},
                graph=loader.graph,
                migration_name=self.migration_name,
            )

            if self.update:  # pragma: no cover
                self.write_to_last_migration_files(changes)
            else:
                self.write_migration_files(changes)
        else:
            if self.verbosity >= 1:  # pragma: no branch
                self.stdout.write(f"No changes detected in app '{source_app_label}'")


class Command(SubCommands):
    help = 'Core django-pgtrigger subcommands.'

    subcommands = {
        'ls': LsCommand,
        'install': InstallCommand,
        'uninstall': UninstallCommand,
        'enable': EnableCommand,
        'disable': DisableCommand,
        'prune': PruneCommand,
        'makemigrations': MakeMigrationsCommand,
    }
