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
Module for generic subgraph build function


"""

import os
import numpy as np
import logging

from pyxir.graph.algorithms.topological_sorting import sort_topologically
from pyxir.shared import fancy_logging

from pyxir.graph.layer.xlayer import XLayer, defaultXLayer
from pyxir.graph.xgraph_factory import XGraphFactory
from pyxir.graph.partitioning.xgraph_partitioner import XGraphPartitioner
from pyxir.graph.optimization.optimizers.transposes_optimizer \
    import XGraphTransposesOptimizer
from pyxir.graph.transformers.layout_transformation_pass \
    import XGraphLayoutTransformationPass


logger = logging.getLogger('pyxir')
fancy_logger = fancy_logging.getLogger("pyxir")


def find_indices(lst, condition):
    return [(i, elem) for i, elem in enumerate(lst) if condition(elem)]


def xgraph_build_func(xgraph,
                      target,
                      xtype,
                      layout='NCHW',
                      **kwargs):

    fancy_logger.banner("Subgraph build func, target: {}, layout: {}"
                        .format(target, layout))
     
    compiler_output = xgraph.get_compiler_output() if xgraph.is_compiled() \
        else None
    compiler_output_keys = list(compiler_output.keys()) \
        if compiler_output else []
    logger.debug("Compiler output keys: {}".format(compiler_output_keys))
  
    if layout not in ['NCHW', 'NHWC']:
        raise ValueError("Supported layouts are [NCHW, NHWC] but got: {}"
                         .format(layout))

    layout_transform_pass = \
        XGraphLayoutTransformationPass(layout, target=target)
    xgraph = layout_transform_pass.execute(xgraph, subgraphs_only=False)

    xgraph_factory = XGraphFactory()
    xgraph_partitioner = XGraphPartitioner()

    subgraphs = {
        xp.name: xp for xp in xgraph_partitioner.get_subgraphs(xgraph)
    }

    # Retrieve CompilerOutput if available
    # compiler_output = xgraph.get_compiler_output() if xgraph.is_compiled() \
    #     else None
    # compiler_output_keys = list(compiler_output.keys()) \
    #     if compiler_output else []
    # logger.debug("Compiler output keys: {}".format(compiler_output_keys))
    # Keep track of the visited partitions/subgraphs and the layers
    #   inside the partition
    visited_xps = {}

    # Keep track of the subgraph output tensors and the corresponding
    #   new layers (TupleGetItem or Transpose)
    xp_out_tensors_2_layers = {}

    net = []
    for X in xgraph.get_layers():

        if X.subgraph is not None and X.subgraph not in visited_xps:

            Xp = subgraphs[X.subgraph]

            if 'target' in Xp.attrs and Xp.attrs['target'] == target:

                visited_xps[Xp.name] = set([X.name])

                logger.debug("XSHAPES: {}".format(X.shapes))

                bottoms = Xp.bottoms

                # Keep track of subgraph input and output names
                sub_xgraph = xgraph_factory.build_from_xlayer(Xp.subgraph_data)

                input_names = Xp.attrs['input_names'][:]
                output_names = Xp.attrs['output_names'][:]
                input_layers = \
                    [sub_xgraph.get(in_name) for in_name in input_names]
                output_layers = \
                    [sub_xgraph.get(out_name) for out_name in output_names]

                attrs = {
                    'input_names': input_names,
                    'output_names': output_names,
                    'input_layers': {
                        il.name: il.layer[:] for il in input_layers
                    },
                    'output_layers': {
                        ol.name: ol.layer[:] for ol in output_layers
                    }
                }
                for k, v in kwargs.items():
                    if k in attrs:
                        raise ValueError("Provided claimed subgraph layer"
                                         " key: {}".format(k))
                    attrs[k] = v
                
                if Xp.name in compiler_output_keys:
                    attrs['rt_in_map'] = compiler_output.get_in_map(Xp.name)
                    attrs['rt_out_map'] = compiler_output.get_out_map(Xp.name)

                Xp.attrs.update(attrs)

                shapes = Xp.shapes[:]

                subgraph_X = Xp._replace(
                    # name = X.name,
                    type=[xtype],
                    shapes=shapes,
                    bottoms=bottoms,
                    # Fill tops later
                    tops=[],
                    subgraph_data=[]
                )
                net.append(subgraph_X)

                # Subgraph layers have multiple outputs (Tuple) so we
                #   retrieve the different subgraph outputs
                #   (see output_names variable) using a TupleGetItem
                #   layer
                top_tensors = Xp.attrs['__top_tensors']

                for i, output_name in enumerate(output_names):
                    tgi_name = output_name
                    # tgi_name = subgraph_X.name + '_tgi' + str(i)
                    output_tensors = top_tensors[output_name]

                    shapes = subgraph_X.shapes[i][:]
                    X_tgi = defaultXLayer()
                    X_tgi = X_tgi._replace(
                        name=tgi_name,
                        type=['TupleGetItem'],
                        shapes=shapes,
                        sizes=shapes.get_size(),
                        layer=[tgi_name],
                        tops=output_tensors[:],
                        bottoms=[subgraph_X.name],
                        internal=1,
                        attrs={'index': i}
                    )
                    net.append(X_tgi)

                    subgraph_X.tops.append(tgi_name)

                    xp_out_tensors_2_layers[output_name] = tgi_name

            else:
                net.append(X)

        elif X.subgraph is not None and X.subgraph in visited_xps:
            # Remove layer
            visited_xps[X.subgraph].add(X.name)
        else:
            net.append(X)

    # Set tops and bottoms  & enforce topological sequence
    for xp in visited_xps.keys():
        Xp = subgraphs[xp]

        for b in Xp.bottoms:
            top_name = Xp.name
            bX = xgraph.get(b)
            bX.tops = [(bXt if bXt not in visited_xps[Xp.name]
                        else top_name)
                       for bXt in bX.tops]

            # NOTE: It's possible that bX was added after the Xp layer in the
            #   new network -> swap
            # bXi = find_indices(net, lambda X: X.name == b)[0]
            # Xpi = find_indices(net, lambda X: X.name == Xp.name)[0]

            # if bXi > Xpi:
            #     bXreal = net[bXi]
            #     # Remove
            #     net = list(filter(lambda X: X.name != b, net))
            #     # Insert just before Xp subgraph
            #     net.insert(Xpi, bXreal)

        for t in Xp.tops:
            tX = xgraph.get(t)
            tX.bottoms = [(tXb if tXb not in visited_xps[Xp.name]
                           else xp_out_tensors_2_layers[tXb])
                          for tXb in tX.bottoms]

    # Topological sorting
    top_net = sort_topologically(net)

    sub_xgraph = xgraph_factory.build_from_xlayer(top_net)

    # Merge transposes if they are cancelling out
    # optimizer = XGraphTransposesOptimizer(sub_xgraph)
    # optimizer.optimize()

    return sub_xgraph
