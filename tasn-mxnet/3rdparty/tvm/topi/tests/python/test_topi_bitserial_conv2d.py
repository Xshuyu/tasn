import numpy as np
import tvm
import topi
import topi.testing
from topi.util import get_const_tuple
from tvm.contrib.pickle_memoize import memoize

def generate_quantized_np(shape, bits, out_dtype):
    min_val = 0
    max_val = 1 << bits
    return np.random.randint(min_val, max_val, size=shape).astype(out_dtype)

def verify_bitserial_conv2d_nchw(batch, in_size, in_channel, num_filter, kernel, stride, padding, 
    activation_bits, weight_bits, dorefa):
    in_height = in_width = in_size
    input_type = 'uint32'
    out_dtype = 'int32'

    with tvm.target.create('llvm'):
        A = tvm.placeholder((batch, in_channel, in_height, in_width), dtype=input_type, name='A')
        W = tvm.placeholder((num_filter, in_channel, kernel, kernel), dtype=input_type, name='W')
        B = topi.nn.bitserial_conv2d(A, W, stride, padding, activation_bits, weight_bits, 
                                     out_dtype=out_dtype, layout="NCHW", dorefa=dorefa)
        s = topi.generic.schedule_bitserial_conv2d_nchw([B])

    a_shape = get_const_tuple(A.shape)
    w_shape = get_const_tuple(W.shape)

    @memoize("topi.tests.test_topi_bitseral_conv2d_nchw")
    def get_ref_data():
        a_np = generate_quantized_np(get_const_tuple(a_shape), activation_bits, input_type)
        w_np = generate_quantized_np(get_const_tuple(w_shape), weight_bits, input_type)
        if dorefa:
            w_ = np.copy(w_np).astype(out_dtype)
            for x in np.nditer(w_, op_flags=['readwrite']):
                x[...] = 1 if x == 1 else -1
            b_np = topi.testing.conv2d_nchw_python(a_np.astype(out_dtype), w_, stride, padding)
        else:
            b_np = topi.testing.conv2d_nchw_python(a_np, w_np, stride, padding)
        return a_np, w_np, b_np
    a_np, w_np, b_np = get_ref_data()

    ctx = tvm.cpu(0)
    a = tvm.nd.array(a_np, ctx)
    w = tvm.nd.array(w_np, ctx)
    b = tvm.nd.array(np.zeros(get_const_tuple(B.shape), dtype=B.dtype), ctx)
    func = tvm.build(s, [A, W, B], "llvm")
    func(a, w, b)
    np.testing.assert_allclose(b.asnumpy(), b_np, rtol=1e-5)

def verify_bitserial_conv2d_nhwc(batch, in_size, in_channel, num_filter, kernel, stride, padding, 
                        activation_bits, weight_bits, dorefa):
    in_height = in_width = in_size
    input_type='uint32'
    out_dtype='int32'

    with tvm.target.create('llvm'):
        A = tvm.placeholder((batch, in_height, in_width, in_channel), dtype=input_type, name='A')
        W = tvm.placeholder((kernel, kernel, in_channel, num_filter), dtype=input_type, name='W')
        B = topi.nn.bitserial_conv2d(A, W, stride, padding, activation_bits, weight_bits, out_dtype=out_dtype, 
                                     layout="NHWC", dorefa=dorefa)
        s = topi.generic.schedule_bitserial_conv2d_nhwc([B])

    a_shape = get_const_tuple(A.shape)
    w_shape = get_const_tuple(W.shape)

    @memoize("topi.tests.test_topi_bitseral_conv2d_nhwc")
    def get_ref_data():
        a_np = generate_quantized_np(get_const_tuple(a_shape), activation_bits, input_type)
        w_np = generate_quantized_np(get_const_tuple(w_shape), weight_bits, input_type)
        if dorefa:
            w_ = np.copy(w_np).astype(out_dtype)
            for x in np.nditer(w_, op_flags=['readwrite']):
                x[...] = 1 if x == 1 else -1
            b_np = topi.testing.conv2d_nhwc_python(a_np, w_, stride, padding).astype(out_dtype)
        else:
            b_np = topi.testing.conv2d_nhwc_python(a_np, w_np, stride, padding).astype(out_dtype)
        return a_np, w_np, b_np
    a_np, w_np, b_np = get_ref_data()

    ctx = tvm.cpu(0)
    a = tvm.nd.array(a_np, ctx)
    w = tvm.nd.array(w_np, ctx)
    b = tvm.nd.array(np.zeros(get_const_tuple(B.shape), dtype=B.dtype), ctx)
    func = tvm.build(s, [A, W, B], 'llvm')

    func(a, w, b)
    np.testing.assert_allclose(b.asnumpy(), b_np, rtol=1e-5)

def test_bitserial_conv2d():
    in_size = 56
    ic, oc = 64, 64
    k = 3
    stride = 1
    pad = 1
    verify_bitserial_conv2d_nchw(1, in_size, ic, oc, k, stride, pad, 1, 1, True)
    verify_bitserial_conv2d_nchw(1, in_size, ic, oc, k, stride, pad, 2, 1, True)
    verify_bitserial_conv2d_nchw(1, in_size, ic, oc, k, stride, pad, 1, 1, False)
    verify_bitserial_conv2d_nchw(1, in_size, ic, oc, k, stride, pad, 2, 1, False)
    verify_bitserial_conv2d_nchw(1, in_size, ic, oc, k, stride, pad, 2, 2, False)

    verify_bitserial_conv2d_nhwc(1, in_size, ic, oc, k, stride, pad, 1, 1, True)
    verify_bitserial_conv2d_nhwc(1, in_size, ic, oc, k, stride, pad, 2, 1, True)
    verify_bitserial_conv2d_nhwc(1, in_size, ic, oc, k, stride, pad, 1, 1, False)
    verify_bitserial_conv2d_nhwc(1, in_size, ic, oc, k, stride, pad, 2, 1, False)
    verify_bitserial_conv2d_nhwc(1, in_size, ic, oc, k, stride, pad, 2, 2, False)

if __name__ == "__main__":
    test_bitserial_conv2d()