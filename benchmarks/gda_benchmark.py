# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Microbenchmarks for JAX `api` functions."""

from functools import partial

import google_benchmark
import jax
from jax._src import test_util as jtu
from jax._src.util import prod
from jax.experimental import global_device_array as gda
import numpy as np

mesh_shapes_axes = [
    ((256, 8), ["x", "y"]),
    ((256, 8), [None]),
    ((256, 8), ["x"]),
    ((256, 8), ["y"]),
    ((256, 8), [("x", "y")]),
    ((128, 8), ["x", "y"]),
    ((4, 2), ["x", "y"]),
]


def gda_construction_callback(mesh_axes, state):
  # Keep the mesh containing 8 local devices as using >8 local devices is
  # unrealistic. Since `from_callback` measures `device_put` time as well, it
  # dominates when local devices are for example 2048 (local devices will never
  # be 2048).
  global_mesh = jtu.create_global_mesh((4, 2), ('x', 'y'))
  global_input_shape = (2048, 2048)
  global_input_data = np.arange(
      prod(global_input_shape)).reshape(global_input_shape)
  def cb(index):
    return global_input_data[index]

  while state:
    gda.GlobalDeviceArray.from_callback(
        global_input_shape, global_mesh, mesh_axes, cb)


def gda_construction_raw(mesh_shape, mesh_axes, state):
  # `device_put` time is not measured in this benchmark. All the devices here
  # are local.
  global_mesh = jtu.create_global_mesh(mesh_shape, ("x", "y"))
  global_input_shape = (2048, 2048)
  global_input_data = np.arange(
      prod(global_input_shape)).reshape(global_input_shape)
  global_indices = gda.get_shard_indices(global_input_shape, global_mesh,
                                         mesh_axes)
  dbs = [
      jax.device_put(global_input_data[global_indices[device]], device)
      for device in global_mesh.local_devices
  ]

  while state:
    gda.GlobalDeviceArray(global_input_shape, global_mesh, mesh_axes, dbs)


def indices_replica_id_calc(mesh_shape, mesh_axes, state):
  global_input_shape = (2048, 2048)
  global_mesh = jtu.create_global_mesh(mesh_shape, ("x", "y"))

  while state:
    gda.get_shard_indices_replica_ids(global_input_shape, global_mesh, mesh_axes)


benchmarks = []
for mesh_shape, axes in mesh_shapes_axes:
  benchmarks.extend([
      google_benchmark.register(
          partial(gda_construction_callback, axes),
          name=f"gda_construction_callback_(4, 2)_{axes}"),
      google_benchmark.register(
          partial(gda_construction_raw, mesh_shape, axes),
          name=f"gda_construction_raw_{mesh_shape}_{axes}"),
      google_benchmark.register(
          partial(indices_replica_id_calc, mesh_shape, axes),
          name=f"indices_replica_id_calc_{mesh_shape}_{axes}"),
  ])


if __name__ == "__main__":
  google_benchmark.main()
