import numpy as np
import pqueens.utils.pdf_estimation as est
from pqueens.iterators.data_iterator import DataIterator
from pqueens.interfaces.bmfmc_interface import BmfmcInterface
from .model import Model
from .simulation_model import SimulationModel
import scipy.stats as st
from pqueens.variables.variables import Variables
from sklearn.preprocessing import StandardScaler
import pqueens.visualization.bmfmc_visualization as qvis
from tqdm import tqdm


class BMFMCModel(Model):
    """
    Bayesian multi-fidelity Monte-Carlo model for uncertainty quantification, which is a
    probabilistic mapping between a high-fidelity simulation model (HF) and one or
    more low fidelity simulation models (LFs), respectively informative
    features :math:`(\\gamma)` from the input space. Based on this mapping and the LF samples
    :math:`\\mathcal{D}_{LF}^*=\\{Z^*,Y_{LF}*^\\}`, the BMFMC model computes the
    posterior statistics:

    :math:`\\mathbb{E}_{f^*}\\left[p(y_{HF}^*|f^*,D_f)\\right]`, equation (14) in [1]

    and

    :math:`\\mathbb{V}_{f^*}\\left[p(y_{HF}^*|f^*,D_f)\\right]`, equation (15) in [1]

    of the HF model's output uncertainty.

    The BMFMC model is designed to be constructed upon the sampling data of a LF model
    :math:`\\mathcal{D}_{LF}^*=\\{Z^*,Y_{LF}^*\\}` that are provided by pickle or csv-files,
    and offers than different options to obtain the HF data:

    1.  Provide HF training data in a file (Attention: user needs to make sure that this training
        set is representative and its input :math:`Z` is a subset of the LF model sampling set:
        :math:`Z\\subset Z^*`
    2.  Run optimal HF simulations based on LF data. This requires a suitable simulation sub-model
        and sub-iterator for the HF model. Note: This submodel/iterator can also be used for
        the active learning feature that allows batch-sequential refinement of the BMFMC method by
        determining next optimal HF simulations
    3.  Provide HF sampling data (as a file), calculated with same :math:`Z^*` as the
        LF simulation runs and select optimal HF training set from this data. This is just helpful
        for scientific benchmarking when a ground-truth solution for the HF output uncertainty has
        been sampled before and this data exists anyway.

    Attributes:

        interface (obj): Interface object
        settings_probab_mapping (dict): Settings/configurations for the probabilistic mapping model
                                        between HF and LF models, respectively input features.
                                        This includes:

                                        - *types*: `gp_approximation_gpy`
                                        - *features_config*: `opt_features`, `no_features` or
                                                             `man_features`
                                        - *num_features*: for `opt_features`, number of features
                                                          to be used
                                        - *X_cols*: for `man_features`, columns of X-matrix that
                                                    should be used as an informative feature

        subordinate_model (obj): HF (simulation) model to run simulations that yield the HF
                                 training set :math:`\\mathcal{D}_{HF}=\\{Z, Y_{HF}\\}` or HF
                                 model to perform active learning (in to order to extend training
                                 data set of probabilistic mapping with most promising HF
                                 data points)

        eval_fit (str): String that determines which error-evaluation technique should be used to
                        assess the quality of the probabilistic mapping
        error_measures (list): List of string with desired error metrics that should be used to
                               assess the quality of the probabilistic mapping based on
                               cross-validation
        X_train (np.array): Matrix of simulation inputs correspond to the training
                                      data-set of the multi-fidelity mapping
        Y_HF_train (np.array): Vector or matrix of HF output that correspond to training input
                               according to :math:`Y_{HF} = y_{HF}(X)`.
        Y_LFs_train (np.array): Output vector/matrix of one or multiple LF models that correspond to
                                the training input according to :math:`Y_{LF,i}=y_{LF,i}(X)`
        X_mc (np.array): Matrix of simulation inputs that were used in the Monte-Carlo sampling
                         of the LF models. Each row is one input set for a simulation. Columns
                         refer to different realizations of the same variable
        Y_LFs_mc (np.array): Output vector/matrix for the LF models that correspond to the X_mc
                            according to :math:`Y_{LF,i}^*=y_{LF,i}(X^*)`. At the moment Y_LF_mc
                            contains in one row scalar results for different LF models. (In the
                            future we will change the format to pandas dataframes to handle
                            vectorized/functional outputs for different models more elegantly)
        Y_HF_mc (np.array): (optional for benchmarking) Output vector/matrix for the HF model
                            that correspond to the X_mc according to
                            :math:`Y_{HF}^*=y_{HF}(X^*)`.
        active_learning (bool): Flag that triggers active learning on the HF model (not
                                implemented yet)
        gammas_ext_mc (np.array): Matrix of extended low-fidelity informative features
                                :math:`\\boldsymbol{\\Gamma}^*` corresponding to Monte-Carlo
                                input :math:`X^*`
        gammas_ext_train (np.array): Matrix of extended low-fidelity informative features
                                   :math:`\\boldsymbol{\\Gamma}` corresponding to the training
                                   input :math:`X`
        Z_train (np.array): Training matrix of low-fidelity features according to
                            :math:`Z=\\left[y_{LF,i}(X),\\Gamma\\right]`
        Z_mc (np.array): Monte-Carlo matrix of low-fidelity features according to
                         :math:`Z^*=\\left[y_{LF,i}(X^*),\\Gamma^*\\right]`
        m_f_mc (np.array): Vector of posterior mean values of multi-fidelity mapping
                           corresponding to the Monte-Carlo input Z_mc according to
                           :math:`\\mathrm{m}_{f^*}(Z^*)`
        var_f_mc (np.array): Vector of posterior variance of multi-fidelity mapping
                             corresponding to the Monte-Carlo input Z_mc according to
                             :math:`\\mathrm{m}_{f^*}(Z^*)`
        y_pdf_support (np.array): Support grid for HF output density :math:`p(y_{HF})`
        p_yhf_mean (np.array): Vector that contains the mean approximation of the HF output
                               density defined on y_hf_support. The vector p_yhf_mean is defined as:
                               :math:`\\mathbb{E}_{f^*}\\left[p(y_{HF}^*|f^*,D_f)\\right]`
                               according to eq. (14) in [1]
        p_yhf_var (np.array): Vector that contains the variance approximation of the HF output
                              density defined on y_hf_support. The vector p_yhf_var is defined as:
                              :math:`\\mathbb{V}_{f^*}\\left[p(y_{HF}^*|f^*,D_f)\\right]`
                              according to eq. (15) in [1]
        predictive_var_bool (bool): Flag that determines whether p_yhf_var should be computed
        p_yhf_mc (np.array): (optional) Monte-Carlo based kernel-density estimate of the HF output
        p_ylf_mc (np.array): (optional) Kernel density estimate for LF model output.
                            Note: For BMFMC the explicit density is never required, only the
                            :math:`\\mathcal{D}_{LF}` is used in the algorithm
        no_features_comparison_bool (bool): If flag is true, the result will be compared to a
                                            prediction that used no LF input features
        eigenfunc_random_fields (np.array): Matrix containing the discretized eigenfunctions of a
                                            underlying random field. Note: This is an intermediate
                                            solution and should be moved to the variables module!
                                            The current solution works so far only for one random
                                            field!
        f_mean_train (np.array): Vector of predicted mean values of multi-fidelity mapping
                                 corresponding to the training input Z_train according to
                                 :math:`\\mathrm{m}_{f^*}(Z)`
        lf_data_iterators (obj): Data iterators to load sampling data of low-fidelity models from a
                                 file
        hf_data_iterator (obj):  Data iterator to load the benchmark sampling data from a HF model
                                 from a file (optional and only for scientific benchmark)
        uncertain_parameters (dict): Dictionary containing probabilistic description of the
                                      uncertain parameters / random fields
        training_indices (np.array): Vector with indices to select the training data subset from
                                     the larger data set of Monte-Carlo data

    Returns:
        Instance of BMFMCModel

    References:
        [1] Nitzler, J., Biehler, J., Fehn, N., Koutsourelakis, P.-S. and Wall, W.A. (2020),
            "A Generalized Probabilistic Learning Approach for Multi-Fidelity Uncertainty
            Propagation in Complex Physical Simulations", arXiv:2001.02892
    """

    def __init__(
        self,
        settings_probab_mapping,
        eval_fit,
        error_measures,
        active_learning,
        predictive_var_bool,
        y_pdf_support,
        uncertain_parameters,
        subordinate_model=None,
        no_features_comparison_bool=False,
        lf_data_iterators=None,
        hf_data_iterator=None,
    ):

        self.interface = None
        self.settings_probab_mapping = settings_probab_mapping
        self.subordinate_model = subordinate_model
        self.eval_fit = eval_fit
        self.error_measures = error_measures
        self.X_train = None
        self.Y_HF_train = None
        self.Y_LFs_train = None
        self.X_mc = None
        self.Y_LFs_mc = None
        self.Y_HF_mc = None
        self.active_learning = active_learning
        self.gammas_ext_mc = None
        self.gammas_ext_train = None
        self.Z_train = None
        self.Z_mc = None
        self.m_f_mc = None
        self.var_y_mc = None
        self.y_pdf_support = None
        self.p_yhf_mean = None
        self.p_yhf_var = None
        self.predictive_var_bool = predictive_var_bool
        self.p_yhf_mc = None
        self.p_ylf_mc = None
        self.no_features_comparison_bool = no_features_comparison_bool
        self.eigenfunc_random_fields = None  # TODO this should be moved to the variable class!
        self.eigenvals = None
        self.f_mean_train = None
        self.y_pdf_support = y_pdf_support
        self.lf_data_iterators = lf_data_iterators
        self.hf_data_iterator = hf_data_iterator
        self.training_indices = None

        super(BMFMCModel, self).__init__(
            name="bmfmc_model", uncertain_parameters=uncertain_parameters, data_flag=True
        )  # TODO handling of variables, fields and parameters should be updated!

    @classmethod
    def from_config_create_model(
        cls, model_name, config,
    ):
        """
        Create a BMFMC model from a problem description defined in the input file of QUEENS

        Args:
            config (dict): Dictionary containing the problem description and created from the
                           json-input file
            model_name (str): Name of the model

        Returns:
            BMFMCModel (obj): A BMFMCModel object
        """

        # TODO the unlabeled treatment of raw data for eigenfunc_random_fields and input vars and
        #  random fields is prone to errors and should be changed! The implementation should
        #  rather use the variable module and reconstruct the eigenfunctions of the random fields
        #  if not provided in the data field

        # get model options
        model_options = config['method'][model_name]
        eval_fit = model_options["eval_fit"]
        error_measures = model_options["error_measures"]
        settings_probab_mapping = model_options["approx_settings"]
        lf_data_paths = model_options.get("path_to_lf_data")
        hf_data_path = model_options.get("path_to_hf_data")

        # get some method options
        method_options = config["method"]["method_options"]
        no_features_comparison_bool = method_options["BMFMC_reference"]
        active_learning = method_options["active_learning"]
        predictive_var_bool = method_options["predictive_var"]
        y_pdf_support_max = method_options["y_pdf_support_max"]
        y_pdf_support_min = method_options["y_pdf_support_min"]

        y_pdf_support = np.linspace(y_pdf_support_min, y_pdf_support_max, 200)
        # ------------------------------ ACTIVE LEARNING ------------------------------
        if active_learning is True:  # TODO also if yhf is not computed yet not only for a.l.
            # TODO: create subordinate model for active learning
            subordinate_HF_model_name = model_options["subordinate_model"]
            subordinate_model = SimulationModel.from_config_create_model(
                subordinate_HF_model_name, config
            )
        else:
            subordinate_model = None  # TODO For now not used

        # ----------------------- create subordinate data iterators ------------------------------
        lf_data_iterators = [DataIterator(path, None, None) for path in lf_data_paths]
        hf_data_iterator = DataIterator(hf_data_path, None, None)
        uncertain_parameters = None  # we set this None for now and update in load_sampling_data()
        # method later

        return cls(
            settings_probab_mapping,
            eval_fit,
            error_measures,
            active_learning,
            predictive_var_bool,
            y_pdf_support,
            uncertain_parameters,
            lf_data_iterators=lf_data_iterators,
            hf_data_iterator=hf_data_iterator,
            subordinate_model=subordinate_model,
            no_features_comparison_bool=no_features_comparison_bool,
        )

    def evaluate(self):
        """
        Construct the probabilistic mapping between HF model and LF features and evaluate the
        BMFMC routine. This evaluation consists of two steps.:
            #. Evaluate the probabilistic mapping for LF Monte Carlo Points and the LF training
               points
            #. Use the previous result to actually evaluate the BMFMC posterior statistics

        Returns:
            output (dict): Dictionary containing the core results and some additional quantities:
                           *  Z_mc: LF-features Monte-Carlo data
                           *  m_f_mc: posterior mean values of probabilistic mapping (f) for LF
                                      Monte-Carlo inputs (Y_LF_mc or Z_mc)
                           *  var_y_mc: posterior variance of probabilistic mapping (f) for LF
                                        Monte-Carlo inputs (Y_LF_mc or Z_mc)
                           *  y_pdf_support: PDF support used in this analysis
                           *  p_yhf_mean: Posterior mean prediction of HF output pdf
                           *  p_yhf_var: Posterior variance prediction of HF output pdf
                           *  p_yhf_mean_BMFMC: Reference without features, posterior mean
                                                prediction of HF output pdf
                           *  p_yhf_var_BMMFMC: Reference without features, posterior variance
                                                prediction of HF output pdf
                           *  p_ylf_mc: For illustration purpose, output pdf of LF model
                           *  p_yhf_mc: For benchmarking, output pdf of HF model based on kde
                                        estimate for full Monte-Carlo simulation on HF model
                           *  Z_train: LF feature vector for training of the probabilistic mapping
        """
        self.interface = BmfmcInterface(self.settings_probab_mapping)
        p_yhf_mean_BMFMC = None
        p_yhf_var_BMFMC = None

        if np.any(self.Y_HF_mc):
            self.compute_pymc_reference()

        # ------------------ STANDARD BMFMC (no additional features) for comparison ----------------
        if self.no_features_comparison_bool is True:
            # construct the probabilistic mapping between y_HF and y_LF
            self.build_approximation(approx_case=False)

            # Evaluate probabilistic mapping for LF points
            self.m_f_mc, self.var_y_mc = self.interface.map(self.Y_LFs_mc.T)
            self.f_mean_train, _ = self.interface.map(self.Y_LFs_train.T)

            # actual 'evaluation' of BMFMC routine
            self.compute_pyhf_statistics()
            p_yhf_mean_BMFMC = self.p_yhf_mean  # this is just for comparison so no class attribute
            p_yhf_var_BMFMC = self.p_yhf_var  # this is just for comparison so no class attribute

        # ------------------- Generalized BMFMC with features --------------------------------------
        # construct the probabilistic mapping between y_HF and LF features z_LF
        self.build_approximation(approx_case=True)

        # Evaluate probabilistic mapping for certain Z-points
        self.m_f_mc, self.var_y_mc = self.interface.map(self.Z_mc.T)
        self.f_mean_train, _ = self.interface.map(self.Z_train.T)
        # TODO the variables (here) manifold must probably an object from the variable class!

        # actual 'evaluation' of generalized BMFMC routine
        self.compute_pyhf_statistics()

        # gather and return the output
        output = {
            "Z_mc": self.Z_mc,
            "m_f_mc": self.m_f_mc,
            "var_y_mc": self.var_y_mc,
            "y_pdf_support": self.y_pdf_support,
            "p_yhf_mean": self.p_yhf_mean,
            "p_yhf_var": self.p_yhf_var,
            "p_yhf_mean_BMFMC": p_yhf_mean_BMFMC,
            "p_yhf_var_BMFMC": p_yhf_var_BMFMC,
            "p_ylf_mc": self.p_ylf_mc,
            "p_yhf_mc": self.p_yhf_mc,
            "Z_train": self.Z_train,
        }
        return output

    def load_sampling_data(self):
        """
        Load the low-fidelity sampling data from a pickle file into QUEENS.
        Check if high-fidelity benchmark data is available and load this as well.

        Returns:
            None
        """
        # --------------------- load description for random fields/ parameters ---------
        # here we load the random parameter description from the pickle file
        # we load the description of the uncertain parameters from the first lf iterator
        # (note: all lf iterators have the same description)
        self.uncertain_parameters = (
            self.lf_data_iterators[0].read_pickle_file().get('uncertain_parameters')
        )

        # --------------------- load LF sampling data with data iterators --------------
        self.X_mc = self.lf_data_iterators[0].read_pickle_file().get("input")
        # TODO maybe load this also as samples for the uncertain parameters?
        # here we assume that all lfs have the same input vector
        try:
            self.eigenfunc_random_fields = (
                self.lf_data_iterators[0].read_pickle_file().get("eigenfunc")
            )
            self.eigenvals = self.lf_data_iterators[0].read_pickle_file().get("eigenvalue")
        except IOError:
            self.eigenfunc_random_fields = None
            self.eigenvals = None

        Y_LFs_mc = [
            lf_data_iterator.read_pickle_file().get("output")[:, 0]
            for lf_data_iterator in self.lf_data_iterators
        ]
        self.Y_LFs_mc = np.atleast_2d(np.vstack(Y_LFs_mc)).T

        # ------------------- Deal with potential HF-MC data --------------------------
        if self.hf_data_iterator is not None:
            try:
                self.Y_HF_mc = self.hf_data_iterator.read_pickle_file().get("output")[:, 0]
                # TODO neglect vectorized output atm
            except FileNotFoundError:
                raise FileNotFoundError(
                    "The file containing the high-fidelity Monte-Carlo data"
                    "was not found! Abort..."
                )
        else:
            raise NotImplementedError(
                "Currently the Monte-Carlo benchmark data for the "
                "high-fidelity model must be provided! In the future QUEENS"
                "will also be able to run the HF simulation based on the"
                "LF data set, automatically. For now abort!...."
            )

    def get_hf_training_data(self):
        """
        Given the low-fidelity sampling data and the optimal training input :math:`X`, either
        simulate the high-fidelity response for :math:`X` or load the corresponding high-fidelity
        response from the high-fidelity benchmark data provided by a pickle file.

        Returns:
            None

        """
        # check if training simulation input was correctly calculated in iterator
        if self.X_train is None:
            raise ValueError(
                "The training input X_train cannot be 'None'! The training inputs "
                "should have been calculated in the iterator! Abort..."
            )

        # check how we should get the corresponding HF simulation output
        if self.Y_HF_mc is not None:
            # match Y_HF_mc data with X_train do determine Y_HF_train
            index_rows = [
                np.where(np.all(self.X_mc == self.X_train[i, :], axis=1))[0][0]
                for i, _ in enumerate(self.X_train[:, 0])
            ]

            self.Y_HF_train = np.atleast_2d(
                np.asarray([self.Y_HF_mc[index] for index in index_rows])
            ).T

        else:
            raise NotImplementedError(
                "Currently the Monte-Carlo benchmark data for the "
                "high-fidelity model must be provided! In the future QUEENS"
                "will also be able to run the HF simulation based on the"
                "LF data set, automatically. For now abort!...."
            )

    def build_approximation(self, approx_case=True):
        """
        Construct the probabilistic surrogate / mapping based on the provided training-data and
        optimize the hyper-parameters by maximizing the data's evidence or its lower bound (ELBO).

        Args:
            approx_case (bool):  Boolean that switches input features :math:`\\boldsymbol{\\gamma}`
                                 off if set to `False`. If not specified or set to `True`
                                 informative input features will be used in the BMFMC framework.

        Returns:
            None
        """

        # get the HF output data (from file or by starting a simulation, dependent on config)
        self.get_hf_training_data()

        # ----- train regression model on the data ----------------------------------------
        if approx_case is True:
            self.set_feature_strategy()
            self.interface.build_approximation(self.Z_train, self.Y_HF_train)
        else:
            self.interface.build_approximation(self.Y_LFs_train, self.Y_HF_train)

        # TODO below is a wrong error measure for probabilistic mapping
        if self.eval_fit == "kfold":
            error_measures = self.eval_surrogate_accuracy_cv(
                self.Z_train, self.Y_HF_train, k_fold=5, measures=self.error_measures
            )
            for measure, error in error_measures.items():
                print("Error {} is:{}".format(measure, error))

        #  TODO implement proper active learning with subiterator below
        if self.active_learning is True:
            raise NotImplementedError(
                'Active learning is not implemented yet! At the moment you '
                'cannot use this option! Please set active_learning to '
                '`False`!'
            )

    def eval_surrogate_accuracy_cv(self, Z, Y_HF, k_fold, measures):
        """
        Compute k-fold cross-validation error for probabilistic mapping

        Args:
            Z (np.array):       Low-fidelity features input-array
            Y_HF (np.array):    High-fidelity output-array
            k_fold (int):       Split dataset in k_fold subsets for cross-validation
            measures (list):    List with desired error metrics

        Returns:
            dict: Dictionary with error metrics and corresponding error values
        """

        if not self.interface.is_initiliazed():
            raise RuntimeError("Cannot compute accuracy of an uninitialized model")

        response_cv = self.interface.cross_validate(Z, Y_HF, k_fold)
        y_pred = np.reshape(np.array(response_cv), (-1, 1))

        error_info = compute_error_measures(Y_HF, y_pred, measures)
        return error_info

    def compute_pyhf_statistics(self):
        """
        Calculate the high-fidelity output density prediction `p_yhf_mean` and its credible bounds
        `p_yhf_var` on the support `y_pdf_support` according to equation (14) and (15) in [1].

        Returns:
            None

        """
        self._calculate_p_yhf_mean()

        if self.predictive_var_bool:
            self._calculate_p_yhf_var()
        else:
            self.p_yhf_var = None

    def _calculate_p_yhf_mean(self):
        """
        Calculate the posterior mean estimate for the HF density.

        Returns:
            None

        """
        standard_deviation = np.sqrt(self.var_y_mc)
        pdf_mat = st.norm.pdf(self.y_pdf_support, loc=self.m_f_mc, scale=standard_deviation)
        pyhf_mean_vec = np.sum(pdf_mat, axis=0)
        self.p_yhf_mean = 1 / self.m_f_mc.size * pyhf_mean_vec

    def _calculate_p_yhf_var(self):
        """
        Calculate the posterior variance of the HF density prediction.

        Returns:
            None

        """
        # calculate full posterior covariance matrix for testing points
        _, k_post = self.interface.map(self.Z_mc.T, support='f', full_cov=True)

        spacing = 1
        f_mean_pred = self.m_f_mc[0::spacing, :]
        yhf_var_pred = self.var_y_mc[0::spacing, :]
        k_post = k_post[0::spacing, 0::spacing]

        # Define support structure for computation
        points = np.vstack((self.y_pdf_support, self.y_pdf_support)).T

        # Define the outer loop (addition of all multivariate normal distributions
        yhf_pdf_grid = np.zeros((points.shape[0],))
        i = 1
        print('\n')
        for num1, (mean1, var1) in enumerate(
            zip(tqdm(f_mean_pred, desc=r'Calculating Var_f[p(y_HF|f,z,D)]'), yhf_var_pred)
        ):

            for num2, (mean2, var2) in enumerate(
                zip(f_mean_pred[num1 + 1 :], yhf_var_pred[num1 + 1 :])
            ):
                num2 = num1 + num2
                covariance = k_post[num1, num2]
                mean_vec = np.array([mean1, mean2])
                diff = points - mean_vec.T
                det_sigma = var1 * var2 - covariance ** 2

                if det_sigma < 0:
                    det_sigma = 1e-6
                    covariance = 0.95 * covariance

                inv_sigma = (
                    1
                    / det_sigma
                    * np.array([[var2, -covariance], [-covariance, var1]], dtype=np.float64)
                )

                a = np.dot(diff, inv_sigma)
                b = np.einsum('ij,ij->i', a, diff)
                c = np.sqrt(4 * np.pi ** 2 * det_sigma)
                args = -0.5 * b + np.log(1 / c)
                args[args > 40] = 40  # limit arguments for for better conditioning
                yhf_pdf_grid += np.exp(args)
                i = i + 1

                # Define inner loop (add rows of 2D domain to yield variance function)
                self.p_yhf_var = 1 / (i - 1) * yhf_pdf_grid - 0.9995 * self.p_yhf_mean ** 2

    def compute_pymc_reference(self):
        """
         Given a high-fidelity Monte-Carlo benchmark dataset, compute the reference kernel
         density estimate for the quantity of interest and optimize the bandwith of the kde.

        Returns:
            None

        """
        # optimize the bandwidth for the kde
        bandwidth_hfmc = est.estimate_bandwidth_for_kde(
            self.Y_HF_mc, np.amin(self.Y_HF_mc), np.amax(self.Y_HF_mc)
        )
        # perform kde with the optimized bandwidth
        self.p_yhf_mc, _ = est.estimate_pdf(
            np.atleast_2d(self.Y_HF_mc),
            bandwidth_hfmc,
            support_points=np.atleast_2d(self.y_pdf_support),
        )
        if self.Y_LFs_train.shape[1] < 2:
            self.p_ylf_mc, _ = est.estimate_pdf(
                np.atleast_2d(self.Y_LFs_mc).T,
                bandwidth_hfmc,
                support_points=np.atleast_2d(self.y_pdf_support),
            )  # TODO: make this also work for several lfs

    def set_feature_strategy(self):
        """
        Depending on the method specified in the input file, set the strategy that will be used to
        calculate the low-fidelity features :math:`Z_{\\text{LF}}`.

        Returns:
            None

        """
        if self.settings_probab_mapping['features_config'] == "man_features":
            idx_vec = self.settings_probab_mapping['X_cols']
            self.gammas_ext_train = np.atleast_2d(self.X_train[:, idx_vec])
            self.gammas_ext_mc = np.atleast_2d(self.X_mc[:, idx_vec])
            self.Z_train = np.hstack([self.Y_LFs_train, self.gammas_ext_train])
            self.Z_mc = np.hstack([self.Y_LFs_mc, self.gammas_ext_mc])
        elif self.settings_probab_mapping['features_config'] == "opt_features":
            if self.settings_probab_mapping['num_features'] < 1:
                raise ValueError(
                    f'You specified {self.settings_probab_mapping["num_features"]} features, '
                    'which is an '
                    f'invalid value! Please only specify integer values greater than zero! Abort...'
                )
            self.update_probabilistic_mapping_with_features()
        elif self.settings_probab_mapping['features_config'] == "no_features":
            self.Z_train = self.Y_LFs_train
            self.Z_mc = self.Y_LFs_mc
        else:
            raise ValueError("Feature space method specified in input file is unknown!")

        # TODO current workaround to update variables object with the inputs for the
        #  multi-fidelity mapping
        update_model_variables(self.Y_LFs_train, self.Z_mc)

    def calculate_extended_gammas(self):
        """
        Given the low-fidelity sampling data, calculate the extended input features
        :math:`\\gamma_{\\text{LF,ext}}`. The informative input
        features :math:`\\boldsymbol{\\gamma}` are calculated so that
        they would maximize the Pearson correlation coefficient between :math:`\\gamma_i^*` and
        :math:`Y_{\\text{LF}}^*`. Afterwards :math:`z_{\\text{LF}}` is composed by
        :math:`y_{\\text{LF}}` and :math:`\\boldsymbol{\\gamma_{\\text{LF}}`

        Returns:
            None

        """
        x_red = self.input_dim_red()
        x_iter_test = x_red
        self.gammas_ext_mc = np.empty((x_iter_test.shape[0], 0))

        # Iteratively sort reduced input space by importance of its dimensions
        for counter in range(x_red.shape[1]):
            # standardize the LF output vector for better performance
            Y_LFS_mc_stdized = StandardScaler().fit_transform(self.Y_LFs_mc)

            # calculate the scores/ranking of candidates for informative input features gamma_i
            corr_coef_unnorm = np.abs(np.dot(x_iter_test.T, Y_LFS_mc_stdized))

            # --------- plot the rankings/scores for first iteration -------------------------------
            if counter == 0:
                ele = np.arange(1, x_iter_test.shape[1] + 1)
                qvis.bmfmc_visualization_instance.plot_feature_ranking(
                    ele, corr_coef_unnorm, counter
                )
            # --------------------------------------------------------------------------------------

            # select input feature with the highest score
            select_bool = corr_coef_unnorm == np.max(corr_coef_unnorm)
            test_iter = np.dot(x_iter_test, select_bool)

            # Scale features linearly to LF output data so that probabilistic model
            # can be fit easier
            features_test = _linear_scale_a_to_b(test_iter, self.Y_LFs_mc)

            # Assemble feature vectors and informative features
            self.gammas_ext_mc = np.hstack((self.gammas_ext_mc, features_test))

    def update_probabilistic_mapping_with_features(self):
        """
        Given the number of additional informative features of the input and the
        extended feature matrix :math:`\\Gamma_{LF,ext}`, assemble first the LF feature matrix
        :math:`Z_{LF}`. In a next step, update the probabilistic mapping with the LF-features.
        The former steps includes a training and prediction step. The determination of optimal
        training points is outsourced to the BMFMC iterator and the results get only called at
        this place.

        Returns:
            None

        """
        # Select demanded number of features
        gamma_mc = self.gammas_ext_mc[:, 0 : self.settings_probab_mapping['num_features']]
        self.Z_mc = np.hstack([self.Y_LFs_mc, gamma_mc])

        # Get training data from training_indices previously calculated in the iterator
        self.Z_train = self.Z_mc[self.training_indices, :]

        # update dataset for probabilistic mapping with new feature dimensions
        self.interface.build_approximation(self.Z_train, self.Y_HF_train)
        self.m_f_mc, self.var_y_mc = self.interface.map(self.Z_mc.T)
        self.f_mean_train, _ = self.interface.map(self.Z_train.T)

    def input_dim_red(self):
        """
        Unsupervised dimensionality reduction of the input space. The random are first expressed
        via a truncated Karhunen-Loeve expansion that still contains, e.g., 95 % of the field's
        variance. Afterwards, input samples of the random fields get projected on the reduced
        basis and the coefficients of the projection sever as the new reduced encoding for the
        latter. Eventually the uncorrelated input samples and the reduced representation of
        random field samples get assembled to a new reduced input vector which is also
        standardized along each of the remaining dimensions.

        Returns:
            X_red_test (np.array): Dimensionality reduced input matrix corresponding to
                                   testing/sampling data for the probabilistic mapping

        """
        x_uncorr, truncated_basis_dict = self.get_random_fields_and_truncated_basis(
            explained_var=95
        )
        coefs_mat = _project_samples_on_truncated_basis(truncated_basis_dict, self.X_mc.shape[0])
        X_red_test_stdizd = _assemble_x_red_stdizd(x_uncorr, coefs_mat)

        return X_red_test_stdizd

    def get_random_fields_and_truncated_basis(self, explained_var=0.95):
        """
        Get the random fields and their description from the data files (pickle-files) and
        return their truncated basis. The truncation is determined based on the explained
        variance threshold (explained_var).

        Args:
            explained_var (float): Threshold for truncation in percent.

        Returns:
            random_fields_trunc_dict (dict): Dictionary containing samples of the random fields
                                             as well as their truncated basis.
            x_uncorr (np.array): Array containing the samples of remaining uncorrelated random
                                 variables

        """
        # determine uncorrelated random variables
        num_random_var = len(self.uncertain_parameters.get("random_variables"))
        x_uncorr = self.X_mc[:, 0:num_random_var]

        # iterate over all random fields
        dim_random_fields = 0
        for random_field, basis, eigenvals in zip(
            self.uncertain_parameters.get("random_fields").items(),
            self.eigenfunc_random_fields.items(),
            self.eigenvals.items(),
        ):
            # check which type of random field was used
            if random_field[1].get("corrstruct") != "non_stationary_squared_exp":
                raise NotImplementedError(
                    f"Your random field had the correlation structure "
                    f"{random_field.get('corrstruct')} but this function is at "
                    f"the moment only implemented for the correlation "
                    f"structure non_stationary_squared_exp! Abort...."
                )
            else:
                # write the simulated samples of the random fields also in the new dictionary
                # Attention: Here we assume that X_mx contains in the first columns uncorrelated
                #            random variables until the column id 'num_random_var' and then only
                #            random fields
                random_fields_trunc_dict = {
                    random_field[0]: {
                        "samples": self.X_mc[
                            :,
                            num_random_var
                            + dim_random_fields : num_random_var
                            + dim_random_fields
                            + random_field[1]["num_points"],
                        ]
                    }
                }

                # determine the truncation basis
                idx_truncation = [
                    idx for idx, eigenval in enumerate(eigenvals[1]) if eigenval > explained_var
                ][0]

                # write the truncated basis also in the dictionary
                random_fields_trunc_dict[random_field[0]].update(
                    {"trunc_basis": basis[1][0:idx_truncation]}
                )

                # adjust the counter for next iteration
                dim_random_fields += random_field[1]["num_points"]

        return x_uncorr, random_fields_trunc_dict


