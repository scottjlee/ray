from typing import TYPE_CHECKING, List, Union

try:
    import pyarrow
except ImportError:
    pyarrow = None

if TYPE_CHECKING:
    from ray.data._internal.sort import SortKeyT


def sort(table: "pyarrow.Table", key: "SortKeyT", descending: bool) -> "pyarrow.Table":
    import pyarrow.compute as pac

    indices = pac.sort_indices(table, sort_keys=key)
    return take_table(table, indices)


def take_table(
    table: "pyarrow.Table",
    indices: Union[List[int], "pyarrow.Array", "pyarrow.ChunkedArray"],
) -> "pyarrow.Table":
    """Select rows from the table.

    This method is an alternative to pyarrow.Table.take(), which breaks for
    extension arrays. This is exposed as a static method for easier use on
    intermediate tables, not underlying an ArrowBlockAccessor.
    """
    from ray.air.util.transform_pyarrow import (
        _is_column_extension_type,
        _concatenate_extension_column,
    )

    if any(_is_column_extension_type(col) for col in table.columns):
        new_cols = []
        for col in table.columns:
            if _is_column_extension_type(col):
                # .take() will concatenate internally, which currently breaks for
                # extension arrays.
                col = _concatenate_extension_column(col)
            new_cols.append(col.take(indices))
        table = pyarrow.Table.from_arrays(new_cols, schema=table.schema)
    else:
        table = table.take(indices)
    return table


def unify_schemas(
    schemas: List["pyarrow.Schema"],
) -> "pyarrow.Schema":
    """Version of `pyarrow.unify_schemas()` which also handles checks for
    variable-shaped tensors in the given schemas."""
    from ray.air.util.tensor_extensions.arrow import (
        ArrowTensorType,
        ArrowVariableShapedTensorType,
    )
    import pyarrow as pa

    schemas_to_unify = []
    schema_tensor_field_overrides = {}
    # column rollup for opaque (null-type) lists here
    cols_with_null_list = set()
    for schema in schemas:
        for col_name in schema.names:
            col_type = schema.field(col_name).type
            if pa.types.is_list(col_type) and pa.types.is_null(col_type.value_type):
                cols_with_null_list.add(col_name)

    if any(isinstance(type_, pyarrow.ExtensionType) for type_ in schemas[0].types):
        # If we have pyarrow extension types that may potentially be variable shaped,
        # examine the first schema to gather the columns that need type conversions.
        for col_idx in range(len(schemas[0].types)):
            tensor_array_types = [
                s.types[col_idx]
                for s in schemas
                if isinstance(s.types[col_idx], pyarrow.ExtensionType)
            ]
            if ArrowTensorType._need_variable_shaped_tensor_array(tensor_array_types):
                if isinstance(tensor_array_types[0], ArrowVariableShapedTensorType):
                    new_type = tensor_array_types[0]
                elif isinstance(tensor_array_types[0], ArrowTensorType):
                    new_type = ArrowVariableShapedTensorType(
                        dtype=tensor_array_types[0].scalar_type,
                        ndim=len(tensor_array_types[0].shape),
                    )
                else:
                    raise ValueError(
                        "Detected need for variable shaped tensor representation, "
                        f"but schema is not ArrayTensorType: {tensor_array_types[0]}"
                    )
                schema_tensor_field_overrides[col_idx] = new_type

    if cols_with_null_list:
        for col_name in cols_with_null_list:
            scalar_type = None
            for schema in schemas:
                col_type = schema.field(col_name).type
                if not pa.types.is_list(col_type) or not pa.types.is_null(
                    col_type.value_type
                ):
                    scalar_type = col_type
                    break
            if scalar_type is not None:
                col_idx = schema.get_field_index(col_name)
                schema_tensor_field_overrides[col_idx] = scalar_type

        # if any of the columns in any block has the opaque list type,
        # override with the scalar type
    if schema_tensor_field_overrides:
        # Go through all schemas and update the types of columns from the above loop.
        for schema in schemas:
            for col_idx, col_new_type in schema_tensor_field_overrides.items():
                var_shaped_col = schema.field(col_idx).with_type(col_new_type)
                schema = schema.set(col_idx, var_shaped_col)
            schemas_to_unify.append(schema)
    else:
        schemas_to_unify = schemas
    # Let Arrow unify the schema of non-tensor extension type columns.
    return pyarrow.unify_schemas(schemas_to_unify)


