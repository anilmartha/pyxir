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

#include <memory>
#include <stdexcept>

#include "pyxir/frontend/onnx.hpp"
#include "pyxir/opaque_func_registry.hpp"

namespace pyxir {
namespace onnx {

// extern "C" int __attribute__((visibility("default"))) import_onnx_model(const char *file_path);

PX_API std::shared_ptr<graph::XGraph> import_onnx_model(
  const std::string &file_path
) {
  if (!pyxir::OpaqueFuncRegistry::Exists("pyxir.onnx.from_onnx"))
    throw std::runtime_error("Cannot import ONNX model from file because"
                             " `pyxir.onnx.from_onnx` opaque function is"
                             " not registered");
  
  std::shared_ptr<pyxir::graph::XGraph> xg = 
    std::make_shared<pyxir::graph::XGraph>("empty_onnx_model");
  
  OpaqueFunc from_onnx = 
    pyxir::OpaqueFuncRegistry::Get("pyxir.onnx.from_onnx");

  from_onnx(xg, file_path);

  return xg;
}


PX_API std::shared_ptr<graph::XGraph> import_onnx_model(
  std::istringstream &sstream
) {
  if (!pyxir::OpaqueFuncRegistry::Exists("pyxir.onnx.from_onnx_bytes"))
    throw std::runtime_error("Cannot import ONNX model from file because"
                             " `pyxir.onnx.from_onnx_bytes` opaque function is"
                             " not registered");
  
  std::shared_ptr<pyxir::graph::XGraph> xg = 
    std::make_shared<pyxir::graph::XGraph>("empty_onnx_model");
  
  OpaqueFunc from_onnx = 
    pyxir::OpaqueFuncRegistry::Get("pyxir.onnx.from_onnx_bytes");
  
  std::string bytes = sstream.str();
  from_onnx(xg, bytes);

  return xg;
}

} // pyxir
} // onnx
