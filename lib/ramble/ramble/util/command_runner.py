# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import time
from typing import Dict, List, Optional

from ramble.util.executable import which
from ramble.util.logger import logger

from spack.util.executable import CommandNotFoundError, Executable, ProcessError


class CommandRunner:
    """Runner for executing external commands

    This class provides a generic wrapper on external commands, to provide a
    unified way to handle dry-run execution of external commands.

    Can be inherited to construct custom command runners.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        command: Optional[str] = None,
        shell: str = "bash",
        dry_run: bool = False,
        path: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        Ensure required command is found in the path
        """
        self.name = name
        self.dry_run = dry_run
        self.shell = shell
        self.env = env
        self.elapsed_time: float = 0.0
        required = not self.dry_run
        if command is None:
            self.command = None
        else:
            search_path = path if path is not None else (env.get("PATH") if env else None)
            try:
                if search_path is not None:
                    self.command = which(command, required=required, path=search_path)
                else:
                    self.command = which(command, required=required)
            except CommandNotFoundError:
                raise RunnerError(f"Command {name} is not found in path") from None

    def get_version(self) -> str:
        """Hook to get the version of the executable

        Should return a string representation of the executable's version.
        """
        raise NotImplementedError

    def set_dry_run(self, dry_run: bool = False):
        """
        Set the dry_run state of this runner
        """
        self.dry_run = dry_run

    def execute(
        self,
        executable: Executable,
        args: List[str],
        allow_failure: bool = False,
        return_output: bool = False,
    ) -> Optional[str]:
        """Wrapper around execution of a command

        Handles execution of a command when the execution path is dependent on
        whether dry run is enabled or disabled.

        Args:
            executable (spack.util.executable.Executable): Executable to run with arguments
            args (list(str)): List of string arguments to pass into executable
            return_output (bool): Whether the output of the command should be returned or not
        """
        if not self.dry_run:
            return self._run_command(
                executable, args, allow_failure=allow_failure, return_output=return_output
            )
        else:
            return self._dry_run_print(executable, args)

    def _raise_validation_error(self, command: str, validation_type: str):
        """Wrapper to raise a validation error for this command"""
        raise ValidationFailedError(
            f'Validation of: "{self.name} {command}" failed '
            f' with a validation_type of "{validation_type}"'
        )

    def _dry_run_print(self, executable: Executable, args: List[str]):
        """Print the command that would be executed if dry-run was false.

        Args match the execute method.
        """
        logger.msg(f"DRY-RUN: would run {executable}")
        logger.msg(f"         with args: {args}")

    def _cmd_start(self, executable, args: List[str]):
        """Print a banner for the start of executing a command

        Args:
            executable (spack.util.executable.Executable): Executable that will be run
            args (list(str)): List of string arguments to pass into executable
        """
        start_str = f"********** Running {self.name} Command **********"
        banner = "*" * len(start_str)
        logger.msg("")
        logger.msg(banner)
        logger.msg(start_str)
        logger.msg(f"**     command: {executable}")
        if args:
            logger.msg(f"**     with args: {args}")
        logger.msg(banner)
        logger.msg("")

    def _cmd_end(self, executable: Executable, args: List[str]):
        """Print a banner for the start of executing a command

        Args:
            executable (spack.util.executable.Executable): Executable that will be run
            args (list(str)): List of string arguments to pass into executable
        """
        finished_str = f"***** Finished Running {self.name} Command ******"
        banner = "*" * len(finished_str)
        logger.msg("")
        logger.msg(banner)
        logger.msg(finished_str)
        logger.msg(f"** Took {self.elapsed_time} seconds")
        logger.msg(banner)
        logger.msg("")

    def _run_command(
        self,
        executable: Executable,
        args: List[str],
        allow_failure: bool = False,
        return_output: bool = False,
    ) -> Optional[str]:
        """Perform execution of executable with args, and optionally return the output

        Args:
            executable (spack.util.executable.Executable): Executable to run with arguments
            args (list(str)): List of string arguments to pass into executable
            allow_failure (bool): Whether a failure in the command should be tolerated
            return_output (bool): Whether the output of the command should be returned or not

        Returns:
            (str): Output of the invocation as a string, if return_output is True.
        """
        active_stream = logger.active_stream()
        active_log = logger.active_log()
        error = False

        self._cmd_start(executable, args)
        out_str = None
        start_time = time.time()
        try:
            if active_stream is None:
                if return_output:
                    out_str = executable(*args, output=str, env=self.env)
                else:
                    executable(*args, env=self.env)
            else:
                if return_output:
                    out_str = executable(*args, output=str, error=active_stream, env=self.env)
                else:
                    executable(*args, output=active_stream, error=active_stream, env=self.env)
        except ProcessError as e:
            if not allow_failure:
                logger.error(e)
                error = True
        self.elapsed_time = time.time() - start_time

        if error:
            err = f"Error running {self.name} command: {executable} " + " ".join(args)
            if active_stream is None:
                logger.die(err)
            else:
                logger.error(err)
                logger.die(f"For more details, see the log file: {active_log}")

        self._cmd_end(executable, args)

        if out_str is not None:
            return out_str
        return None


class RunnerError(Exception):
    """Raised when a problem occurs with a command runner"""


class NoPathRunnerError(RunnerError):
    """Raised when an executable is not found in the path"""


class ValidationFailedError(RunnerError):
    """Raised when a package manager requirement was not met"""
