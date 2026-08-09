import numpy as np
import math
from cnu_python.cnu_int4 import cnu_hardware_int4
from vnu_python.vnu_int4 import vnu_hardware_int4
from check_matrix_generator import get_H_x, get_H_z

# ---- define check matrix ----
H = get_H_x()

num_check_node, num_variable_node = H.shape

print(num_check_node)
print(num_variable_node)