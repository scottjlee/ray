import json
import os
from typing import TYPE_CHECKING

import numpy as np
from pandas.api.types import is_int64_dtype, is_float_dtype, is_object_dtype
import pytest

import ray

from ray.tests.conftest import *  # noqa

if TYPE_CHECKING:
    import tensorflow as tf
    from tensorflow_metadata.proto.v0 import schema_pb2


@pytest.fixture
def tf_records_partial(request):
    """Underlying data corresponds to `data_partial` fixture."""
    import tensorflow as tf

    return [
        # Record one (corresponding to row one).
        tf.train.Example(
            features=tf.train.Features(
                feature={
                    "int_item": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[1])
                    ),
                    "int_list": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[2, 2, 3])
                    ),
                    "int_partial": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[])
                    ),
                    "float_item": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[1.0])
                    ),
                    "float_list": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[2.0, 3.0, 4.0])
                    ),
                    "float_partial": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[1.0])
                    ),
                    "bytes_item": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"abc"])
                    ),
                    "bytes_list": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"def", b"1234"])
                    ),
                    "bytes_partial": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[])
                    ),
                }
            )
        ),
        # Record two (corresponding to row two).
        tf.train.Example(
            features=tf.train.Features(
                feature={
                    "int_item": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[2])
                    ),
                    "int_list": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[3, 3, 4])
                    ),
                    "int_partial": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[9, 2])
                    ),
                    "float_item": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[2.0])
                    ),
                    "float_list": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[5.0, 6.0, 7.0])
                    ),
                    "float_partial": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[])
                    ),
                    "bytes_item": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"ghi"])
                    ),
                    "bytes_list": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"jkl", b"5678"])
                    ),
                    "bytes_partial": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"hello"])
                    ),
                }
            )
        ),
    ]


@pytest.fixture
def data_partial(request):
    """TFRecords generated from this corresponds to
    the `tf_records_partial` fixture."""
    return [
        # Row one.
        {
            "int_item": 1,
            "int_list": [2, 2, 3],
            "int_partial": [],
            "float_item": 1.0,
            "float_list": [2.0, 3.0, 4.0],
            "float_partial": 1.0,
            "bytes_item": b"abc",
            "bytes_list": [b"def", b"1234"],
            "bytes_partial": None,
        },
        # Row two.
        {
            "int_item": 2,
            "int_list": [3, 3, 4],
            "int_partial": [9, 2],
            "float_item": 2.0,
            "float_list": [5.0, 6.0, 7.0],
            "float_partial": None,
            "bytes_item": b"ghi",
            "bytes_list": [b"jkl", b"5678"],
            "bytes_partial": b"hello",
        },
    ]


@pytest.fixture
def tf_records_empty(request):
    """Underlying data corresponds to `data_empty` fixture."""
    import tensorflow as tf

    return [
        # Record one (corresponding to row one).
        tf.train.Example(
            features=tf.train.Features(
                feature={
                    "int_item": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[1])
                    ),
                    "int_list": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[2, 2, 3])
                    ),
                    "int_partial": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[])
                    ),
                    "int_empty": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[])
                    ),
                    "float_item": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[1.0])
                    ),
                    "float_list": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[2.0, 3.0, 4.0])
                    ),
                    "float_partial": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[1.0])
                    ),
                    "float_empty": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[])
                    ),
                    "bytes_item": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"abc"])
                    ),
                    "bytes_list": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"def", b"1234"])
                    ),
                    "bytes_partial": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[])
                    ),
                    "bytes_empty": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[])
                    ),
                }
            )
        ),
        # Record two (corresponding to row two).
        tf.train.Example(
            features=tf.train.Features(
                feature={
                    "int_item": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[2])
                    ),
                    "int_list": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[3, 3, 4])
                    ),
                    "int_partial": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[9, 2])
                    ),
                    "int_empty": tf.train.Feature(
                        int64_list=tf.train.Int64List(value=[])
                    ),
                    "float_item": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[2.0])
                    ),
                    "float_list": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[5.0, 6.0, 7.0])
                    ),
                    "float_partial": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[])
                    ),
                    "float_empty": tf.train.Feature(
                        float_list=tf.train.FloatList(value=[])
                    ),
                    "bytes_item": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"ghi"])
                    ),
                    "bytes_list": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"jkl", b"5678"])
                    ),
                    "bytes_partial": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[b"hello"])
                    ),
                    "bytes_empty": tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[])
                    ),
                }
            )
        ),
    ]


