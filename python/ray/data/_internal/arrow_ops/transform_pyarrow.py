from typing import TYPE_CHECKING, List, Union

from ray.air.util.tensor_extensions.arrow import (
    ArrowTensorType,
    ArrowVariableShapedTensorType,
)

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
    schemas_to_unify = []
    schema_tensor_field_overrides = {}

    if type(schemas[0]) == pyarrow.Schema:
        if any(isinstance(type_, pyarrow.ExtensionType) for type_ in schemas[0].types):
            for col_idx in range(len(schemas[0].types)):
                column_types = [s.types[col_idx] for s in schemas]
                if ArrowTensorType._need_variable_shaped_tensor_array(column_types):
                    new_type = ArrowVariableShapedTensorType(
                        dtype=column_types[0].scalar_type,
                        ndim=len(column_types[0].shape),
                    )
                    schema_tensor_field_overrides[col_idx] = new_type
            for schema in schemas:
                for col_idx, col_new_type in schema_tensor_field_overrides.items():
                    var_shaped_col = schema.field(col_idx).with_type(col_new_type)
                    schema = schema.set(col_idx, var_shaped_col)
                schemas_to_unify.append(schema)
        else:
            schemas_to_unify = schemas
    print("===> schemas_to_unify:", schemas_to_unify)
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
            assert type_ == arr.type
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

    if not blocks:
        # Short-circuit on empty list of blocks.
        return blocks

    if len(blocks) == 1:
        return blocks[0]

    schema = blocks[0].schema
    if any(isinstance(type_, pyarrow.ExtensionType) for type_ in schema.types):
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
                col = _concatenate_chunked_arrays(col_chunked_arrays)
            cols.append(col)
        # Unify schemas.
        schema = unify_schemas([b.schema for b in blocks])
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
