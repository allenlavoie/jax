# Copyright 2021 Google LLC
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

import unittest

from absl.testing import absltest
from absl.testing import parameterized

import jax
import jax.numpy as jnp
from jax import lax
from jax.config import config
from jax.experimental import checkify
import jax._src.test_util as jtu

config.parse_flags_with_absl()


class CheckifyTransformTests(jtu.JaxTestCase):
  @parameterized.named_parameters(jtu.cases_from_list(
      {"testcase_name": "_jit={}".format(jit), "jit": jit}
      for jit in [False, True]))
  @jtu.skip_on_devices('tpu')
  def test_jit_nan(self, jit):
    def f(x1, x2):
      y1 = jnp.sin(x1)
      y2 = jnp.sin(x2)
      return y1 + y2

    f = jax.jit(f) if jit else f

    err, _ = checkify.checkify(f)(3., 4.)
    self.assertIs(err.get(), None)

    err, _ = checkify.checkify(f)(3., jnp.inf)
    self.assertStartsWith(err.get(), 'nan generated by primitive sin')

  @parameterized.named_parameters(jtu.cases_from_list(
      {"testcase_name": "_jit={}".format(jit), "jit": jit}
      for jit in [False, True]))
  def test_jit_oob(self, jit):
    def f(x, i):
      y = jnp.sin(x)
      z = y[i]
      w = jnp.cos(z)
      return w

    f = jax.jit(f) if jit else f

    err, _ = checkify.checkify(f)(jnp.arange(3), 2)
    self.assertIs(err.get(), None)

    err, _ = checkify.checkify(f)(jnp.arange(3), 5)
    self.assertStartsWith(err.get(), 'out-of-bounds indexing')

  @parameterized.named_parameters(jtu.cases_from_list(
      {"testcase_name": "_jit={}".format(jit), "jit": jit}
      for jit in [False, True]))
  @jtu.skip_on_devices('tpu')
  def test_jit_multi(self, jit):
    def f(x, i):
      y = x[i]
      z = jnp.cos(y)
      return z

    f = jax.jit(f) if jit else f

    # no error
    err, _ = checkify.checkify(f)(jnp.array([0., jnp.inf, 2.]), 2)
    self.assertIs(err.get(), None)

    # oob error
    err, _ = checkify.checkify(f)(jnp.array([0., 1., 2.]), 5)
    self.assertStartsWith(err.get(), 'out-of-bounds indexing')

    # nan error
    err, _ = checkify.checkify(f)(jnp.array([0., 1., jnp.inf]), 2)
    self.assertStartsWith(err.get(), 'nan generated by primitive cos')

  @parameterized.named_parameters(jtu.cases_from_list(
      {"testcase_name": "_jit={}".format(jit), "jit": jit}
      for jit in [False, True]))
  def test_jit_ordering(self, jit):
    def f(x, i):
      y = x[i]
      z = jnp.sin(x)
      return y * z

    f = jax.jit(f) if jit else f

    # both oob and nan error, but oob happens first
    err, _ = checkify.checkify(f)(jnp.array([0., 1., jnp.inf]), 5)
    self.assertStartsWith(err.get(), 'out-of-bounds indexing')

  @jtu.skip_on_devices('tpu')
  def test_pmap_basic(self):
    if len(jax.devices()) < 2:
      raise unittest.SkipTest("requires at least 2 devices")

    @jax.pmap
    def f(x1, x2):
      y1 = jnp.sin(x1)
      y2 = jnp.sin(x2)
      return y1 + y2

    xs = jnp.array([0., 2.])
    err, _ = checkify.checkify(f)(xs, xs)
    self.assertIs(err.get(), None)

    ys = jnp.array([3., jnp.inf])
    err, _ = checkify.checkify(f)(xs, ys)
    self.assertStartsWith(err.get(), 'nan generated by primitive sin')

  @jtu.skip_on_devices('tpu')
  def test_cond_basic(self):
    @jax.jit
    def f(x):
      return lax.cond(x > 0,
                      lambda: jnp.sin(x),
                      lambda: x)

    err, y = checkify.checkify(f)(3.)
    self.assertIs(err.get(), None)

    err, y = checkify.checkify(f)(jnp.inf)
    self.assertStartsWith(err.get(), 'nan generated by primitive sin')

    err, y = checkify.checkify(f)(-jnp.inf)
    self.assertIs(err.get(), None)


if __name__ == "__main__":
  absltest.main(testLoader=jtu.JaxTestLoader())