@pytest.fixture
def data_empty(request):
    """TFRecords generated from this corresponds to
    the `tf_records_empty` fixture."""
    return [
        # Row one.
        {
            "int_item": 1,
            "int_list": [2, 2, 3],
            "int_partial": [],
            "int_empty": [],
            "float_item": 1.0,
            "float_list": [2.0, 3.0, 4.0],
            "float_partial": 1.0,
            "float_empty": [],
            "bytes_item": b"abc",
            "bytes_list": [b"def", b"1234"],
            "bytes_partial": [],
            "bytes_empty": [],
        },
        # Row two.
        {
            "int_item": 2,
            "int_list": [3, 3, 4],
            "int_partial": [9, 2],
            "int_empty": [],
            "float_item": 2.0,
            "float_list": [5.0, 6.0, 7.0],
            "float_partial": [],
            "float_empty": [],
            "bytes_item": b"ghi",
            "bytes_list": [b"jkl", b"5678"],
            "bytes_partial": b"hello",
            "bytes_empty": [],
        },
    ]


def _features_to_schema(features: "tf.train.Features") -> "schema_pb2.Schema":
    from tensorflow_metadata.proto.v0 import schema_pb2

    tf_schema = schema_pb2.Schema()
    for feature_name, feature_msg in features.feature.items():
        schema_feature = tf_schema.feature.add()
        schema_feature.name = feature_name
        if feature_msg.HasField("bytes_list"):
            schema_feature.type = schema_pb2.FeatureType.BYTES
        elif feature_msg.HasField("float_list"):
            schema_feature.type = schema_pb2.FeatureType.FLOAT
        elif feature_msg.HasField("int64_list"):
            schema_feature.type = schema_pb2.FeatureType.INT
    return tf_schema


def _ds_eq_streaming(ds_expected, ds_actual) -> bool:
    if not ray.data.context.DatasetContext.get_current().use_streaming_executor:
        assert ds_expected.take() == ds_actual.take()
    else:
        # In streaming, we set batch_format to "default" (because calling
        # ds.dataset_format() will still invoke bulk execution and we want
        # to avoid that). As a result, it's receiving PandasRow (the defaut
        # batch format), which doesn't have the same ordering of columns as
        # the ArrowRow.
        from ray.data.block import BlockAccessor

        def get_rows(ds):
            rows = []
            for batch in ds.iter_batches(batch_size=None, batch_format="pyarrow"):
                batch = BlockAccessor.for_block(BlockAccessor.batch_to_block(batch))
                for row in batch.iter_rows():
                    rows.append(row)
            return rows

        assert get_rows(ds_expected) == get_rows(ds_actual)


