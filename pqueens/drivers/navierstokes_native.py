import os
import pdb
from pqueens.drivers.driver import Driver
from pqueens.utils.injector import inject


class NavierStokesNative(Driver):
    """
    Driver to run the deal-II navierstokes code natively on workstation

    Args:
        output_navierstokes (str): Path to the output directory of the Navier Stokes solver

    Returns:
        NavierStokesNative_obj (obj): Instance of the NavierStokesNative class

    """

    def __init__(self, base_settings):
        super(NavierStokesNative, self).__init__(base_settings)
        self.output_navierstokes = None  # Will be assigned on runtime

    @classmethod
    def from_config_create_driver(cls, config, base_settings, workdir=None):
        """
        Create Driver from input file.

        Args:
            config (dict): Dictionary with problem description based on the json input file
            base_settings (dict): Dictionary with base settings of the parent class (depreciated:
                                  will be removed in the future)
            workdir (str): Path to the QUEENS working directory on the localhost

        Returns:
            NavierStokesNative_obj (obj): Instance of the NavierStokesNative class

        """
        base_settings['address'] = 'localhost:27017'
        return cls(base_settings)

    # ----------------- CHILD METHODS THAT NEED TO BE IMPLEMENTED -----------------
    def setup_dirs_and_files(self):
        """
        Setup directory structure

        Returns:
            None

        """
        # base directories
        dest_dir = os.path.join(self.experiment_dir, str(self.job_id))

        # Depending on the input file, directories will be created locally or on a cluster
        output_directory = os.path.join(dest_dir, 'output', 'vtu')
        self.output_navierstokes = os.path.join(dest_dir, 'output/')
        if not os.path.isdir(output_directory):
            os.makedirs(output_directory)

        # create input file name
        self.input_file = (
            dest_dir + '/' + str(self.experiment_name) + '_' + str(self.job_id) + '.json'
        )

        # create output file name
        self.output_file = (
            output_directory + '/' + str(self.experiment_name) + '_' + str(self.job_id)
        )

    def run_job(self):
        """
        Actual method to run the job on computing machine
        using run_subprocess method from base class

        Returns:
            None

        """
        # write output directory in input file (this is a special case
        # for the navierstokes solver)
        inject({"output_dir": self.output_navierstokes}, self.input_file, self.input_file)

        # assemble run command sttring
        command_string = self.assemble_command_string()

        # run BACI via subprocess
        stdout, stderr, self.pid = self.run_subprocess(command_string)

        # detection of failed jobs
        if stderr:
            self.result = None
            self.job['status'] = 'failed'

    def assemble_command_string(self):
        """  Assemble BACI run command list

            Returns:
                list: command list to execute BACI

        """
        # set MPI command
        mpi_command = 'mpirun -np'

        command_list = [
            mpi_command,
            str(self.num_procs),
            self.executable,
            self.input_file,
            self.output_file,
        ]

        return ' '.join(filter(None, command_list))
