import contextlib
import logging

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS

from pgtrigger import core, installation, registry, runtime


def _setup_logging():  # pragma: no cover
    installation.LOGGER.addHandler(logging.StreamHandler())
    installation.LOGGER.setLevel(logging.INFO)


class SubCommands(BaseCommand):  # pragma: no cover
    """
    Subcommand class vendored in from
    https://github.com/andrewp-as-is/django-subcommands.py
    because of installation issues
    """

    argv = []
    subcommands = {}

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", title="subcommands", description="")
        subparsers.required = True

        for command_name, command_class in self.subcommands.items():
            command = command_class()

            subparser = subparsers.add_parser(command_name, help=command_class.help)
            command.add_arguments(subparser)
            prog_name = subcommand = ""
            if self.argv:
                prog_name = self.argv[0]
                subcommand = self.argv[1]

            command_parser = command.create_parser(prog_name, subcommand)
            subparser._actions = command_parser._actions

    def run_from_argv(self, argv):
        self.argv = argv
        return super().run_from_argv(argv)

    def handle(self, *args, **options):
        command_name = options["subcommand"]
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
        database = options["database"] or DEFAULT_DB_ALIAS
        schemas = options["schema"] or []

        if schemas:
            context = runtime.schema(*schemas, databases=[database])
        else:
            context = contextlib.nullcontext()

        with context:
            return self.handle_with_schema(*args, **options)


class LsCommand(BaseSchemaCommand):
    help = "List triggers and their installation state."

    def add_arguments(self, parser):
        parser.add_argument("uris", nargs="*", type=str)
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        uris = options["uris"]

        status_formatted = {
            core.UNINSTALLED: "\033[91mUNINSTALLED\033[0m",
            core.INSTALLED: "\033[92mINSTALLED\033[0m",
            core.OUTDATED: "\033[93mOUTDATED\033[0m",
            core.PRUNE: "\033[96mPRUNE\033[0m",
            core.UNALLOWED: "\033[94mUNALLOWED\033[0m",
        }

        enabled_formatted = {
            True: "\033[92mENABLED\033[0m",
            False: "\033[91mDISABLED\033[0m",
            None: "\033[94mN/A\033[0m",
        }

        def _format_status(status, enabled, uri):
            if status in (core.UNINSTALLED, core.UNALLOWED):
                enabled = None

            return status_formatted[status], enabled_formatted[enabled], uri

        formatted = []

        for model, trigger in registry.registered(*uris):
            uri = trigger.get_uri(model)
            status, enabled = trigger.get_installation_status(model, database=options["database"])
            formatted.append(_format_status(status, enabled, uri))

        if not uris:
            for trigger in installation.prunable(database=options["database"]):
                formatted.append(_format_status("PRUNE", trigger[2], f"{trigger[0]}:{trigger[1]}"))

        max_status_len = max(len(val) for val, _, _ in formatted)
        max_enabled_len = max(len(val) for _, val, _ in formatted)
        for status, enabled, uri in formatted:
            print(
                f"{{: <{max_status_len}}} {{: <{max_enabled_len}}} {{}}".format(
                    status, enabled, uri
                )
            )


class InstallCommand(BaseSchemaCommand):
    help = "Install triggers."

    def add_arguments(self, parser):
        parser.add_argument("uris", nargs="*", type=str)
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        installation.install(*options["uris"], database=options["database"])


class UninstallCommand(BaseSchemaCommand):
    help = "Uninstall triggers."

    def add_arguments(self, parser):
        parser.add_argument("uris", nargs="*", type=str)
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        installation.uninstall(*options["uris"], database=options["database"])


class EnableCommand(BaseSchemaCommand):
    help = "Enable triggers."

    def add_arguments(self, parser):
        parser.add_argument("uris", nargs="*", type=str)
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        installation.enable(*options["uris"], database=options["database"])


class DisableCommand(BaseSchemaCommand):
    help = "Disable triggers."

    def add_arguments(self, parser):
        parser.add_argument("uris", nargs="*", type=str)
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        installation.disable(*options["uris"], database=options["database"])


class PruneCommand(BaseSchemaCommand):
    help = "Prune installed triggers that are no longer in the codebase."

    def add_arguments(self, parser):
        parser.add_argument("-d", "--database", help="The database")
        parser.add_argument(
            "-s",
            "--schema",
            action="append",
            help="Set the search path to this schema",
        )

    def handle_with_schema(self, *args, **options):
        _setup_logging()
        installation.prune(database=options["database"])


class Command(SubCommands):
    help = "Core django-pgtrigger subcommands."

    subcommands = {
        "ls": LsCommand,
        "install": InstallCommand,
        "uninstall": UninstallCommand,
        "enable": EnableCommand,
        "disable": DisableCommand,
        "prune": PruneCommand,
    }
