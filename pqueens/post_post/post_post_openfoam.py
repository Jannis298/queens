import glob
from io import StringIO
import os
import numpy as np
import pandas as pd
from pqueens.post_post.post_post import PostPost


class PostPostOpenFOAM(PostPost):
    """ Class for post-post-processing OpenFOAM output

        Attributes:
            time_tol (float):       Tolerance if desired time can not be matched exactly
            target_time (float):    Time at which to evaluate QoI
            skiprows (int):         Number of header rows to skip

    """

    def __init__(self, time_tol, target_time, skiprows, usecols, delete_data_flag, file_prefix):
        """ Init PostPost object

        Args:
            time_tol (float):         Tolerance if desired time can not be matched exactly
            target_time (float):      Time at which to evaluate QoI
            skiprows (int):           Number of header rows to skip
            usecols (list):           Index of columns to use in result file
            delete_data_flag (bool):  Delete files after processing
            file_prefix (str):        Prefix of result files

        """

        super(PostPostOpenFOAM, self).__init__(delete_data_flag, file_prefix)
        self.usecols = usecols
        self.time_tol = time_tol
        self.target_time = target_time
        self.skiprows = skiprows

    @classmethod
    def from_config_create_post_post(cls, options):
        """ Create post_post routine from problem description

        Args:
            options (dict): input options

        Returns:
            post_post: PostPostOpenFOAM object
        """
        post_post_options = options['options']
        time_tol = post_post_options['time_tol']
        target_time = post_post_options['target_time']
        skiprows = post_post_options['skiprows']
        usecols = post_post_options['usecols']
        delete_data_flag = post_post_options['delete_field_data']
        file_prefix = post_post_options['file_prefix']

        return cls(time_tol, target_time, skiprows, usecols, delete_data_flag, file_prefix)

    def read_post_files(self):
        """ Loop over post files in given output directory and extract results """

        prefix_expr = '*' + self.file_prefix + '*'
        time_dir = os.path.join(self.output_dir, str(self.target_time))
        files_of_interest = os.path.join(time_dir, prefix_expr)
        post_files_list = glob.glob(files_of_interest)
        post_out = []

        for filename in post_files_list:
            try:
                post_data = pd.read_csv(
                    filename,
                    sep=r',|\s+',
                    usecols=self.usecols,
                    skiprows=self.skiprows,
                    engine='python',
                )
                data_extract = str(post_data.iloc[0, 0])
                if "(" in data_extract:
                    final_data_extract = data_extract.replace('(', '')
                elif ")" in data_extract:
                    final_data_extract = data_extract.replace(')', '')
                else:
                    final_data_extract = data_extract
                quantity_of_interest = float(final_data_extract)
                post_out = np.append(post_out, quantity_of_interest)
                # very simple error check
                if not post_out:
                    self.error = True
                    self.result = None
                    break
            except IOError:
                self.error = True
                self.result = None
                break
        self.error = False
        self.result = post_out
