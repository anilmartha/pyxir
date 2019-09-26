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

""" Base module for running XGraphs """

import abc
import copy
import logging

from pyxir.shared import fancy_logging
from pyxir.shared import QuantParams

logger = logging.getLogger("pyxir")
fancy_logger = fancy_logging.getLogger("pyxir")


class BaseRuntime(object):

    __metaclass__ = abc.ABCMeta

    """
    Responsible for executing a graph

    Arguments:
    ----------
    network: List[XLayer]
        the network (list of operations) to be executed
    params: Dict[str,numpy.ndarray]
        the network parameters (weights, biases)
    device: str (optional, default = 'cpu')
        the target device for graph execution (only 'cpu' supported
        at the moment)
    batch_size: int
        the batch size for the runtime graph, default is -1 (dynamic)

    Attributes:
    -----------
    net: List[RtLayer]
        a list of computational steps in the model network
    inputs: List[RtLayer]
        a list of the network input layers
    outputs: List[RtLayer]
        a list of the network output layers
    params: dict
        the parameters of the graph by name
    device: str
        the target device for graph execution
    batch_size: int
        the batch size for the runtime graph, default is -1 (dynamic)
    """

    def __init__(self,
                 name,
                 network,
                 params,
                 device='cpu',
                 batch_size=-1):
        # type: (str, List[XLayer], Dict[str,numpy.ndarray], str)
        self.name = name
        self.params = params
        self.device = device
        self.batch_size = batch_size

        self._init_net(network, self.params)

        self.name_to_nodes = {
            op.name: op for op in network
        }

    @abc.abstractmethod
    def _xfdnn_op_to_exec_op(self, op_type):
        # type: (str) -> function
        """
        Abstract method

        Returns a function of type:
        (XLayer, Dict[str,List[int]], Dict[str,numpy.ndarray], Dict[str,Dict])
            -> List[rt_layer.RtLayer]
        that takes in a parameters layer object, inputs shapes dict, params
        dict and quantization parameters dict and outputs and returns a list
        of executable RtLayer objects

        TODO: make the returned function more formal
        """
        raise NotImplementedError("")

    def _init_net(self, network, params):
        # type: (List[XLayer], Dict[str,numpy.ndarray]) -> None

        fancy_logger.banner("INIT NET")

        self.net = []
        self.inputs = []
        self.outputs = []

        input_shapes = {}

        for op_idx, op in enumerate(network):

            logger.info("-----------------------")
            logger.info("Op idx: {}, op_name: {}, op_type: {} op shapes: {}"
                        .format(op_idx, op.name, op.type, op.shapes))
            # logger.info(op)

            xfdnn_layers = self._xfdnn_op_to_exec_op(op.type[0])(
                op, input_shapes, params, batch_size=self.batch_size)

            logger.debug("Add input shape: {} : {}"
                         .format(op.name, xfdnn_layers[-1].shape))
            input_shapes[op.name] = xfdnn_layers[-1].shape

            self.net = self.net + xfdnn_layers
            # self.params.update(params)

            if op.type[0] in ['Input', 'StrInput'] and op.name not in params:
                self.inputs.append(xfdnn_layers[0])
            if 'Output' in op.type:
                self.outputs.append(xfdnn_layers[0])

    def run_stepwise(self, inputs, stop=None):
        # type: (dict, str) -> (int, str, dict, numpy.ndarray, numpy.ndarray)
        """
        TODO Remove stepwise execution (for tensorflow)?
        """
        fancy_logger.banner("RUN NET STEPWISE")

        inputs.update(self.params)

        for layer_idx, layer in enumerate(self.net):

            # logger.info("-----------------------")
            # logger.info("Run layer idx: {}, op_name: {}"
            #   .format(layer_idx, layer.name))

            inpts = [inputs[name] for name in layer.inputs]

            outpt = layer.forward_exec(inpts)

            # TODO: can we make this more elegant?
            if layer.type in ['Convolution']:
                quant_outpt = layer.get_output_for_quantization(inpts)
            else:
                quant_outpt = outpt

            # TODO: remove unnecessary data as we keep track of
            #   the outputs of all layers
            inputs[layer.name] = outpt

            yield (
                layer_idx,
                layer,
                inpts,
                outpt,
                quant_outpt
            )

            if stop is not None and layer.name == stop:
                break

    def run(self, inputs, outputs=[], stop=None, force_stepwise=True):
        # (Dict[str,numpy.ndarray], List[str], str, bool)
        #   -> (List[numpy.ndarray]/numpy.ndarray)
        """
        Execute this computational graph on the given inputs.

        Arguments
        ---------
        inputs: Dict[str, numpy.ndarray]
            the inputs for this executable computational graph
        outputs: List[str]
            the output(s) to be returned
        stop: str
            the operation at which to stop running
        force_stepwise: bool (default: True)
            whether to force a stepwise calculation of the computational graph
            on the provided inputs
            ! Unused because this runtime always used stepwise calculations

        Returns
        -------
        res: List[numpy.ndarray]
            a list of outputs if requested, otherwise list containing the last
            output
        """
        fancy_logger.banner("RUN NET")

        inputs.update(self.params)
        res = {}
        for layer_idx, layer in enumerate(self.net):

            logger.info("-----------------------")
            logger.info("Run layer idx: {}, op_name: {}"
                        .format(layer_idx, layer.name))
            logger.info("Inputs: {}".format(layer.inputs))
            inpts = [inputs[name] for name in layer.inputs]

            outpt = layer.forward_exec(inpts)

            # TODO: remove unnecessary data as we keep track of
            #   the outputs of all layers
            inputs[layer.name] = outpt

            if layer.name in outputs:
                res[layer.name] = outpt

            if stop is not None and layer.name == stop:
                break

        if len(outputs) == 0:
            res['output'] = outpt

        return [res[outpt] for outpt in outputs] \
            if len(outputs) > 0 else [res['output']]

    @abc.abstractmethod
    def optimize(self, inputs, debug=False):
        # (Dict[str, numpy.ndarray], bool) ->
        #    Tuple(dict, List[numpy.ndarray]/numpy.ndarray)
        raise NotImplementedError("")

    # SETTERS/GETTERS #

    def get_input_names(self):
        # type: () -> List[str]
        return [layer.name for layer in self.inputs]

    def get_input_shapes(self):
        # type: () -> List[List[int]]
        return [layer.shape for layer in self.inputs]

    def get_ouput_names(self):
        # type: () -> List[str]
        return [layer.name for layer in self.outputs]

    def get_output_shapes(self):
        # type: () -> List[List[int]]
        return [layer.shape for layer in self.outputs]

    def get_node(self, node_name):
        # (str) -> dict
        """
        Returns the node with provided name if it exists else throws a KeyError
        """
        # TODO: Return
        return self.name_to_nodes[node_name]

    def get_input_node_names(self, node_name):
        # (str) -> list
        """
        Returns a list of dictionaries containing the inputs' node information
        """
        node = self.get_node(node_name)
        return node.bottoms

    def get_output_node_names(self, node_name):
        # (str) -> list
        """
        Returns a list of dictionaries containing the outputs' node information
        """
        node = self.get_node(node_name)
        return node.tops