# --------------------------- functions ------------------------------------------------------
def _project_samples_on_truncated_basis(truncated_basis_dict, num_samples):
    """
    Project the high-dimensional samples of the random field on the truncated bases to yield the
    projection coefficients of the series expansion that serve as a new reduced representation of
    the random fields/

    Args:
        truncated_basis_dict (dic): Dictionary containing random field samples and truncated bases
        num_samples (int): Number of Monte-Carlo samples

    Returns:
        coefs_mat (np.array): Matrix containing the reduced representation of all random fields
                              stacked together along the columns
    """
    coefs_mat = np.empty((num_samples, 0))
    for basis in truncated_basis_dict.items():
        coefs_mat = np.hstack((coefs_mat, np.dot(basis[1]["samples"], basis[1]["trunc_basis"].T)))

    return coefs_mat


def compute_error(y_act, y_pred, measure):
    """ Compute error for a given a specific error metric

        Args:
            y_act (np.array):  Prediction with full data set
            y_pred (np.array): Prediction with reduced data set
            measure (str):     Desired error metric

        Returns:
            float: error based on desired metric
    """
    if measure == "sum_squared":
        error = np.sum((y_act - y_pred) ** 2)
    elif measure == "mean_squared":
        error = np.mean((y_act - y_pred) ** 2)
    elif measure == "root_mean_squared":
        error = np.sqrt(np.mean((y_act - y_pred) ** 2))
    elif measure == "sum_abs":
        error = np.sum(np.abs(y_act - y_pred))
    elif measure == "mean_abs":
        error = np.mean(np.abs(y_act - y_pred))
    elif measure == "abs_max":
        error = np.max(np.abs(y_act - y_pred))
    else:
        raise NotImplementedError("Desired error measure is unknown!")
    return error


