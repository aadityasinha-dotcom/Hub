from hub.tests.common import get_actual_compression_from_buffer, assert_images_close
import numpy as np
import pytest
import hub
import lz4.frame  # type: ignore
from hub.util.compression import (
    compress_array,
    decompress_array,
    compress_multiple,
    decompress_multiple,
    verify_compressed_file,
    decompress_bytes,
)
from hub.compression import (
    get_compression_type,
    BYTE_COMPRESSION,
    IMAGE_COMPRESSION,
    IMAGE_COMPRESSIONS,
    BYTE_COMPRESSIONS,
    AUDIO_COMPRESSIONS,
    SUPPORTED_COMPRESSIONS,
)
from hub.util.exceptions import CorruptedSampleError
from PIL import Image  # type: ignore


compressions = SUPPORTED_COMPRESSIONS[:]
compressions.remove(None)  # type: ignore
compressions.remove("wmf")  # driver has to be provided by user for wmf write support

image_compressions = IMAGE_COMPRESSIONS[:]
image_compressions.remove("wmf")


@pytest.mark.parametrize("compression", image_compressions + BYTE_COMPRESSIONS)
def test_array(compression, compressed_image_paths):
    # TODO: check dtypes and no information loss
    compression_type = get_compression_type(compression)
    if compression_type == BYTE_COMPRESSION:
        array = np.random.randint(0, 10, (32, 32))
    elif compression_type == IMAGE_COMPRESSION:
        array = np.array(hub.read(compressed_image_paths[compression][0]))
    shape = array.shape
    compressed_buffer = compress_array(array, compression)
    if compression_type == BYTE_COMPRESSION:
        decompressed_array = decompress_array(
            compressed_buffer, shape=shape, dtype=array.dtype, compression=compression
        )
    else:
        assert get_actual_compression_from_buffer(compressed_buffer) == compression
        decompressed_array = decompress_array(compressed_buffer, shape=shape)
    if compression == "png" or compression_type == BYTE_COMPRESSION:
        np.testing.assert_array_equal(array, decompressed_array)
    else:
        assert_images_close(array, decompressed_array)


@pytest.mark.parametrize("compression", image_compressions + BYTE_COMPRESSIONS)
def test_multi_array(compression, compressed_image_paths):
    compression_type = get_compression_type(compression)
    if compression_type == IMAGE_COMPRESSION:
        img = Image.open(compressed_image_paths[compression][0])
        img2 = img.resize((img.size[0] // 2, img.size[1] // 2))
        img3 = img.resize((img.size[0] // 3, img.size[1] // 3))
        arrays = list(map(np.array, [img, img2, img3]))
        compressed_buffer = compress_multiple(arrays, compression)
        decompressed_arrays = decompress_multiple(
            compressed_buffer, [arr.shape for arr in arrays]
        )
    elif compression_type == BYTE_COMPRESSION:
        arrays = [np.random.randint(0, 10, (32, 32)) for _ in range(3)]
        compressed_buffer = compress_multiple(arrays, compression)
        decompressed_arrays = decompress_multiple(
            compressed_buffer, [(32, 32)] * 3, arrays[0].dtype, compression
        )

    for arr1, arr2 in zip(arrays, decompressed_arrays):
        if compression == "png" or compression_type == BYTE_COMPRESSION:
            np.testing.assert_array_equal(arr1, arr2)
        else:
            assert_images_close(arr1, arr2)


@pytest.mark.parametrize("compression", image_compressions)
def test_verify(compression, compressed_image_paths, corrupt_image_paths):
    for path in compressed_image_paths[compression]:
        sample = hub.read(path)
        sample_loaded = hub.read(path)
        sample_loaded.compressed_bytes(compression)
        sample_verified_and_loaded = hub.read(path, verify=True)
        sample_verified_and_loaded.compressed_bytes(compression)
        pil_image_shape = np.array(Image.open(path)).shape
        assert (
            sample.shape
            == sample_loaded.shape
            == sample_verified_and_loaded.shape
            == pil_image_shape
        ), (
            sample.shape,
            sample_loaded.shape,
            sample_verified_and_loaded.shape,
            pil_image_shape,
        )
        verify_compressed_file(path, compression)
        with open(path, "rb") as f:
            verify_compressed_file(f, compression)
    if compression in corrupt_image_paths:
        path = corrupt_image_paths[compression]
        sample = hub.read(path)
        sample.compressed_bytes(compression)
        Image.open(path)
        with pytest.raises(CorruptedSampleError):
            sample = hub.read(path, verify=True)
            sample.compressed_bytes(compression)
        with pytest.raises(CorruptedSampleError):
            verify_compressed_file(path, compression)
        with pytest.raises(CorruptedSampleError):
            with open(path, "rb") as f:
                verify_compressed_file(f, compression)
        with pytest.raises(CorruptedSampleError):
            with open(path, "rb") as f:
                verify_compressed_file(f.read(), compression)


def test_lz4_bc():
    inp = np.random.random((100, 100)).tobytes()
    compressed = lz4.frame.compress(inp)
    decompressed = decompress_bytes(compressed, "lz4")
    assert decompressed == inp


@pytest.mark.parametrize("compression", AUDIO_COMPRESSIONS)
def test_audio(compression, audio_paths):
    path = audio_paths[compression]
    sample = hub.read(path)
    arr = np.array(sample)
    assert arr.dtype == "float32"
    with open(path, "rb") as f:
        assert sample.compressed_bytes(compression) == f.read()