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
Module for transforming Relay L2 operators to XLayer objects

L2: Convolution related operators


"""

import math
import logging
import numpy as np

import tvm

from pyxir import graph
from pyxir.graph.layer import xlayer_factory as xlf

from .relay_2_xlayer_registry import register_relay_2_xlayer_converter,\
    register_relay_2_xlayer_converter_base

logger = logging.getLogger("pyxir")


@register_relay_2_xlayer_converter('nn.avg_pool2d')
def nn_avg_pool2d(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                  **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.avg_pool2d
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - strides (tuple of int, optional)
            The strides of pooling.
        - padding (tuple of int, optional)
            The padding for pooling.
        - layout (str, optional)
            Layout of the input.
        - ceil_mode (bool, optional)
            To enable or disable ceil while pooling.
        - count_include_pad (bool, optional)
            To include padding to compute the average.
    """
    if expr in net:
        logger.debug("MEMORY: NN AVG POOL2D")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    pool_size = [int(e) for e in list(expr.attrs.pool_size)]
    strides = [int(e) for e in list(expr.attrs.strides)]
    padding = [int(e) for e in list(expr.attrs.padding)]
    data_layout = str(expr.attrs.layout)
    ceil_mode = bool(expr.attrs.ceil_mode)
    count_include_pad = bool(expr.attrs.count_include_pad)

    # if count_include_pad:
    #     logger.debug("Padding: {}".format(padding))
    #     raise NotImplementedError("Including padding in avg pool2d
    #                               " computation"
    #                               " is not supported")

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__
    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    logger.debug("nn_avg_pool2d: {}".format(""))

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create XLayer

    pool_type = 'Avg'

    # Convert NHWC -> NCHW TODO: remove data layout
    if data_layout == 'NHWC':
        t_name = 'nn_avg_pool2d_NHWC>NCHW-' + str(hash(expr))
        data_layer.tops.append(t_name)

        data_layer = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, data_layer, [0, 3, 1, 2])

        schedule.append(t_name)
        net[t_name] = data_layer

    # Create name
    op_name = 'nn_avg_pool2d-' + str(hash(expr))

    X = xlf.get_xop_factory_func('Pooling')(
        op_name, data_layer, pool_type, pool_size,
        strides, padding, 'NCHW',
        ceil_mode, count_include_pad,
        relay_id=[hash(expr)])
    logger.debug("-- outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops
    data_layer.tops.append(X.name)

    # Convert to NCHW -> NHWC TODO: remove data layout
    if data_layout == 'NHWC':
        schedule.append(X.name)
        net[X.name] = X

        t_name = 'nn_avg_pool2d_NCHW>NHWC-' + str(hash(expr))
        X.tops.append(t_name)

        res_X = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, X, [0, 2, 3, 1])
    else:
        res_X = X

    return res_X


