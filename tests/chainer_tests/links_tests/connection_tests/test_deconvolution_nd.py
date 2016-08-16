import unittest

import numpy

import chainer
from chainer import cuda
from chainer import gradient_check
from chainer import initializers
from chainer.links import deconvolution_nd
from chainer import testing
from chainer.testing import attr
from chainer.testing import condition
from chainer.testing import parameterize
from chainer.utils import conv


@parameterize(*testing.product({
    'dims': [(5, 4, 3), (4, 3), (3,)],
    'nobias': [True, False],
    'dtype': [numpy.float32],   # TODO(takagi) other dtypes.
    'use_cudnn': [True, False],
    'use_outsize': [True, False],
}))
class TestDeconvolutionND(unittest.TestCase):

    def setUp(self):
        N = 2
        in_channels = 3
        out_channels = 2
        ndim = len(self.dims)
        ksize = (3,) * ndim
        stride = (2,) * ndim
        pad = (1,) * ndim

        outs = tuple(
            conv.get_deconv_outsize(d, k, s, p)
            for (d, k, s, p) in zip(self.dims, ksize, stride, pad))

        outsize = outs if self.use_outsize else None
        initial_bias = \
            initializers.Uniform(scale=1) if not self.nobias else None

        self.link = deconvolution_nd.DeconvolutionND(
            ndim, in_channels, out_channels, ksize, stride=stride, pad=pad,
            outsize=outsize, initial_bias=initial_bias)
        self.link.zerograds()

        x_shape = (N, in_channels) + self.dims
        self.x = numpy.random.uniform(-1, 1, x_shape).astype(self.dtype)
        gy_shape = (N, out_channels) + outs
        self.gy = numpy.random.uniform(-1, 1, gy_shape).astype(self.dtype)

    def check_forward_consistency(self, link, x_data):
        x_cpu = chainer.Variable(x_data)
        y_cpu = link(x_cpu)
        self.assertEqual(y_cpu.data.dtype, x_data.dtype)

        link.to_gpu()
        x_gpu = chainer.Variable(cuda.to_gpu(x_data))
        y_gpu = link(x_gpu)
        self.assertEqual(y_gpu.data.dtype, x_data.dtype)

        testing.assert_allclose(y_cpu.data, y_gpu.data)

    @attr.gpu
    @condition.retry(3)
    def test_forward_consistency(self):
        self.link.use_cudnn = self.use_cudnn
        self.check_forward_consistency(self.link, self.x)

    def check_backward(self, link, x_data, y_grad):
        params = [link.W]
        if not self.nobias:
            params.append(link.b)

        gradient_check.check_backward(
            link, x_data, y_grad, params, eps=1e-2, rtol=1e-4, atol=1e-4)

    @condition.retry(3)
    def test_backward_cpu(self):
        self.check_backward(self.link, self.x, self.gy)

    @attr.gpu
    @condition.retry(3)
    def test_backward_gpu(self):
        self.link.use_cudnn = self.use_cudnn
        self.link.to_gpu()
        self.check_backward(
            self.link, cuda.to_gpu(self.x), cuda.to_gpu(self.gy))


class TestDeconvolutionNDNoInitialBias(unittest.TestCase):

    def test_no_initial_bias(self):
        ndim = 3
        ksize = 3
        link = deconvolution_nd.DeconvolutionND(
            ndim, 3, 2, ksize, initial_bias=None)
        self.assertIsNone(link.b)


testing.run_module(__name__, __file__)
