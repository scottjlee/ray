from typing import List

import ray
from ray.data._internal.execution.interfaces import (
    PhysicalOperator,
    RefBundle,
)
from ray.data._internal.execution.operators.input_data_buffer import InputDataBuffer
from ray.data._internal.logical.operators.from_numpy_operator import FromNumpyRefs
from ray.data.block import BlockAccessor, BlockExecStats


def _plan_from_numpy_refs_op(op: FromNumpyRefs) -> PhysicalOperator:
    """Get the corresponding DAG of physical operators for FromNumpyRefs.

    Note this method only converts the given `op`, but not its input dependencies.
    See Planner.plan() for more details.
    """

    def get_input_data() -> List[RefBundle]:
        ref_bundles: List[RefBundle] = []
        for arr in op._ndarrays:
            stats = BlockExecStats.builder()
            block = BlockAccessor.batch_to_block(arr)
            block_metadata = BlockAccessor.for_block(block).get_metadata(
                input_files=None, exec_stats=stats.build()
            )
            ref_bundles.append(
                RefBundle([ray.put(block), block_metadata], owns_blocks=True)
            )
        return ref_bundles

    return InputDataBuffer(input_data_factory=get_input_data)
