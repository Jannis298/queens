"""Singularity management utilities."""
import logging
import os
import random
import subprocess
import time
from pathlib import Path

from pqueens.utils.config_directories import ABS_SINGULARITY_IMAGE_PATH
from pqueens.utils.exceptions import SingularityError
from pqueens.utils.path_utils import PATH_TO_QUEENS, relative_path_from_pqueens
from pqueens.utils.run_subprocess import SubprocessError, run_subprocess
from pqueens.utils.user_input import request_user_input_with_default_and_timeout

_logger = logging.getLogger(__name__)


def create_singularity_image():
    """Create pre-designed singularity image for cluster applications."""
    # create the actual image
    command_string = 'singularity --version'
    run_subprocess(command_string, additional_error_message='Singularity could not be executed!')

    definition_path = 'singularity/singularity_recipe.def'
    abs_definition_path = relative_path_from_pqueens(definition_path)
    command_list = [
        f"cd {PATH_TO_QUEENS}",
        "&& unset SINGULARITY_BIND &&",
        f"singularity build --force --fakeroot {ABS_SINGULARITY_IMAGE_PATH}",
        str(abs_definition_path),
    ]
    command_string = ' '.join(command_list)

    # Singularity logs to the wrong stream depending on the OS.
    try:
        run_subprocess(
            command_string, additional_error_message='Build of local singularity image failed!'
        )
    except SubprocessError as sp_error:
        # Check if build was successful
        if str(sp_error).find("INFO:    Build complete:") < 0 or str(sp_error).find("FATAL:") >= 0:
            raise SingularityError("Could not build singularity") from sp_error

    if not ABS_SINGULARITY_IMAGE_PATH.is_file():
        raise FileNotFoundError(f'No singularity image "{ABS_SINGULARITY_IMAGE_PATH}" found')


