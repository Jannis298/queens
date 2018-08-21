import os
import importlib.util
import numpy as np
from .interface import Interface


class DirectPythonInterface(Interface):
    """ Class for mapping input variables to responses using a python function

        The DirectPythonInterface class maps input variables to outputs,
        i.e. responses by making direct calls to a python function. The function
        has to be defined in a file, which is passed as an argument at runtime.
        The structure of the file must adhere to the structure of the files
        in the folder pqueens/example_input_files. In fact the purppose of
        this class is to be able to call the test examples in said folder.

    Attributes:
        name (string):                  name of interface
        variables (dict):               dictionary with variables
        function (function object):     adress of database to use

    """

    def __init__(self, interface_name, function_file, variables):
        """ Create interface

        Args:
            interface_name (string):    name of interface
            function_file (string):     function file name (including path)
                                        to be executed
            variables (dict):           dictionary with variables

        """

        self.name = interface_name
        self.variables = variables

        # get path to queens example simulator functions directory
        function_dir = os.path.join(os.path.dirname(__file__), '..', 'example_simulator_functions')
        abs_function_dir = os.path.abspath(function_dir)
        # join paths intelligently, i.e., if function_files contains an
        # absolute path it will preserved, otherwise the call belwo will prepend
        # the absolute path to the example_simalator_functions directory
        abs_function_file = os.path.join(abs_function_dir, function_file)

        try:
            spec = importlib.util.spec_from_file_location("my_function", abs_function_file)
            my_function = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(my_function)
        except FileNotFoundError:
            print('Did not find file locally, trying absolute path')
            raise FileNotFoundError("Could not import specified python function "
                                    "file! Fix your config file!")

        self.function = my_function



    @classmethod
    def from_config_create_interface(cls, interface_name, config):
        """ Create interface from config dictionary

        Args:
            interface_name (str):   name of interface
            config(dict):           dictionary containing problem description

        Returns:
            interface:              instance of DirectPythonInterface
        """
        interface_options = config[interface_name]

        function_file = interface_options["main_file"]
        parameters = config['parameters']

        # instanciate object
        return cls(interface_name, function_file, parameters)

    def map(self, samples):
        """ Mapping function which orchestrates call to simulator function

        Args:
            samples (list):         list of variables objects

        Returns:
            np.array,np.array       two arrays containing the inputs from the
                                    suggester, as well as the corresponding outputs
        """
        output = {}
        mean_values = []
        for variables in samples:
            params = variables.get_active_variables()
            mean_values.append(self.function.main(1, params))
        output['mean'] = np.reshape(np.array(mean_values), (-1, 1))
        return output