@register_relay_2_xlayer_converter('nn.batch_flatten')
def nn_batch_flatten(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                     **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], int, Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.batch_flatten
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
    """
    if expr in net:
        logger.debug("MEMORY: NN BATCH FLATTEN")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__

    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    logger.debug("nn_batch_flatten: {}".format(""))

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create ParametersLayer

    # Create names
    op_name = 'nn_batch_flatten-' + str(hash(expr))

    P = xlf.get_xop_factory_func('Flatten')(op_name, data_layer,
                                            relay_id=[hash(expr)])

    # !Important: set input layer tops:
    data_layer.tops.append(op_name)

    return P


@register_relay_2_xlayer_converter('nn.conv2d')
def nn_conv2d(expr, params, schedule, net, op_idx, RELAY_2_XLAYER, **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.conv2d
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - weight (tvm.relay.Expr)
            The weight expressions.
        - strides (tuple of int, optional)
            The strides of convolution.
        - padding (tuple of int, optional)
            The padding of convolution on both sides of inputs before
            convolution.
        - dilation (tuple of int, optional)
            Specifies the dilation rate to be used for dilated convolution.
        - groups (int, optional)
            Number of groups for grouped convolution.
        - channels (int, optional)
            Number of output channels of this convolution.
        - kernel_size (tuple of int, optional)
            The spatial of the convolution kernel.
        - data_layout (str, optional)
            Layout of the input.
        - kernel_layout (str, optional)
            Layout of the weight.
        - out_layout (str, optional)
            Layout of the output, by default, out_layout is the same as
            data_layout
        - out_dtype (str, optional)
            Specifies the output data type for mixed precision conv2d.
    """
    if expr in net:
        logger.debug("MEMORY: CONV2D")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    # HW
    kernel_size = [int(e) for e in list(expr.attrs.kernel_size)]
    strides = [int(e) for e in list(expr.attrs.strides)]
    padding = [int(e) for e in list(expr.attrs.padding)]
    dilation = [int(e) for e in list(expr.attrs.dilation)]
    groups = int(expr.attrs.groups) if expr.attrs.groups is not None else 1
    channels = int(expr.attrs.channels) if expr.attrs.channels is not None \
        else None
    data_layout = str(expr.attrs.data_layout)
    kernel_layout = str(expr.attrs.kernel_layout)
    # out_layout = str(expr.attrs.out_layout)
    # out_dtype = str(expr.attrs.out_dtype)

    data_expr, data_expr_class = \
        expr.args[0], expr.args[0].__class__.__name__
    weights_expr, weights_expr_class = \
        expr.args[1], expr.args[1].__class__.__name__

    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)
    weights_layer = RELAY_2_XLAYER[weights_expr_class](weights_expr, params,
                                                       schedule, net, op_idx,
                                                       RELAY_2_XLAYER,
                                                       **kwargs)

    logger.debug("nn_conv2d")

    assert(len(data_layer.shapes) == 4)
    assert(weights_layer.data is not None)

    # Update schedule with child layers
    # ! We don't add weights layer as this weight is precomputed
    # TODO What if weights layer can't be precomputed
    # TODO WHat if weights layer is shared
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create XLayer

    # Convert NHWC -> NCHW TODO: remove data layout
    if data_layout == 'NHWC':
        t_name = 'nn_conv2d_NHWC>NCHW-' + str(hash(expr))
        data_layer.tops.append(t_name)

        data_layer = \
            xlf.get_xop_factory_func('Transpose', internal=True)(
                t_name, data_layer, [0, 3, 1, 2])

        schedule.append(t_name)
        net[t_name] = data_layer

    # Create name
    op_name = 'nn_conv2d-' + str(hash(expr))

    # [pad_h, pad_w] or [pad_h_top, pad_h_bottom, pad_w_left, pad_w_right]
    xpadding = padding if len(padding) == 2\
        else [padding[i] for i in [0, 2, 1, 3]]

    X = xlf.get_xop_factory_func('Convolution')(
        op_name, data_layer, weights_layer,
        kernel_size, strides, xpadding, dilation, groups,
        channels, 'NCHW', kernel_layout,
        relay_id=[hash(expr)])

    logger.debug("--outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops
    data_layer.tops.append(X.name)

    # Convert to NCHW -> NHWC TODO: remove data layout
    if data_layout == 'NHWC':
        schedule.append(X.name)
        net[X.name] = X

        t_name = 'nn_conv2d_NCHW>NHWC-' + str(hash(expr))
        X.tops.append(t_name)

        res_X = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, X, [0, 2, 3, 1])
    else:
        res_X = X

    return res_X


