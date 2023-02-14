from typing import TYPE_CHECKING, Any, Callable, Dict, Union, Iterable, Iterator
import struct

import numpy as np

from ray.util.annotations import PublicAPI
from ray.data._internal.util import _check_import
from ray.data.block import Block, BlockAccessor
from ray.data.datasource.file_based_datasource import FileBasedDatasource

if TYPE_CHECKING:
    import pyarrow
    import tensorflow as tf


@PublicAPI(stability="alpha")
class TFRecordDatasource(FileBasedDatasource):

    _FILE_EXTENSION = "tfrecords"

    def _read_stream(
        self, f: "pyarrow.NativeFile", path: str, **reader_args
    ) -> Iterator[Block]:
        from google.protobuf.message import DecodeError
        import pyarrow as pa
        import tensorflow as tf

        for record in _read_records(f, path):
            example = tf.train.Example()
            try:
                example.ParseFromString(record)
            except DecodeError as e:
                raise ValueError(
                    "`TFRecordDatasource` failed to parse `tf.train.Example` "
                    f"record in '{path}'. This error can occur if your TFRecord "
                    f"file contains a message type other than `tf.train.Example`: {e}"
                )

            yield pa.Table.from_pydict(_convert_example_to_dict(example))

    def _write_block(
        self,
        f: "pyarrow.NativeFile",
        block: BlockAccessor,
        writer_args_fn: Callable[[], Dict[str, Any]] = lambda: {},
        **writer_args,
    ) -> None:

        _check_import(self, module="crc32c", package="crc32c")

        arrow_table = block.to_arrow()

        # It seems like TFRecords are typically row-based,
        # https://www.tensorflow.org/tutorials/load_data/tfrecord#writing_a_tfrecord_file_2
        # so we must iterate through the rows of the block,
        # serialize to tf.train.Example proto, and write to file.

        examples = _convert_arrow_table_to_examples(arrow_table)

        # Write each example to the arrow file in the TFRecord format.
        for example in examples:
            _write_record(f, example)


def _convert_example_to_dict(
    example: "tf.train.Example",
) -> Dict[str, "pyarrow.Array"]:
    record = {}
    for feature_name, feature in example.features.feature.items():
        record[feature_name] = _get_feature_value(feature)
    return record


def _convert_arrow_table_to_examples(
    arrow_table: "pyarrow.Table",
) -> Iterable["tf.train.Example"]:
    import tensorflow as tf

    # Serialize each row[i] of the block to a tf.train.Example and yield it.
    for i in range(arrow_table.num_rows):

        # First, convert row[i] to a dictionary.
        features: Dict[str, "tf.train.Feature"] = {}
        for name in arrow_table.column_names:
            features[name] = _value_to_feature(arrow_table[name][i])

        # Convert the dictionary to an Example proto.
        proto = tf.train.Example(features=tf.train.Features(feature=features))

        yield proto


def _get_feature_value(
    feature: "tf.train.Feature",
) -> "pyarrow.Array":
    import pyarrow as pa

    values = (
        feature.HasField("int64_list"),
        feature.HasField("float_list"),
        feature.HasField("bytes_list"),
    )
    # Exactly one of `bytes_list`, `float_list`, and `int64_list` should contain data.
    # Otherwise, all three should be empty lists, indicating an empty feature value.
    assert sum(bool(value) for value in values) <= 1

    if feature.HasField("bytes_list"):
        value = feature.bytes_list.value
        type_ = pa.binary()
    elif feature.HasField("float_list"):
        value = feature.float_list.value
        type_ = pa.float32()
    elif feature.HasField("int64_list"):
        value = feature.int64_list.value
        type_ = pa.int64()
    else:
        value = []
        type_ = pa.null()
    value = list(value)
    if len(value) == 1:
        # Use the value itself if the features contains a single value.
        # This is to give better user experience when writing preprocessing UDF on
        # these single-value lists.
        value = value[0]
    else:
        # If the feature value is empty, set the type to null for now
        # to allow pyarrow to construct a valid Array; later, infer the
        # type from other records which have non-empty values for the feature.
        if len(value) == 0:
            type_ = pa.null()
        type_ = pa.list_(type_)
    return pa.array([value], type=type_)