@pytest.mark.parametrize("with_tf_schema", (True, False))
def test_read_tfrecords(
    with_tf_schema, ray_start_regular_shared, tmp_path, tf_records_empty
):
    import tensorflow as tf

    example = tf_records_empty[0]

    tf_schema = None
    if with_tf_schema:
        tf_schema = _features_to_schema(tf_records_empty[0].features)

    path = os.path.join(tmp_path, "data.tfrecords")
    with tf.io.TFRecordWriter(path=path) as writer:
        writer.write(example.SerializeToString())

    ds = ray.data.read_tfrecords(path, tf_schema=tf_schema)
    df = ds.to_pandas()
    # Protobuf serializes features in a non-deterministic order.
    assert is_int64_dtype(dict(df.dtypes)["int_item"])
    assert is_object_dtype(dict(df.dtypes)["int_list"])
    assert is_object_dtype(dict(df.dtypes)["int_partial"])
    assert is_object_dtype(dict(df.dtypes)["int_empty"])

    assert is_float_dtype(dict(df.dtypes)["float_item"])
    assert is_object_dtype(dict(df.dtypes)["float_list"])
    assert is_float_dtype(dict(df.dtypes)["float_partial"])
    assert is_object_dtype(dict(df.dtypes)["float_empty"])

    assert is_object_dtype(dict(df.dtypes)["bytes_item"])
    assert is_object_dtype(dict(df.dtypes)["bytes_list"])
    assert is_object_dtype(dict(df.dtypes)["bytes_partial"])
    assert is_object_dtype(dict(df.dtypes)["bytes_empty"])

    assert list(df["int_item"]) == [1]
    assert np.array_equal(df["int_list"][0], np.array([2, 2, 3]))
    assert np.array_equal(df["int_partial"][0], np.array([], dtype=np.int64))
    assert np.array_equal(df["int_empty"][0], np.array([], dtype=np.int64))

    assert list(df["float_item"]) == [1.0]
    assert np.array_equal(df["float_list"][0], np.array([2.0, 3.0, 4.0]))
    assert list(df["float_partial"]) == [1.0]
    assert np.array_equal(df["float_empty"][0], np.array([], dtype=np.float32))

    assert list(df["bytes_item"]) == [b"abc"]
    assert np.array_equal(df["bytes_list"][0], np.array([b"def", b"1234"]))
    assert np.array_equal(df["bytes_partial"][0], np.array([], dtype=np.bytes_))
    assert np.array_equal(df["bytes_empty"][0], np.array([], dtype=np.bytes_))


@pytest.mark.parametrize("with_tf_schema", (True, False))
def test_write_tfrecords(
    with_tf_schema, ray_start_regular_shared, tmp_path, tf_records_partial, data_partial
):
    """Test that write_tfrecords writes TFRecords correctly.

    Test this by writing a Dataset to a TFRecord (function under test),
    reading it back out into a tf.train.Example,
    and checking that the result is analogous to the original Dataset.
    """

    import tensorflow as tf

    # The dataset we will write to a .tfrecords file.
    ds = ray.data.from_items(
        data_partial,
        # Here, we specify `parallelism=1` to ensure that all rows end up in the same
        # block, which is required for type inference involving
        # partially missing columns.
        parallelism=1,
    )

    # The corresponding tf.train.Example that we would expect to read
    # from this dataset.
    expected_records = tf_records_partial

    tf_schema = None
    if with_tf_schema:
        features = expected_records[0].features
        tf_schema = _features_to_schema(features)

    # Perform the test.
    # Write the dataset to a .tfrecords file.
    ds.write_tfrecords(tmp_path, tf_schema=tf_schema)

    # Read the Examples back out from the .tfrecords file.
    # This follows the offical TFRecords tutorial:
    # https://www.tensorflow.org/tutorials/load_data/tfrecord#reading_a_tfrecord_file_2

    filenames = sorted(os.listdir(tmp_path))
    filepaths = [os.path.join(tmp_path, filename) for filename in filenames]
    raw_dataset = tf.data.TFRecordDataset(filepaths)

    tfrecords = []
    for raw_record in raw_dataset:
        example = tf.train.Example()
        example.ParseFromString(raw_record.numpy())
        tfrecords.append(example)

    assert tfrecords == expected_records


