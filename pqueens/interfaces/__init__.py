# -*- coding: utf-8 -*-
"""Interfaces.

This package contains a set of so-called interfaces. The purpose of an interface
is essentially the mapping of inputs to outputs. For now there are four kinds
of interface plus the base class.

The mapping is can made by passing the inputs further down to a
regression_approximation or a mf_regression_approximation, both of which
essentially then evaluate a regression model themselves.

The alternatives are the evaluation of simple python function using the
direct_python_interface or running an external software through the job_interface.
"""
from pqueens.utils.import_utils import get_module_class

valid_types = {
    'job_interface': ['pqueens.interfaces.job_interface', 'JobInterface'],
    'direct_python_interface': [
        'pqueens.interfaces.direct_python_interface',
        'DirectPythonInterface',
    ],
    'approximation_interface': [
        'pqueens.interfaces.approximation_interface',
        'ApproximationInterface',
    ],
    'approximation_interface_mf': [
        'pqueens.interfaces.approximation_interface_mf',
        'ApproximationInterfaceMF',
    ],
}


def from_config_create_interface(interface_name, config):
    """Create Interface from config dictionary.

    Args:
        interface_name (str):   name of the interface
        config (dict):          dictionary with problem description

    Returns:
        interface:              Instance of one of the derived interface classes
    """
    interface_options = config[interface_name]
    interface_type = interface_options.get("type")
    interface_class = get_module_class(interface_options, valid_types, interface_type)
    interface = interface_class.from_config_create_interface(interface_name, config)
    return interface