def _concatenate_chunked_arrays(arrs: "pyarrow.ChunkedArray") -> "pyarrow.ChunkedArray":
    """
    Concatenate provided chunked arrays into a single chunked array.
    """
    from ray.data.extensions import (
        ArrowTensorType,
        ArrowVariableShapedTensorType,
    )

    # Single flat list of chunks across all chunked arrays.
    chunks = []
    type_ = None
    for arr in arrs:
        if type_ is None:
            type_ = arr.type
        else:
            if isinstance(type_, (ArrowTensorType, ArrowVariableShapedTensorType)):
                raise ValueError(
                    "_concatenate_chunked_arrays should only be used on non-tensor "
                    f"extension types, but got a chunked array of type {type_}."
                )
            assert type_ == arr.type, f"Types mismatch: {type_} != {arr.type}"
        # Add chunks for this chunked array to flat chunk list.
        chunks.extend(arr.chunks)
    # Construct chunked array on flat list of chunks.
    return pyarrow.chunked_array(chunks, type=type_)


def concat(blocks: List["pyarrow.Table"]) -> "pyarrow.Table":
    """Concatenate provided Arrow Tables into a single Arrow Table. This has special
    handling for extension types that pyarrow.concat_tables does not yet support.
    """
    from ray.data.extensions import (
        ArrowTensorArray,
        ArrowTensorType,
        ArrowVariableShapedTensorType,
    )
    import pyarrow as pa

    if not blocks:
        # Short-circuit on empty list of blocks.
        return blocks

    if len(blocks) == 1:
        return blocks[0]

    cols_with_null_list = set()
    for b in blocks:
        for col_name in b.schema.names:
            col_type = b.schema.field(col_name).type
            if pa.types.is_list(col_type) and pa.types.is_null(col_type.value_type):
                cols_with_null_list.add(col_name)

    schema = blocks[0].schema
    if (
        any(isinstance(type_, pa.ExtensionType) for type_ in schema.types)
        or cols_with_null_list
    ):
        # Custom handling for extension array columns.
        cols = []
        for col_name in schema.names:
            col_chunked_arrays = []
            for block in blocks:
                col_chunked_arrays.append(block.column(col_name))
            if isinstance(
                schema.field(col_name).type,
                (ArrowTensorType, ArrowVariableShapedTensorType),
            ):
                # For our tensor extension types, manually construct a chunked array
                # containing chunks from all blocks. This is to handle
                # homogeneous-shaped block columns having different shapes across
                # blocks: if tensor element shapes differ across blocks, a
                # variable-shaped tensor array will be returned.
                col = ArrowTensorArray._chunk_tensor_arrays(
                    [chunk for ca in col_chunked_arrays for chunk in ca.chunks]
                )
            else:
                if col_name in cols_with_null_list:
                    scalar_type = None
                    for arr in col_chunked_arrays:
                        if not pa.types.is_list(arr.type) or not pa.types.is_null(
                            arr.type.value_type
                        ):
                            scalar_type = arr.type
                            break

                    for c_idx in range(len(col_chunked_arrays)):
                        c = col_chunked_arrays[c_idx]
                        if not pa.types.is_list(c.type) or not pa.types.is_null(
                            c.type.value_type
                        ):
                            col_chunked_arrays[c_idx] = c
                        elif pa.types.is_null(c.type.value_type):
                            if pa.types.is_list(scalar_type):
                                col_chunked_arrays[c_idx] = col_chunked_arrays[
                                    c_idx
                                ].cast(scalar_type)
                            else:
                                col_chunked_arrays[c_idx] = pa.chunked_array(
                                    [pa.nulls(c.length(), type=scalar_type)]
                                )
                col = _concatenate_chunked_arrays(col_chunked_arrays)
            cols.append(col)

        # If the result contains pyarrow schemas, unify them
        schemas_to_unify = [b.schema for b in blocks]
        if pyarrow is not None and any(
            isinstance(s, pyarrow.Schema) for s in schemas_to_unify
        ):
            schema = unify_schemas(schemas_to_unify)
        else:
            # Otherwise, if the resulting schemas are simple types (e.g. int),
            # check that all blocks with valid schemas have the same type.
            schema = schemas_to_unify[0]
            if schema is not None:
                for s in schemas_to_unify:
                    if s is not None and s != schema:
                        raise ValueError(
                            "Found blocks with different types "
                            f"in schemas: {schemas_to_unify}"
                        )
        # Build the concatenated table.
        table = pyarrow.Table.from_arrays(cols, schema=schema)
        # Validate table schema (this is a cheap check by default).
        table.validate()
    else:
        # No extension array columns, so use built-in pyarrow.concat_tables.
        table = pyarrow.concat_tables(blocks, promote=True)
    return table


def concat_and_sort(
    blocks: List["pyarrow.Table"], key: "SortKeyT", descending: bool
) -> "pyarrow.Table":
    ret = concat(blocks)
    indices = pyarrow.compute.sort_indices(ret, sort_keys=key)
    return take_table(ret, indices)