@pytest.mark.parametrize("with_tf_schema", (True, False))
def test_write_tfrecords_empty_features(
    with_tf_schema,
    ray_start_regular_shared,
    tmp_path,
    tf_records_empty,
    data_empty,
):
    """Test that write_tfrecords writes TFRecords with completely empty features
    correctly (i.e. the case where type inference from partially filled features
    is not possible). We expect this to succeed when passing an explicit `tf_schema`
    param, and otherwise will raise a `ValueError`.

    Test this by writing a Dataset to a TFRecord (function under test),
    reading it back out into a tf.train.Example,
    and checking that the result is analogous to the original Dataset.
    """

    import tensorflow as tf

    # The dataset we will write to a .tfrecords file.
    ds = ray.data.from_items(data_empty)

    # The corresponding tf.train.Example that we would expect to read
    # from this dataset.
    expected_records = tf_records_empty

    if not with_tf_schema:
        with pytest.raises(ValueError):
            # Type inference from fully empty columns should fail if
            # no schema is specified.
            ds.write_tfrecords(tmp_path)
    else:
        features = expected_records[0].features
        tf_schema = _features_to_schema(features)

        # Perform the test.
        # Write the dataset to a .tfrecords file.
        ds.write_tfrecords(tmp_path, tf_schema=tf_schema)

        # Read the Examples back out from the .tfrecords file.
        # This follows the offical TFRecords tutorial:
        # https://www.tensorflow.org/tutorials/load_data/tfrecord#reading_a_tfrecord_file_2

        filenames = sorted(os.listdir(tmp_path))
        filepaths = [os.path.join(tmp_path, filename) for filename in filenames]
        raw_dataset = tf.data.TFRecordDataset(filepaths)

        tfrecords = []
        for raw_record in raw_dataset:
            example = tf.train.Example()
            example.ParseFromString(raw_record.numpy())
            tfrecords.append(example)

        assert tfrecords == expected_records


@pytest.mark.parametrize("with_tf_schema", (True, False))
def test_readback_tfrecords(
    ray_start_regular_shared,
    tmp_path,
    with_tf_schema,
    tf_records_partial,
    data_partial,
):
    """
    Test reading back TFRecords written using datasets.
    The dataset we read back should be the same that we wrote.
    """

    # The dataset we will write to a .tfrecords file.
    # Here and in the read_tfrecords call below, we specify `parallelism=1`
    # to ensure that all rows end up in the same block, which is required
    # for type inference involving partially missing columns.
    ds = ray.data.from_items(data_partial, parallelism=1)
    expected_records = tf_records_partial

    tf_schema = None
    if with_tf_schema:
        features = expected_records[0].features
        tf_schema = _features_to_schema(features)

    # Write the TFRecords.
    ds.write_tfrecords(tmp_path, tf_schema=tf_schema)
    # Read the TFRecords.
    readback_ds = ray.data.read_tfrecords(tmp_path, tf_schema=tf_schema)
    _ds_eq_streaming(ds, readback_ds)


@pytest.mark.parametrize("with_tf_schema", (True, False))
def test_readback_tfrecords_empty_features(
    ray_start_regular_shared,
    tmp_path,
    with_tf_schema,
    tf_records_empty,
    data_empty,
):
    """
    Test reading back TFRecords written using datasets.
    The dataset we read back should be the same that we wrote.
    """

    # The dataset we will write to a .tfrecords file.
    ds = ray.data.from_items(data_empty)
    if not with_tf_schema:
        with pytest.raises(ValueError):
            # With no schema specified, this should fail because
            # type inference on completely empty columns is ambiguous.
            ds.write_tfrecords(tmp_path)
    else:
        expected_records = tf_records_empty

        features = expected_records[0].features
        tf_schema = _features_to_schema(features)

        # Write the TFRecords.
        ds.write_tfrecords(tmp_path, tf_schema=tf_schema)

        # Read the TFRecords.
        readback_ds = ray.data.read_tfrecords(tmp_path)
        _ds_eq_streaming(ds, readback_ds)


def test_write_invalid_tfrecords(ray_start_regular_shared, tmp_path):
    """
    If we try to write a dataset with invalid TFRecord datatypes,
    ValueError should be raised.
    """

    ds = ray.data.from_items([{"item": None}])

    with pytest.raises(ValueError):
        ds.write_tfrecords(tmp_path)


def test_read_invalid_tfrecords(ray_start_regular_shared, tmp_path):
    file_path = os.path.join(tmp_path, "file.json")
    with open(file_path, "w") as file:
        json.dump({"number": 0, "string": "foo"}, file)

    # Expect RuntimeError raised when reading JSON as TFRecord file.
    with pytest.raises(RuntimeError, match="Failed to read TFRecord file"):
        ray.data.read_tfrecords(file_path).schema()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__]))
