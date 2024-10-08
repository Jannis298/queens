"""Adam optimizer."""

import logging

import numpy as np

from queens.stochastic_optimizers.stochastic_optimizer import StochasticOptimizer
from queens.utils.iterative_averaging_utils import ExponentialAveraging

_logger = logging.getLogger(__name__)


class Adam(StochasticOptimizer):
    r"""Adam stochastic optimizer [1].

    References:
        [1] Kingma and Ba. "Adam: A Method for Stochastic Optimization".  ICLR 2015. 2015.

    Attributes:
        beta_1 (float):  :math:`\beta_1` parameter as described in [1].
        beta_2 (float):  :math:`\beta_2` parameter as described in [1].
        m (ExponentialAveragingObject): Exponential average of the gradient.
        v (ExponentialAveragingObject): Exponential average of the gradient momentum.
        eps (float): Nugget term to avoid a division by values close to zero.
    """

    _name = "Adam Stochastic Optimizer"

    def __init__(
        self,
        learning_rate,
        optimization_type,
        rel_l1_change_threshold,
        rel_l2_change_threshold,
        clip_by_l2_norm_threshold=np.inf,
        clip_by_value_threshold=np.inf,
        max_iteration=1e6,
        beta_1=0.9,
        beta_2=0.999,
        eps=1e-8,
    ):
        """Initialize optimizer.

        Args:
            learning_rate (float): Learning rate for the optimizer
            optimization_type (str): "max" in case of maximization and "min" for minimization
            rel_l1_change_threshold (float): If the L1 relative change in parameters falls below
                                             this value, this criterion catches.
            rel_l2_change_threshold (float): If the L2 relative change in parameters falls below
                                             this value, this criterion catches.
            clip_by_l2_norm_threshold (float): Threshold to clip the gradient by L2-norm
            clip_by_value_threshold (float): Threshold to clip the gradient components
            max_iteration (int): Maximum number of iterations
            beta_1 (float): :math:`beta_1` parameter as described in [1]
            beta_2 (float): :math:`beta_1` parameter as described in [1]
            eps (float): Nugget term to avoid a division by values close to zero
        """
        # pylint:disable=duplicate-code
        super().__init__(
            learning_rate=learning_rate,
            optimization_type=optimization_type,
            rel_l1_change_threshold=rel_l1_change_threshold,
            rel_l2_change_threshold=rel_l2_change_threshold,
            clip_by_l2_norm_threshold=clip_by_l2_norm_threshold,
            clip_by_value_threshold=clip_by_value_threshold,
            max_iteration=max_iteration,
        )
        self.beta_1 = beta_1
        self.beta_2 = beta_2
        self.m = ExponentialAveraging(coefficient=beta_1)
        self.v = ExponentialAveraging(coefficient=beta_2)
        self.eps = eps

    def scheme_specific_gradient(self, gradient):
        """Adam gradient computation.

        Args:
            gradient (np.array): Gradient

        Returns:
            gradient (np.array): Adam gradient
        """
        if self.iteration == 0:
            self.m.current_average = np.zeros(gradient.shape)
            self.v.current_average = np.zeros(gradient.shape)

        m_hat = self.m.update_average(gradient)
        v_hat = self.v.update_average(gradient**2)
        m_hat /= 1 - self.beta_1 ** (self.iteration + 1)
        v_hat /= 1 - self.beta_2 ** (self.iteration + 1)
        gradient = m_hat / (v_hat**0.5 + self.eps)
        return gradient
