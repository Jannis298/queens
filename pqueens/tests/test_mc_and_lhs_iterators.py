'''
Created on November 23th  2017
@author: jbi

'''
import unittest
import numpy as np
from pqueens.interfaces.direct_python_interface import DirectPythonInterface
from pqueens.models.simulation_model import SimulationModel
from pqueens.variables.variables import Variables
from pqueens.iterators.monte_carlo_iterator import MonteCarloIterator
from pqueens.iterators.lhs_iterator import LHSIterator


class TestLHSIterator(unittest.TestCase):
    """ Test LHS Iterator """
    def setUp(self):
        uncertain_parameters = {}
        uncertain_parameter1 = {}
        uncertain_parameter1["type"] = "FLOAT"
        uncertain_parameter1["size"] = 1
        uncertain_parameter1["distribution"] = "uniform"
        uncertain_parameter1["distribution_parameter"] = [-3.14159265359, 3.14159265359]

        uncertain_parameter2 = {}
        uncertain_parameter2["type"] = "FLOAT"
        uncertain_parameter2["size"] = 1
        uncertain_parameter2["distribution"] = "normal"
        uncertain_parameter2["distribution_parameter"] = [0, 2]

        uncertain_parameter3 = {}
        uncertain_parameter3["type"] = "FLOAT"
        uncertain_parameter3["size"] = 1
        uncertain_parameter3["distribution"] = "lognormal"
        uncertain_parameter3["distribution_parameter"] = [0.3, 1]

        uncertain_parameters['x1'] = uncertain_parameter1
        uncertain_parameters['x2'] = uncertain_parameter2
        uncertain_parameters['x3'] = uncertain_parameter3

        self.variables = Variables.from_uncertain_parameters_create(uncertain_parameters)

        # create interface
        self.interface = DirectPythonInterface('test_interface',
                                               'pqueens/example_simulator_functions/ishigami.py',
                                               self.variables)

        # create mock model
        self.model = SimulationModel("my_model", self.interface, uncertain_parameters)

        # create LHS iterator
        self.my_iterator = LHSIterator(self.model, seed=42, num_samples=100, num_iterations=1)

    def test_correct_sampling(self):
        """ Test if we get correct samples"""

        #np.set_printoptions(precision=10)
        #print("Samples first row {}".format(self.my_iterator.samples[0,:]))
        #print("Sample mean {}".format(my_means))
        #print("Sample std {}".format(my_std))
        self.my_iterator.pre_run()

        # check if mean and std match
        means_ref = np.array([-1.4546056001e-03, 5.4735307403e-03, 2.1664850171e+00])

        np.testing.assert_allclose(np.mean(self.my_iterator.samples, axis=0),
                                   means_ref, 1e-09, 1e-09)

        std_ref = np.array([1.8157451781, 1.9914892803, 2.4282341125])
        np.testing.assert_allclose(np.std(self.my_iterator.samples, axis=0),
                                   std_ref, 1e-09, 1e-09)


        # check if samples are identical too
        ref_sample_first_row = np.array([-2.7374616292, -0.6146554017, 1.3925529817])

        np.testing.assert_allclose(self.my_iterator.samples[0, :],
                                   ref_sample_first_row, 1e-07, 1e-07)


    def test_correct_results(self):
        """ Test if we get correct results"""
        self.my_iterator.pre_run()
        self.my_iterator.core_run()

        #np.set_printoptions(precision=10)
        #print("Results first 10 {}".format(self.my_iterator.outputs[0:10]))

        # check if samples are identical too
        ref_results = np.array([[1.7868040337],
                                [-13.8624183835],
                                [6.3423271929],
                                [6.1674472752],
                                [5.3528917433],
                                [-0.7472766806],
                                [5.0007066283],
                                [6.4763926539],
                                [-6.4173504897],
                                [3.1739282221]])

        np.testing.assert_allclose(self.my_iterator.outputs[0:10],
                                   ref_results, 1e-09, 1e-09)

class TestMCIterator(unittest.TestCase):
    def setUp(self):
        uncertain_parameters = {}
        uncertain_parameter1 = {}
        uncertain_parameter1["type"] = "FLOAT"
        uncertain_parameter1["size"] = 1
        uncertain_parameter1["distribution"] = "uniform"
        uncertain_parameter1["distribution_parameter"] = [-3.14159265359, 3.14159265359]

        uncertain_parameter2 = {}
        uncertain_parameter2["type"] = "FLOAT"
        uncertain_parameter2["size"] = 1
        uncertain_parameter2["distribution"] = "normal"
        uncertain_parameter2["distribution_parameter"] = [0, 2]

        uncertain_parameter3 = {}
        uncertain_parameter3["type"] = "FLOAT"
        uncertain_parameter3["size"] = 1
        uncertain_parameter3["distribution"] = "lognormal"
        uncertain_parameter3["distribution_parameter"] = [0.3, 1]

        uncertain_parameters['x1'] = uncertain_parameter1
        uncertain_parameters['x2'] = uncertain_parameter2
        uncertain_parameters['x3'] = uncertain_parameter3

        self.variables = Variables.from_uncertain_parameters_create(uncertain_parameters)

        # create interface
        self.interface = DirectPythonInterface('test_interface',
                                               'pqueens/example_simulator_functions/ishigami.py',
                                               self.variables)

        # create mock model
        self.model = SimulationModel("my_model", self.interface, uncertain_parameters)

        # create LHS iterator
        self.my_iterator = MonteCarloIterator(self.model, seed=42, num_samples=100)

    def test_correct_sampling(self):
        """ Test if we get correct samples"""

        self.my_iterator.pre_run()

        #np.set_printoptions(precision=10)
        #print("Samples first row {}".format(self.my_iterator.samples[0,:]))
        #print("Sample mean {}".format(np.mean(self.my_iterator.samples,axis=0)))
        #print("Sample std {}".format(np.std(self.my_iterator.samples,axis=0)))

        # check if mean and std match
        means_ref = np.array([-1.8735991508e-01, -2.1607203347e-03, 2.8955130234e+00])

        np.testing.assert_allclose(np.mean(self.my_iterator.samples, axis=0),
                                   means_ref, 1e-09, 1e-09)

        std_ref = np.array([1.8598117085, 1.8167064845, 6.7786919771])
        np.testing.assert_allclose(np.std(self.my_iterator.samples, axis=0),
                                   std_ref, 1e-09, 1e-09)


        # check if samples are identical too
        ref_sample_first_row = np.array([-0.7882876819, 0.1740941365, 1.3675241182])

        np.testing.assert_allclose(self.my_iterator.samples[0, :],
                                   ref_sample_first_row, 1e-07, 1e-07)


    def test_correct_results(self):
        """ Test if we get correct results"""
        self.my_iterator.pre_run()
        self.my_iterator.core_run()

        #np.set_printoptions(precision=10)
        #print("Results first 10 {}".format(self.my_iterator.outputs[0:10]))

        # check if samples are identical too
        ref_results = np.array([[-7.4713449052e-01],
                                [3.6418728120e+01],
                                [1.3411821745e+00],
                                [1.0254005782e+04],
                                [-2.9330095397e+00],
                                [2.1639496168e+00],
                                [-1.1964201899e-01],
                                [7.6345947125e+00],
                                [7.6591139616e+00],
                                [1.1519434320e+01]])

        np.testing.assert_allclose(self.my_iterator.outputs[0:10],
                                   ref_results, 1e-09, 1e-09)