def _value_to_feature(
    value: Union["pyarrow.Scalar", "pyarrow.Array"]
) -> "tf.train.Feature":
    import tensorflow as tf
    import pyarrow as pa

    if isinstance(value, pa.ListScalar):
        # Use the underlying type of the ListScalar's value in
        # determining the output feature's data type.
        value_type = value.type.value_type
        value = value.as_py()
    else:
        value_type = value.type
        value = value.as_py()
        if value is None:
            value = []
        else:
            value = [value]

    if pa.types.is_integer(value_type):
        return tf.train.Feature(int64_list=tf.train.Int64List(value=value))
    if pa.types.is_floating(value_type):
        return tf.train.Feature(float_list=tf.train.FloatList(value=value))
    if pa.types.is_binary(value_type):
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=value))
    if pa.types.is_null(value_type):
        raise ValueError(
            "Unable to infer type from partially missing column. "
            "Try setting read parallelism = 1, or use an input data source which "
            "explicitly specifies the schema."
        )
    raise ValueError(
        f"Value is of type {value_type}, "
        "which we cannot convert to a supported tf.train.Feature storage type "
        "(bytes, float, or int)."
    )


# Adapted from https://github.com/vahidk/tfrecord/blob/74b2d24a838081356d993ec0e147eaf59ccd4c84/tfrecord/reader.py#L16-L96  # noqa: E501
#
# MIT License
#
# Copyright (c) 2020 Vahid Kazemi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
def _read_records(
    file: "pyarrow.NativeFile",
    path: str,
) -> Iterable[memoryview]:
    """
    Read records from TFRecord file.

    A TFRecord file contains a sequence of records. The file can only be read
    sequentially. Each record is stored in the following formats:
        uint64 length
        uint32 masked_crc32_of_length
        byte   data[length]
        uint32 masked_crc32_of_data

    See https://www.tensorflow.org/tutorials/load_data/tfrecord#tfrecords_format_details
    for more details.
    """
    length_bytes = bytearray(8)
    crc_bytes = bytearray(4)
    datum_bytes = bytearray(1024 * 1024)
    row_count = 0
    while True:
        try:
            # Read "length" field.
            num_length_bytes_read = file.readinto(length_bytes)
            if num_length_bytes_read == 0:
                break
            elif num_length_bytes_read != 8:
                raise ValueError(
                    "Failed to read the length of record data. Expected 8 bytes but "
                    "got {num_length_bytes_read} bytes."
                )

            # Read "masked_crc32_of_length" field.
            num_length_crc_bytes_read = file.readinto(crc_bytes)
            if num_length_crc_bytes_read != 4:
                raise ValueError(
                    "Failed to read the length of CRC-32C hashes. Expected 4 bytes "
                    "but got {num_length_crc_bytes_read} bytes."
                )

            # Read "data[length]" field.
            (data_length,) = struct.unpack("<Q", length_bytes)
            if data_length > len(datum_bytes):
                datum_bytes = datum_bytes.zfill(int(data_length * 1.5))
            datum_bytes_view = memoryview(datum_bytes)[:data_length]
            num_datum_bytes_read = file.readinto(datum_bytes_view)
            if num_datum_bytes_read != data_length:
                raise ValueError(
                    f"Failed to read the record. Exepcted {data_length} bytes but got "
                    f"{num_datum_bytes_read} bytes."
                )

            # Read "masked_crc32_of_data" field.
            # TODO(chengsu): ideally we should check CRC-32C against the actual data.
            num_crc_bytes_read = file.readinto(crc_bytes)
            if num_crc_bytes_read != 4:
                raise ValueError(
                    "Failed to read the CRC-32C hashes. Expected 4 bytes but got "
                    f"{num_crc_bytes_read} bytes."
                )

            # Return the data.
            yield datum_bytes_view

            row_count += 1
            data_length = None
        except Exception as e:
            error_message = (
                f"Failed to read TFRecord file {path}. Please ensure that the "
                f"TFRecord file has correct format. Already read {row_count} rows."
            )
            if data_length is not None:
                error_message += f" Byte size of current record data is {data_length}."
            raise RuntimeError(error_message) from e


# Adapted from https://github.com/vahidk/tfrecord/blob/74b2d24a838081356d993ec0e147eaf59ccd4c84/tfrecord/writer.py#L57-L72  # noqa: E501
#
# MIT License
#
# Copyright (c) 2020 Vahid Kazemi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


def _write_record(
    file: "pyarrow.NativeFile",
    example: "tf.train.Example",
) -> None:
    record = example.SerializeToString()
    length = len(record)
    length_bytes = struct.pack("<Q", length)
    file.write(length_bytes)
    file.write(_masked_crc(length_bytes))
    file.write(record)
    file.write(_masked_crc(record))


def _masked_crc(data: bytes) -> bytes:
    """CRC checksum."""
    import crc32c

    mask = 0xA282EAD8
    crc = crc32c.crc32(data)
    masked = ((crc >> 15) | (crc << 17)) + mask
    masked = np.uint32(masked & np.iinfo(np.uint32).max)
    masked_bytes = struct.pack("<I", masked)
    return masked_bytes
