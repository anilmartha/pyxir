#
# Copyright 2020 Xilinx Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for testing the pyxir TF executor


"""

import unittest
import numpy as np

from pyxir.runtime import base
from pyxir.graph.layer import xlayer
from pyxir.graph.io import xlayer_io

from pyxir.runtime.tensorflow.x_2_tf_registry import X_2_TF


class TestRuntimeTF(unittest.TestCase):

    def test_constant(self):
        C = np.array([0.1, 0.05], dtype=np.float32)

        X = xlayer.XLayer(
            name='c1',
            type=['Constant'],
            shapes=[2],
            sizes=[2],
            bottoms=[],
            data=[C],
            tops=[],
            attrs={},
            targets=[]
        )

        input_shapes = {}
        params = {}
        layers = X_2_TF['Constant'](X, input_shapes, params)
        assert len(layers) == 1

        outpt = layers[0].forward_exec([])

        np.testing.assert_array_almost_equal(outpt, C)

    def test_variable(self):
        V = np.array([0.1, 0.05], dtype=np.float32)

        X = xlayer.XLayer(
            name='var',
            type=['Variable'],
            shapes=[2],
            sizes=[2],
            bottoms=[],
            tops=[],
            attrs={
                # 'init_value': V,
                'dtype': 'float32'
            },
            data=[V],
            targets=[]
        )

        input_shapes = {}
        params = {}
        layers = X_2_TF['Variable'](X, input_shapes, params)
        assert(len(layers) == 1)

        inputs = {}
        for layer in layers:
            inpts = [inputs[name] for name in layer.inputs]
            outpt = layer.forward_exec(inpts)

        np.testing.assert_array_almost_equal(outpt, V)
