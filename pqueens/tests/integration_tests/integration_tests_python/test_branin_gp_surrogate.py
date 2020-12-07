import os
import pickle
import numpy as np
import pytest

from pqueens.main import main


def test_branin_gp_surrogate(inputdir, tmpdir, expected_pdf):
    """ Test case for GP based surrogate model """
    arguments = [
        '--input=' + os.path.join(inputdir, 'branin_gp_surrogate.json'),
        '--output=' + str(tmpdir),
    ]

    main(arguments)
    result_file = str(tmpdir) + '/' + 'xxx.pickle'
    with open(result_file, 'rb') as handle:
        results = pickle.load(handle)

    np.testing.assert_array_almost_equal(results["pdf_estimate"]["mean"], expected_pdf, decimal=4)


@pytest.fixture()
def expected_pdf():
    pdf = [
        3.1776e-04,
        2.1679e-03,
        7.6932e-03,
        1.2928e-02,
        1.0083e-02,
        4.2060e-03,
        1.4365e-03,
        7.5351e-04,
        3.7115e-04,
        7.0949e-05,
    ]
    return np.array(pdf)
