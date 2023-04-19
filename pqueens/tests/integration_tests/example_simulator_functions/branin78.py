"""Branin function.

Originates back to [1].

[1]: Dixon, L. C. W., & Szego, G. P. (1978). The global optimization problem: an introduction.
     Towards global optimization, 2, 1-15.
"""
# pylint: disable=invalid-name

import numpy as np


def branin78_lofi(x1, x2, **kwargs):
    """Low-fidelity fidelity Branin function.

    Compute the value of a medium-fidelity version of the Branin function as described
    in [1]. The corresponding high- and low-fidelity versions are implemented
    in *branin_hifi* and *branin_lofi*, respectively.

    **TODO_doc:** Shouldn't the previous sentence be: 'The corresponding high- and medium-fidelity
    versions are implemented in *branin_hifi* and *branin_medfi*, respectively.'

    Args:
        x1 (float): First input parameter
        x2 (float): Second input parameter

    Returns:
        float: Value of low-fidelity Branin function


    References:
        [1] Perdikaris, P. et al., 2017. Nonlinear information fusion algorithms
            for data-efficient multi-fidelity modelling.
            Proceedings of the Royal Society of London A: Mathematical,
            Physical and Engineering Sciences, 473(2198), pp.20160751–16.
    """
    y = branin78_medfi(1.2 * (x1 + 2.0), 1.2 * (x2 + 2.0)) - 3.0 * x2 + 1.0

    return y


def branin78_medfi(x1, x2, **kwargs):
    """Medium fidelity Branin function.

    Compute the value of a medium-fidelity version of Branin function as described
    in [1]. The corresponding high- and low-fidelity versions are implemented
    in *branin_hifi* and *branin_lofi*, respectively.

    Args:
        x1 (float): First input parameter
        x2 (float): Second input parameter

    Returns:
        float: Value of medium fidelity Branin function

    References:
        [1] Perdikaris, P. et al., 2017. Nonlinear information fusion algorithms
            for data-efficient multi-fidelity modelling.
            Proceedings of the Royal Society of London A: Mathematical,
            Physical and Engineering Sciences, 473(2198), pp.20160751–16.
    """
    y = (
        10.0 * np.sqrt(branin78_hifi(x1 - 2.0, x2 - 2))
        + 2.0 * (x1 - 0.5)
        - 3.0 * (3.0 * x2 - 1.0)
        - 1.0
    )

    return y


def branin78_hifi(x1, x2, **kwargs):
    """High-fidelity Branin function.

    Compute value of high fidelity version of Branin function as described
    in [1]. The corresponding medium- and low-fidelity versions are implemented
    in *branin_medfi* and *branin_lofi*, respectively.

    Args:
        x1 (float): First input parameter [−5, 10]
        x2 (float): Second input parameter [0, 15]

    Returns:
        float: Value of high-fidelity Branin function

    References:
        [1] Perdikaris, P. et al., 2017. Nonlinear information fusion algorithms
            for data-efficient multi-fidelity modelling.
            Proceedings of the Royal Society of London A: Mathematical,
            Physical and Engineering Sciences, 473(2198), pp.20160751–16.
    """
    result = (
        (-1.275 * x1**2 / np.pi**2 + 5.0 * x1 / np.pi + x2 - 6.0) ** 2
        + (10.0 - 5.0 / (4.0 * np.pi)) * np.cos(x1)
        + 10.0
    )

    return result