def compute_error_measures(y_act, y_pred, measures):
    """
        Compute error-metrics based on difference between prediction with full data-set and reduced
        data-set

        Args:
            y_act (np.array):  Predictions with full data-set
            y_pred (np.array): Predictions with reduced data-set
            measures (list):   Dictionary with desired error metrics

        Returns:
            dict: Dictionary with error measures and corresponding error values
    """
    error_measures = {}
    for measure in measures:
        error_measures[measure] = compute_error(y_act, y_pred, measure)
    return error_measures


def update_model_variables(Y_LFs_train, Z_mc):
    """
    Intermediate solution: Update the QUEENS variable object with the previous calculated
    low-fidelity features :math:`Z_{\\text{LF}}`

    Args:
        Y_LFs_train (np.array): Low-fidelity outputs :math:`Y_{\\text{LF}}` for training input
                                :math:`X`.
        Z_mc (np.array): Low-fidelity feature matrix :math:`Z_{\\text{LF}}^{*}` corresponding to
        sampling input :math:`X^{*}`

    Returns:
        None
    """
    # TODO this is an intermediate solution while the variable class has not been changed to a
    #  more flexible version

    uncertain_parameters = {
        "random_variables": {}
    }  # initialize a dict uncertain parameters to define input_variables of model

    num_lfs = Y_LFs_train.shape[1]  # TODO not a very nice solution but work for now

    # set the random variable for the LFs first
    for counter, value in enumerate(Z_mc.T):  # iterate over all lfs
        if counter < num_lfs - 1:
            key = "LF{}".format(counter)
        else:
            key = "Feat{}".format(counter - num_lfs - 1)

        dummy = {key: {"value": value}}
        uncertain_parameters["random_variables"].update(dummy)  # we assume only 1 column per dim

    # Append random variables for the feature dimensions (random fields are not necessary so far)
    Model.variables = [Variables(uncertain_parameters)]


# ---------------- Some private helper functions ------------------------------------------------
def _linear_scale_a_to_b(data_a, data_b):
    """
    Scale a data vector 'data_a' linearly to the range of data vector 'data_b'.

    Args:
        data_a (np.array): Data vector that should be scaled.
        data_b (np.array): Reference data vector that provides the range for scaling.

    Returns:
       scaled_a (np.array): Scaled data_a vector.

    """
    min_b = np.min(data_b)
    max_b = np.max(data_b)
    scaled_a = min_b + (data_a - np.min(data_a)) * (
        (max_b - min_b) / (np.max(data_a) - np.min(data_a))
    )
    return scaled_a


def _assemble_x_red_stdizd(x_uncorr, coef_mat):
    """
    Assemble and standardize the dimension-reduced input x_red

    Args:
        x_uncorr (np.array):
        coef_mat (np.array):

    Returns:
        X_red_test_stdizd (np.array):

    """
    x_red = np.hstack((x_uncorr, coef_mat))
    X_red_test_stdizd = StandardScaler().fit_transform(x_red)
    return X_red_test_stdizd