class SingularityManager:
    """Singularity management class.

    Attributes:
        remote (bool): *True* if the simulation runs are remote.
        remote_connect (str): String of user@remote_machine .
        singularity_bind (str): Binds for the singularity runs.
        singularity_path (Path): Path to singularity exec.
        input_file (Path): Path to QUEENS input file.
    """

    def __init__(
        self, singularity_path, singularity_bind, input_file, remote=False, remote_connect=None
    ):
        """Init method for the singularity object.

        Args:
            remote (bool): True if the simulation runs are remote
            remote_connect (str): String of user@remote_machine
            singularity_bind (str): Binds for the singularity runs
            singularity_path (path): Path to singularity exec
            input_file (path): Path to QUEENS input file
        """
        self.remote = remote
        self.remote_connect = remote_connect
        self.singularity_bind = singularity_bind
        self.singularity_path = singularity_path
        self.input_file = input_file

        if self.remote and self.remote_connect is None:
            raise ValueError(
                "Remote singularity option is set to true but no remote connect is supplied."
            )

    def sync_remote_image(self):
        """Sync image on remote resource with local singularity."""
        _logger.info("Syncing remote image with local image...")
        _logger.info("(This takes a couple of seconds)")
        command_list = [
            f"rsync --archive --checksum --verbose --verbose {ABS_SINGULARITY_IMAGE_PATH}",
            self.remote_connect + ':' + str(self.singularity_path / 'singularity_image.sif'),
        ]
        command_string = ' '.join(command_list)
        _, _, stdout, _ = run_subprocess(
            command_string,
            additional_error_message="Was not able to sync local singularity image to remote! ",
        )
        _logger.debug(stdout)
        _logger.info("Sync of remote image was successful.\n")

    def prepare_singularity_files(self):
        """Prepare local and remote singularity images.

        Make sure that an up-to-date singularity image is available
        where it is needed, locally and remotely. If no image exists or
        the existing image is outdated, a new image is built. The local
        image is synced with the remote machine to ensure that the image
        on the remote machine is up-to-date.
        """
        if new_singularity_image_needed():
            _logger.info(
                "Local singularity image is not up-to-date with QUEENS! "
                "Building new local image..."
            )
            _logger.info("(This takes a couple of minutes.)")
            create_singularity_image()
            _logger.info("Local singularity image built successfully!\n")

        else:
            _logger.info("Found an up-to-date local singularity image.\n")

        if self.remote:
            self.sync_remote_image()

    def kill_previous_queens_ssh_remote(self, username):
        """Kill existing ssh-port-forwardings on the remote machine.

        These were caused by previous QUEENS simulations that either crashed or are still in place
        due to other reasons. This method will avoid that a user opens too many unnecessary ports
        on the remote and blocks them for other users.

        Args:
            username (string): Username of person logged in on remote machine
        """
        # find active queens ssh ports on remote
        command_list = [
            'ssh',
            self.remote_connect,
            '\'ps -aux | grep ssh | grep',
            username.rstrip(),
            '| grep :localhost:27017\'',
        ]

        command_string = ' '.join(command_list)
        _, _, active_ssh, _ = run_subprocess(command_string)

        # skip entries that contain "grep" as this is the current command
        try:
            active_ssh = [line for line in active_ssh.splitlines() if not 'grep' in line]
        except IndexError:
            pass

        if active_ssh:
            # _logger.info the queens related open ports
            _logger.info('The following QUEENS sessions are still occupying ports on the remote:')
            _logger.info('----------------------------------------------------------------------')
            for line in active_ssh:
                _logger.info(line)
            _logger.info('----------------------------------------------------------------------')
            _logger.info('')
            _logger.info('Do you want to close these connections (recommended)?')
            while True:
                try:
                    _logger.info('Please type "y" or "n" >> ')
                    answer = request_user_input_with_default_and_timeout(default="n", timeout=10)
                except SyntaxError:
                    answer = None

                if answer.lower() == 'y':
                    ssh_ids = [line.split()[1] for line in active_ssh]
                    for ssh_id in ssh_ids:
                        command_list = ['ssh', self.remote_connect, '\'kill -9', ssh_id + '\'']
                        command_string = ' '.join(command_list)
                        run_subprocess(command_string)
                    _logger.info('Old QUEENS port-forwardings were successfully terminated!')
                    break

                if answer.lower() == 'n':
                    break
                if answer is None:
                    _logger.info(
                        'You gave an empty input! Only "y" or "n" are valid inputs! Try again!'
                    )
                else:
                    _logger.info(
                        'The input %s is not an appropriate choice! '
                        'Only "y" or "n" are valid inputs!',
                        answer,
                    )
                    _logger.info('Try again!')
        else:
            pass

    def establish_port_forwarding_remote(self, address_localhost):
        """Automated port-forwarding from localhost to remote machine.

        Forward data to the database on localhost's port 27017 and a designated
        port on the master node of the remote machine.

        Args:
            address_localhost (str): IP-address of localhost

        Returns:
            TODO_doc
        """
        _logger.info('Establish remote port-forwarding')
        port_fail = 1
        max_attempts = 100
        attempts = 1
        while port_fail != "" and attempts < max_attempts:
            port = random.randrange(2030, 20000, 1)
            command_list = [
                'ssh',
                '-t',
                '-t',
                self.remote_connect,
                '\'ssh',
                '-fN',
                '-g',
                '-L',
                str(port) + r':' + 'localhost' + r':27017',
                address_localhost + '\'',
            ]
            command_string = ' '.join(command_list)
            port_fail = os.popen(command_string).read()
            _logger.info('attempt #%d: %s', attempts, command_string)
            _logger.debug('which returned: %s', port_fail)
            time.sleep(0.1)
            attempts += 1

        _logger.info('Remote port-forwarding established successfully for port %s', port)

        return port

    def establish_port_forwarding_local(self, address_localhost):
        """Establish port-forwarding from local to remote.

        Establish a port-forwarding for localhost's port 9001 to the
        remote's ssh-port 22 for passwordless communication with the remote
        machine over ssh.

        Args:
            address_localhost (str): IP-address of the localhost
        """
        remote_address = self.remote_connect.split(r'@')[1]
        command_list = [
            'ssh',
            '-f',
            '-N',
            '-L',
            r'9001:' + remote_address + r':22',
            address_localhost,
        ]
        with subprocess.Popen(
            command_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as ssh_proc:
            stat = ssh_proc.poll()
            while stat is None:
                stat = ssh_proc.poll()
            # Think of some kind of error catching here;
            # so far it works but error might be cryptical

    def close_local_port_forwarding(self):
        """Closes port forwarding from local to remote machine."""
        _, _, username, _ = run_subprocess('whoami')
        command_string = "ps -aux | grep 'ssh -f -N -L 9001:' | grep ':22 " + username + "@'"
        _, _, active_ssh, _ = run_subprocess(
            command_string, raise_error_on_subprocess_failure=False
        )

        if active_ssh:
            active_ssh_ids = []
            try:
                active_ssh_ids = [
                    line.split()[1] for line in active_ssh.splitlines() if not 'grep' in line
                ]
            except IndexError:
                pass

            if active_ssh_ids:
                for ssh_id in active_ssh_ids:
                    command_string = 'kill -9 ' + ssh_id
                    run_subprocess(command_string, raise_error_on_subprocess_failure=False)
                _logger.info(
                    'Active QUEENS local to remote port-forwardings were closed successfully!'
                )

    def close_remote_port(self, port):
        """Closes the ports used in the current QUEENS simulation.

        Args:
            port (int): Random port selected previously
        """
        # get the process id of open port
        _, _, username, _ = run_subprocess('whoami')
        command_list = [
            'ssh',
            self.remote_connect,
            '\'ps -aux | grep ssh | grep',
            username.rstrip(),
            '| grep',
            str(port) + ':localhost:27017\'',
        ]
        command_string = ' '.join(command_list)
        _, _, active_ssh, _ = run_subprocess(
            command_string, raise_error_on_subprocess_failure=False
        )

        # skip entries that contain "grep" as this is the current command
        try:
            active_ssh_ids = [
                line.split()[1] for line in active_ssh.splitlines() if not 'grep' in line
            ]
        except IndexError:
            pass

        if active_ssh_ids != '':
            for ssh_id in active_ssh_ids:
                command_list = ['ssh', self.remote_connect, '\'kill -9', ssh_id + '\'']
                command_string = ' '.join(command_list)
                run_subprocess(command_string)
            _logger.info('Active QUEENS remote to local port-forwardings were closed successfully!')


def new_singularity_image_needed():
    """Indicate if a new singularity image needs to be build.

    Before checking if the files changed, a check is performed to see if there is an image first.

    Returns:
        (bool): True if new image is needed.
    """
    if ABS_SINGULARITY_IMAGE_PATH.exists():
        return _files_changed()
    return True


def _files_changed():
    """Indicates if the source files deviate w.r.t. to singularity container.

    Returns:
        [bool]: if files have changed
    """
    # Folders included in the singularity image relevant for a run
    folders_to_compare_list = [
        'drivers/',
        'data_processor/',
        'utils/',
        'external_geometry/',
        'randomfields/',
        'singularity/',
    ]

    # Specific files in the singularity image relevant for a run
    files_to_compare_list = [
        'database/mongodb.py',
        'schedulers/cluster_scheduler.py',
    ]
    # generate absolute paths
    files_to_compare_list = [relative_path_from_pqueens(file) for file in files_to_compare_list]
    folders_to_compare_list = [relative_path_from_pqueens(file) for file in folders_to_compare_list]

    # Add files from the relevant folders to the list of files
    for folder in folders_to_compare_list:
        files_to_compare_list.extend(_get_python_files_in_folder(folder))

    files_changed = False
    for file in files_to_compare_list:
        # File path inside the container
        file = str(file)
        filepath_in_singularity = '/queens/pqueens/' + file.rsplit("pqueens/", maxsplit=1)[-1]

        # Compare the queens source files with the ones inside the container
        command_string = (
            f"singularity exec {ABS_SINGULARITY_IMAGE_PATH} "
            + f"cmp {file} {filepath_in_singularity}"
        )
        _, _, stdout, stderr = run_subprocess(
            command_string, raise_error_on_subprocess_failure=False
        )

        # If file is different or missing stop iteration and build the image
        if stdout or stderr:
            files_changed = True
            break
    return files_changed


def _get_python_files_in_folder(relative_path):
    """Get list of absolute paths of files in folder.

    Only python files are included.

    Args:
        relative_path (str): Relative path to folder from pqueens.

    Returns:
        file_paths: List of the absolute paths of the python files within the folder.
    """
    abs_path = Path(relative_path_from_pqueens(relative_path))
    file_paths = list(abs_path.glob("*.py"))
    file_paths.sort()
    return file_paths


def sha1sum(file_path, remote_connect=None):
    """Hash files using *sha1sum*.

    *sha1sum* is a computer program that calculates hashes and is the default on most Linux
    distributions. If it is not available on your OS under the same name, you can still create a
    symlink.

    Args:
        file_path (str): Absolute path to the file to hash
        remote_connect (str, optional): username@machine in case of remote machines

    Returns:
        str: The hash of the file
    """
    command_string = f"sha1sum {file_path}"
    if remote_connect:
        command_string = f"ssh {remote_connect} && " + command_string
    _, _, output, _ = run_subprocess(
        command_string,
        additional_error_message="Was not able to hash the file",
    )
    return output.split(" ")[0]
