import logging

import numpy as np
import pqueens.database.database as DB_module
from pqueens.external_geometry.external_geometry import ExternalGeometry
from pqueens.iterators.iterator import Iterator
from pqueens.iterators.monte_carlo_iterator import MonteCarloIterator
from pqueens.models.model import Model
from pqueens.utils.process_outputs import process_ouputs, write_results

from sklearn.preprocessing import StandardScaler

_logger = logging.getLogger(__name__)


class BMFIAIterator(Iterator):
    """
    Iterator for Bayesian multi-fidelity inverse analysis. Here, we build the multi-fidelity
    probabilistic surrogate, determine optimal training points X_train and evaluate the low- and
    high-fidelity model for these training inputs to yield Y_LF_train and Y_HF_train.
    training data. The actual inverse problem is not solved or iterated in this module but
    instead we iterate over the training data to approximate the probabilistic mapping p(yhf|ylf).

    Attributes:
        result_description (dict): Dictionary containing settings for result handling and writing
        X_train (np.array): Input training matrix for HF and LF model
        Y_LF_train (np.array): Corresponding LF model response to X_train input
        Y_HF_train (np.array): Corresponding HF model response to X_train input
        Z_train (np.array): Corresponding LF informative features to X_train input
        features_config (str): Type of feature selection method
        hf_model (obj): High-fidelity model object
        lf_model (obj): Low fidelity model object
        coords_experimental_data (np.array): Coordinates of the experimental data
        time_vec (np.array): Time vector of experimental observations
        output_label (str): Name or label of the output quantity of interest (used to find the
                            data in the csv file)
        coord_labels (lst): Label or names of the underlying coordinates for the experimental
                            data. This should be in the same order as the experimental_data array
        y_obs_vec (np.array): Output data of experimental observations
        settings_probab_mapping (dict): Dictionary with settings for the probabilistic
                                        multi-fidelity mapping
        db (obj): Database object
        external_geometry_obj (obj): External geometry object
        gammas_train (np.array): Informative features evaluated at the training inputs
        scaler_gamma (obj): Scaler object for the informative features gamma


    Returns:
       BMFIAIterator (obj): Instance of the BMFIAIterator

    """

    def __init__(
        self,
        result_description,
        global_settings,
        features_config,
        hf_model,
        lf_model,
        output_label,
        coord_labels,
        settings_probab_mapping,
        db,
        external_geometry_obj,
        x_train,
        Y_LF_train,
        Y_HF_train,
        Z_train,
        coords_experimental_data,
        time_vec,
        y_obs_vec,
        gammas_train,
        scaler_gamma,
    ):
        super(BMFIAIterator, self).__init__(
            None, global_settings
        )  # Input prescribed by iterator.py

        self.result_description = result_description
        self.X_train = x_train
        self.Y_LF_train = Y_LF_train
        self.Y_HF_train = Y_HF_train
        self.Z_train = Z_train
        self.features_config = features_config
        self.hf_model = hf_model
        self.lf_model = lf_model
        self.coords_experimental_data = coords_experimental_data
        self.time_vec = time_vec
        self.output_label = output_label
        self.coord_labels = coord_labels
        self.y_obs_vec = y_obs_vec
        self.settings_probab_mapping = settings_probab_mapping
        self.db = db
        self.external_geometry_obj = external_geometry_obj
        self.gammas_train = gammas_train
        self.scaler_gamma = scaler_gamma

    @classmethod
    def from_config_create_iterator(cls, config, iterator_name=None, model=None):
        """
        Build a BMFIAIterator object from the problem description

        Args:
            config (dict): Configuration / input file for QUEENS as dictionary
            iterator_name (str): Iterator name (optional)
            model (str): Model name (optional)

        Returns:
            iterator (obj): BMFIAIterator object

        """
        # Get appropriate sections in the config file
        method_options = config["method"]["method_options"]
        model_name = method_options["model"]
        global_settings = config.get('global_settings', None)
        result_description = method_options["result_description"]

        # get mf approx settings
        mf_approx_settings = config[model_name].get("mf_approx_settings")
        features_config = mf_approx_settings["features_config"]

        # get the mf subiterator settings
        bmfia_iterator_name = mf_approx_settings["mf_subiterator"]
        bmfia_iterator_dict = config[bmfia_iterator_name]
        hf_model_name = bmfia_iterator_dict["high_fidelity_model"]
        lf_model_name = bmfia_iterator_dict["low_fidelity_model"]
        initial_design_dict = bmfia_iterator_dict["initial_design"]

        hf_model = Model.from_config_create_model(hf_model_name, config)
        lf_model = Model.from_config_create_model(lf_model_name, config)

        # ---------- configure external geometry object (returns None if not available) -
        external_geometry = ExternalGeometry.from_config_create_external_geometry(config)

        # ---------- create database object to load coordinates --------------------------
        output_label = config[model_name].get("output_label")
        coord_labels = config[model_name].get("coordinate_labels")
        db = DB_module.database
        # ---------- calculate the optimal training samples via classmethods ----------
        x_train = cls._calculate_optimal_x_train(initial_design_dict, external_geometry, lf_model)

        # ---------------------- initialize some variables / attributes ---------------
        Y_LF_train = None
        Y_HF_train = None
        Z_train = None
        coords_experimental_data = None
        time_vec = None
        y_obs_vec = None
        gammas_train = None
        scaler_gamma = StandardScaler()

        return cls(
            result_description,
            global_settings,
            features_config,
            hf_model,
            lf_model,
            output_label,
            coord_labels,
            mf_approx_settings,
            db,
            external_geometry,
            x_train,
            Y_LF_train,
            Y_HF_train,
            Z_train,
            coords_experimental_data,
            time_vec,
            y_obs_vec,
            gammas_train,
            scaler_gamma,
        )

    @classmethod
    def _calculate_optimal_x_train(cls, initial_design_dict, external_geometry_obj, model):
        """
        Based on the selected design method, determine the optimal set of input points X_train to
        run the HF and the LF model on for the construction of the probabilistic surrogate

        Args:
            initial_design_dict (dict): Dictionary with description of initial design.
            external_geometry_obj (obj): Object with information about an external geometry
            model (obj): A model object on which the calculation is performed (only needed for
                         interfaces here. The model is not evaluated here)

        Returns:
            x_train (np.array): Optimal training input samples

        """
        run_design_method = cls._get_design_method(initial_design_dict)
        x_train = run_design_method(initial_design_dict, external_geometry_obj, model)
        return x_train

    @classmethod
    def _get_design_method(cls, initial_design_dict):
        """
        Get the design method for selecting the HF data from the LF MC data-set

        Args:
            initial_design_dict (dict): Dictionary with description of initial design.

        Returns:
            run_design_method (obj): Design method for selecting the HF training set

        """
        # choose design method
        if initial_design_dict['type'] == 'random':
            run_design_method = cls._random_design
        else:
            raise NotImplementedError

        return run_design_method

    @classmethod
    def _random_design(cls, initial_design_dict, external_geometry_obj, model):
        """
        Calculate the HF training points from large LF-MC data-set based on random selection
        from bins over y_LF.

        Args:
            initial_design_dict (dict): Dictionary with description of initial design.
            external_geometry_obj (obj): Object with external geometry information
            model (obj): A model object on which the calculation is performed (only needed for
                         interfaces here. The model is not evaluated here)

        Returns:
            x_train (np.array): Optimal training input samples

        """
        # Some dummy arguments that are necessary for class initialization but not needed
        dummy_model = model
        dummy_result_description = {}
        dummy_global_settings = {}
        dummy_db = 'dummy_db'

        mc_iterator = MonteCarloIterator(
            dummy_model,
            initial_design_dict['seed'],
            initial_design_dict['num_HF_eval'],
            dummy_result_description,
            dummy_global_settings,
            external_geometry_obj,
            dummy_db,
        )
        mc_iterator.pre_run()
        x_train = mc_iterator.samples
        return x_train

    # ----------- main methods of the object form here ----------------------------------------
    def core_run(self):
        """
        Main or core run of the BMFIA iterator that summarizes the actual evaluation of the HF and
        LF models for these data and the determination of LF informative features.

        Returns:
            Z_train (np.array): Matrix with low-fidelity feature training data
            Y_HF_train (np.array): Matrix with HF training data

        """
        # ----- build model on training points and evaluate it -----------------------
        self.eval_model()

        # ----- Set the feature strategy of the probabilistic mapping (select gammas)
        self._set_feature_strategy()

        return self.Z_train, self.Y_HF_train

    def _evaluate_LF_model_for_X_train(self):
        """
        Evaluate the low-fidelity model for the X_train input data-set

        Returns:
            None

        """
        self.lf_model.update_model_from_sample_batch(self.X_train)

        # reshape the scalar output by the coordinate dimension
        num_coords = self.coords_experimental_data.shape[0]
        self.Y_LF_train = self.lf_model.evaluate()['mean'].reshape(-1, num_coords)

    def _evaluate_HF_model_for_X_train(self):
        """
        Evaluate the high-fidelity model for the X_train input data-set

        Returns:
            None

        """
        self.hf_model.update_model_from_sample_batch(self.X_train)

        # reshape the scalar output by the coordinate dimension
        num_coords = self.coords_experimental_data.shape[0]
        self.Y_HF_train = self.hf_model.evaluate()['mean'].reshape(-1, num_coords)

    def _set_feature_strategy(self):
        """
        Depending on the method specified in the input file, set the strategy that will be used to
        calculate the low-fidelity features :math:`Z_{\\text{LF}}`. Basically this methods gives
        different options on how to construct informative features :math:`\\gamma_i` from which
        the low-fidelity feature vector/matrix :math:`Z_{\\text{LF}}` is constructed upon.
        So far we have the option of:
        -  selecting :math:`\\gamma_i` manually from the input
        vector (man_features)
        - automatically determine optimal features from the input vector
        (opt_features) (not ready yet)
        - seleting no further informative features (no_features), meaning only
        the low fidelity model output is considered in the mapping.
        - Additionally integrate the spatial coordinates as an informative feature
        (coord_features)
        - Additionally integrate the time-coordinates as an informative features
        (time_features)

        Note: At the moment still under heavy development and not finished, yet.

        Returns:
            None

        """
        self.coords_experimental_data = np.tile(
            self.coords_experimental_data, (self.X_train.shape[0], 1)
        )
        if self.settings_probab_mapping['features_config'] == "man_features":
            idx_vec = self.settings_probab_mapping['X_cols']
            if len(idx_vec) < 2:
                gammas_train = np.atleast_2d(self.X_train[:, idx_vec]).T
            else:
                gammas_train = np.atleast_2d(self.X_train[:, idx_vec])

            # standardization
            self.gammas_train = self.scaler_gamma.fit_transform(gammas_train.T).T

            z_lst = []
            for y in self.Y_LF_train.T:
                z_lst.append(np.hstack([np.atleast_2d(y).T, np.atleast_2d(self.gammas_train).T]))

            self.Z_train = np.array(z_lst).T

        elif self.settings_probab_mapping['features_config'] == "opt_features":
            if self.settings_probab_mapping['num_features'] < 1:
                raise ValueError(
                    f"You selected "
                    f"'num_features={self.settings_probab_mapping['num_features']}' optimal"
                    f"informative features. This is not a valid choice for the number of "
                    f"informative features! Abort..."
                )
            self._update_probabilistic_mapping_with_features()
        elif self.settings_probab_mapping['features_config'] == "coord_features":
            self.Z_train = np.hstack([self.Y_LF_train, self.coords_experimental_data])
        elif self.settings_probab_mapping['features_config'] == "no_features":
            self.Z_train = self.Y_LF_train
        elif self.settings_probab_mapping['features_config'] == "time_features":
            time_repeat = int(self.coords_experimental_data.shape[0] / self.time_vec.size)
            self.time_vec = np.repeat(self.time_vec.reshape(-1, 1), repeats=time_repeat, axis=0)
            self.time_vec = self.time_vec / np.max(self.time_vec) * (
                np.max(self.y_obs_vec) - np.min(self.y_obs_vec)
            ) + np.min(self.y_obs_vec)

            self.Z_train = np.hstack([self.Y_LF_train, self.time_vec])
        else:
            raise IOError("Feature space method specified in input file is unknown!")

    def _update_probabilistic_mapping_with_features(self):
        raise NotImplementedError(
            "Optimal features for inverse problems are not yet implemented! Abort..."
        )

    def eval_model(self):
        """
        Evaluate the LF and HF model to for the training inputs X_train.

        Returns:
            None

        """
        # ---- run LF model on X_train (potentially we need to iterate over this and the previous
        # step to determine optimal X_train; for now just one sequence)
        _logger.info('-------------------------------------------------------------------')
        _logger.info('Starting to evaluate the low-fidelity model for training points....')
        _logger.info('-------------------------------------------------------------------')

        self._evaluate_LF_model_for_X_train()

        _logger.info('-------------------------------------------------------------------')
        _logger.info('Successfully calculated the low-fidelity training points!')
        _logger.info('-------------------------------------------------------------------')

        # ---- run HF model on X_train
        _logger.info('-------------------------------------------------------------------')
        _logger.info('Starting to evaluate the high-fidelity model for training points...')
        _logger.info('-------------------------------------------------------------------')

        self._evaluate_HF_model_for_X_train()

        _logger.info('-------------------------------------------------------------------')
        _logger.info('Successfully calculated the high-fidelity training points!')
        _logger.info('-------------------------------------------------------------------')

    # ------------------- BELOW JUST PLOTTING AND SAVING RESULTS ------------------
    def post_run(self):
        """
        Saving and plotting of the results.

        Returns:
            None
        """
        if self.result_description['write_results'] is True:
            results = process_ouputs(self.output, self.result_description)
            write_results(
                results,
                self.global_settings["output_dir"],
                self.global_settings["experiment_name"],
            )
