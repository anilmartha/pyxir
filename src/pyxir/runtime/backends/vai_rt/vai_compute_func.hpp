/*
 *  Copyright 2020 Xilinx Inc.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *  
 *      http://www.apache.org/licenses/LICENSE-2.0
 *  
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

#pragma once

#include <unordered_set>
#include <dpu/dpu_runner.hpp>

#include "pyxir/graph/xgraph.hpp"
#include "pyxir/common/xbuffer.hpp"

void vaiDebugMsg(const char *, const char *, const char *, int);
#ifdef DEBUG
#define vaiDebug(x) vaiDebugMsg(x,__FUNCTION__,__FILE__,__LINE__);
#else
#define vaiDebug(x)
#endif

namespace pyxir {
namespace runtime {
namespace vai_rt {

class VaiComputeFunc {

  public:
    VaiComputeFunc(XGraphHolder &xg,
                   const std::string &target,
                   const std::vector<std::string> &in_tensor_names,
                   const std::vector<std::string> &out_tensor_names);

    void operator()(std::vector<XBufferHolder> &in_tensors,
                    std::vector<XBufferHolder> &out_tensors);

    bool is_op_supported(const std::string &op_type)
    {
      return supported_ops_.find(op_type) != supported_ops_.end();
    }

  private:
    XGraphHolder xg_;
    std::string target_;
    std::vector<std::string> in_tensor_names_;
    std::vector<std::string> out_tensor_names_;

    // The input tensors and output tensors of the accelerator might be
    //  different than the original input and output tensors
    // std::unordered_map<std::string, std::string> rt_in_to_in_map_;
    // std::unordered_map<std::string, std::string> rt_out_to_out_map_;
    std::vector<vitis::ai::Tensor*> dpu_runner_in_tensors_;
    std::vector<vitis::ai::Tensor*> dpu_runner_out_tensors_;
    std::vector<int> in_tensor_order_;
    std::vector<int> out_tensor_order_;

    std::unique_ptr<vitis::ai::DpuRunner> dpu_runner_;

    std::unordered_set<std::string> supported_ops_ =
      {"Input", "Output", "DPUV1", "TupleGetItem"};
};

} // vai_rt
} // namespace runtime
} // namespace pyxir