@register_relay_2_xlayer_converter('nn.conv2d_transpose')
def nn_conv2d_transpose(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                        **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    Convert Relay nn.conv2d_transpose to Conv2DTranspose XLayer

    Relay
    -----
    Type: tvm.relay.nn.conv2d_transpose
    Ref: https://docs.tvm.ai/langref/relay_op.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - weight (tvm.relay.Expr)
            The weight expressions.
        - strides (Tuple[int], optional)
            The strides of convolution.
        - padding (Tuple[int], optional)
            The padding of convolution on both sides of inputs.
        - dilation (Tuple[int], optional)
            Specifies the dilation rate to be used for dilated convolution.
        - channels (int, optional)
            Number of output channels of this convolution.
        - kernel_size (tuple of int, optional)
            The spatial of the convolution kernel.
        - groups (int, optional)
            Number of groups for grouped convolution.
        - data_layout (str, optional)
            Layout of the input.
        - kernel_layout (str, optional)
            Layout of the weight.
        - out_layout (Optional[str])
            Layout of the output, by default, out_layout is the same as
            data_layout
        - output_padding (Tuple[int], optional)
            Additional zero-padding to be added to one side of the output.
        - out_dtype (str, optional)
            Specifies the output data type for mixed precision conv2d.
    """
    if expr in net:
        logger.debug("MEMORY: CONV2D_TRANSPOSE")
        return net[expr]

    # HW
    kernel_size = [int(e) for e in list(expr.attrs.kernel_size)]
    strides = [int(e) for e in list(expr.attrs.strides)]
    padding = [int(e) for e in list(expr.attrs.padding)]
    dilation = [int(e) for e in list(expr.attrs.dilation)]
    groups = int(expr.attrs.groups) if expr.attrs.groups is not None else 1
    channels = int(expr.attrs.channels) if expr.attrs.channels is not None \
        else None
    data_layout = str(expr.attrs.data_layout)
    kernel_layout = str(expr.attrs.kernel_layout)
    # out_layout = str(expr.attrs.out_layout)
    # out_dtype = str(expr.attrs.out_dtype)

    data_expr, data_expr_class = \
        expr.args[0], expr.args[0].__class__.__name__
    weights_expr, weights_expr_class = \
        expr.args[1], expr.args[1].__class__.__name__

    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)
    weights_layer = RELAY_2_XLAYER[weights_expr_class](weights_expr, params,
                                                       schedule, net, op_idx,
                                                       RELAY_2_XLAYER,
                                                       **kwargs)

    logger.debug("nn_conv2d_transpose")

    logger.debug("-- kernel_size {}".format(kernel_size))
    logger.debug("-- strides {}, {}".format(strides, type(strides[0])))
    logger.debug("-- padding {}".format(padding))
    logger.debug("-- dilation {}".format(dilation))
    logger.debug("-- groups {}, {}".format(groups, type(groups)))
    logger.debug("-- channels {}".format(channels))
    logger.debug("-- data_layout {}".format(data_layout))
    logger.debug("-- kernel_layout {}".format(kernel_layout))

    assert len(data_layer.shapes) == 4
    assert weights_layer.data is not None

    # Update schedule with child layers
    # ! We don't add weights layer as this weight is precomputed
    # TODO What if weights layer can't be precomputed
    # TODO WHat if weights layer is shared
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create ParametersLayer

    # TODO: NHWC
    # Create name
    op_name = 'nn_conv2d_transpose-' + str(hash(expr))

    # [pad_h, pad_w] or [pad_h_top, pad_h_bottom, pad_w_left, pad_w_right]
    xpadding = padding if len(padding) == 2\
        else [padding[i] for i in [0, 2, 1, 3]]

    X = xlf.get_xop_factory_func('Conv2DTranspose')(
        op_name, data_layer, weights_layer, kernel_size,
        strides, xpadding,
        dilation,
        groups, channels,
        data_layout, kernel_layout,
        relay_id=[hash(expr)]
    )
    logger.debug("--outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops:
    data_layer.tops.append(op_name)

    return X


@register_relay_2_xlayer_converter('nn.global_avg_pool2d')
def nn_global_avg_pool2d(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                         **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.global_avg_pool2d
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - layout (str, optional)
            Layout of the input.
    """
    if expr in net:
        logger.debug("MEMORY: GLOBAL AVG POOL2D")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    data_layout = str(expr.attrs.layout)

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__
    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    logger.debug("nn_global_avg_pool2d")

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create XLayers

    # Convert NHWC -> NCHW TODO: remove data layout
    if data_layout == 'NHWC':
        t_name = 'nn_global_avg_pool2d_NHWC>NCHW-' + str(hash(expr))
        data_layer.tops.append(t_name)

        data_layer = \
            xlf.get_xop_factory_func('Transpose', internal=True)(
                t_name, data_layer, [0, 3, 1, 2])

        schedule.append(t_name)
        net[t_name] = data_layer

    # Create name
    op_name = 'nn_global_avg_pool2d-' + str(hash(expr))

    pool_type = 'Avg'
    X = xlf.get_xop_factory_func('GlobalPooling')(
        op_name, data_layer, pool_type, 'NCHW',
        relay_id=[hash(expr)])
    logger.debug("-- outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops
    data_layer.tops.append(X.name)

    # Convert to NCHW -> NHWC TODO: remove data layout
    if data_layout == 'NHWC':
        schedule.append(X.name)
        net[X.name] = X

        t_name = 'nn_global_avg_pool2d_NCHW>NHWC-' + str(hash(expr))
        X.tops.append(t_name)

        res_X = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, X, [0, 2, 3, 1])
    else:
        res_X = X

    return res_X


@register_relay_2_xlayer_converter('nn.global_max_pool2d')
def nn_global_max_pool2d(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                         **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO Overlap with globale_avg_pool2d

    Relay
    -----
    Type: tvm.relay.op.nn.nn.global_max_pool2d
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - layout (str, optional)
            Layout of the input.
    """
    if expr in net:
        logger.debug("MEMORY: GLOBAL MAX POOL2D")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    data_layout = str(expr.attrs.layout)

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__
    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    logger.debug("nn_global_max_pool2d")

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create XLayers

    # Convert NHWC -> NCHW TODO: remove data layout
    if data_layout == 'NHWC':
        t_name = 'nn_global_max_pool2d_NHWC>NCHW-' + str(hash(expr))
        data_layer.tops.append(t_name)

        data_layer = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, data_layer, [0, 3, 1, 2])

        schedule.append(t_name)
        net[t_name] = data_layer

    # Create name
    op_name = 'nn_global_max_pool2d-' + str(hash(expr))

    pool_type = 'Max'
    X = xlf.get_xop_factory_func('GlobalPooling')(
        op_name, data_layer, pool_type, 'NCHW',
        relay_id=[hash(expr)])
    logger.debug("-- outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops:
    data_layer.tops.append(op_name)

    # Convert to NCHW -> NHWC TODO: remove data layout
    if data_layout == 'NHWC':
        schedule.append(X.name)
        net[X.name] = X

        t_name = 'nn_global_max_pool2d_NCHW>NHWC-' + str(hash(expr))
        X.tops.append(t_name)

        res_X = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, X, [0, 2, 3, 1])
    else:
        res_X = X

    return res_X


@register_relay_2_xlayer_converter('nn.max_pool2d')
def nn_max_pool2d(expr, params, schedule, net, op_idx, RELAY_2_XLAYER,
                  **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.max_pool2d
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - strides (tuple of int, optional)
            The strides of pooling.
        - padding (tuple of int, optional)
            The padding for pooling.
        - layout (str, optional)
            Layout of the input.
        - ceil_mode (bool, optional)
            To enable or disable ceil while pooling.
    """
    if expr in net:
        logger.debug("MEMORY: MAX POOL2D")
        return net[expr]

    pool_size = [int(e) for e in list(expr.attrs.pool_size)]
    strides = [int(e) for e in list(expr.attrs.strides)]
    padding = [int(e) for e in list(expr.attrs.padding)]
    data_layout = str(expr.attrs.layout)
    ceil_mode = bool(expr.attrs.ceil_mode)

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__
    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    logger.debug("nn_max_pool2d")

    # logger.debug("strides", type(strides))
    # logger.debug("padding", padding)
    # logger.debug("layout", layout)
    # logger.debug("ceil_mode", ceil_mode)
    # logger.debug("count_include_pad", count_include_pad)

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create XLayers

    pool_type = 'Max'

    # Convert NHWC -> NCHW TODO: remove data layout
    if data_layout == 'NHWC':
        t_name = 'nn_max_pool2d_NHWC>NCHW-' + str(hash(expr))
        data_layer.tops.append(t_name)

        data_layer = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, data_layer, [0, 3, 1, 2])

        schedule.append(t_name)
        net[t_name] = data_layer

    # Create name
    op_name = 'nn_max_pool2d-' + str(hash(expr))

    logger.debug("-- name: {}".format(op_name))

    X = xlf.get_xop_factory_func('Pooling')(
        op_name, data_layer, pool_type, pool_size,
        strides, padding, 'NCHW',
        ceil_mode, False,
        relay_id=[hash(expr)])
    logger.debug("-- outshape: {}".format(list(X.shapes)))

    # !Important: set input layer tops
    data_layer.tops.append(X.name)

    # Convert to NCHW -> NHWC TODO: remove data layout
    if data_layout == 'NHWC':
        schedule.append(X.name)
        net[X.name] = X

        t_name = 'nn_max_pool2d_NCHW>NHWC-' + str(hash(expr))
        X.tops.append(t_name)

        res_X = xlf.get_xop_factory_func('Transpose', internal=True)(
            t_name, X, [0, 2, 3, 1])
    else:
        res_X = X

    return res_X


@register_relay_2_xlayer_converter('nn.pad')
def nn_pad(expr, params, schedule, net, op_idx, RELAY_2_XLAYER, **kwargs):
    # type: (tvm.relay.expr.Expr, Dict[str, numpy.ndarray], List[Expr],
    #   Dict[int, XLayer], Dict[str, int], Dict[str, Function]) -> XLayer
    """
    TODO

    Relay
    -----
    Type: tvm.relay.op.nn.nn.batch_flatten
    Ref: https://docs.tvm.ai/api/python/relay/nn.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator
        - pad_width (tuple of <tuple of <int>>, required)
            Number of values padded to the edges of each axis, in the format
            of ((before_1, after_1), …, (before_N, after_N))
        - pad_value (float, optional, default=0.0)
            The value used for padding
    """
    if expr in net:
        logger.debug("MEMORY: NN PAD")
        # This expressions is already transformed so we reuse that one
        return net[expr]

    data_expr, data_expr_class = expr.args[0], expr.args[0].__class__.__name__
    data_layer = RELAY_2_XLAYER[data_expr_class](data_expr, params, schedule,
                                                 net, op_idx, RELAY_2_XLAYER,
                                                 **kwargs)

    # TODO create a class for doing this kind of data retrieval and parsing
    pad_width = [[int(e) for e in t] for t in expr.attrs.pad_width]
    pad_value = float(expr.attrs.pad_value)

    logger.debug("nn_pad: {}".format(""))
    logger.debug("-- pad width: {}".format(pad_width))
    logger.debug("-- pad value: {}".format(pad_value))

    # Update schedule with input data layer
    if data_expr not in net:
        schedule.append(data_expr)
        net[data_expr] = data_layer

    # Create ParametersLayer
    # data_layout = kwargs['data_layout']

    # Create name
    op_name = 'nn_pad-' + str(hash(expr))
    logger.debug("-- pad input shape: {}".format(data_layer.shapes))

    X = xlf.get_xop_factory_func('Pad')(op_name, data_layer, pad_width,
                                        pad_value,
                                        relay_id=[hash(expr)])

    # !Important: set input layer tops:
    data_layer.tops.append(op_name)

    return X


@register_relay_2_xlayer_converter_base('nn.upsampling')
def nn_upsampling(op_name, expr, in_xlayers):
    # type: (str, tvm.relay.expr.Expr, List[XLayer]) -> XLayer
    """
    2D Upsampling

    Relay
    -----
    Type: tvm.relay.split
    Desc:
        Upsampling.

        This operator takes data as input and does 2D scaling to the given
        scale factor. In the default case, where the data_layout is NCHW with
        data of shape (n, c, h, w) out will have a shape
        (n, c, h*scale_h, w*scale_w)

        method indicates the algorithm to be used while calculating the out
        value and method can be one of (bilinear, nearest_neighbor, bicubic)

    Ref: https://docs.tvm.ai/langref/relay_op.html
    Parameters:
        - data (tvm.relay.Expr)
            The input data to the operator.
        - scale_h (tvm.relay.Expr)
            The scale factor for height upsampling.
        - scale_w (tvm.relay.Expr)
            The scale factor for width upsampling.
        - layout (str, optional)
            Layout of the input.
        - method (str, optional)
            Scale method to used [nearest_neighbor, bilinear, bicubic].
        - align_corners (bool, optional)
            Whether to keep corners in proper place.
    """
    scale_h = float(expr.attrs.scale_h)
    scale_w = float(expr.attrs.scale_w)
    layout = str(expr.attrs.layout)
    method = str(expr.attrs.method)
    align_corners = bool(expr.attrs.align_corners)

    X = xlf.get_xop_factory_func('Upsampling2D')(op_name,
                                                 in_xlayers,
                                                 scale_h=scale_h,
                                                 scale_w=scale_w,
                                                 data_layout=layout,
                                                 method=method,
                                                 align_corners=align_corners,
                                                 relay_id=[hash(expr)])
    logger.debug("-- outshape: {}".format(list(X.shapes)))

    return X
