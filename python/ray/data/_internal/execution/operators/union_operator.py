from typing import List, Optional

from ray.data._internal.execution.interfaces import (
    ExecutionOptions,
    PhysicalOperator,
    RefBundle,
)
from ray.data._internal.execution.operators.base_physical_operator import NAryOperator
from ray.data._internal.stats import StatsDict


class UnionOperator(NAryOperator):
    """An operator that combines blocks from input operators."""

    def __init__(
        self,
        *input_ops: PhysicalOperator,
    ):
        """Create a UnionOperator.

        Args:
            input_ops: Operators generating input data for this operator to union.
        """
        # Intermediary buffers used to store blocks from each input dependency
        # when order is preserved.
        self._input_buffers: List[List[RefBundle]] = [[] for _ in range(len(input_ops))]

        # The index of the input dependency that is currently the source of
        # the output buffer. New inputs from this input dependency will be added
        # directly to the output buffer. Only used when order is preserved.
        self._input_idx_to_output = 0

        self._output_buffer: List[RefBundle] = []
        self._stats: StatsDict = {}
        super().__init__(*input_ops)

    def start(self, options: ExecutionOptions):
        # Whether to preserve the order of the input data (both the
        # order of the input operators and the order of the blocks within).
        self._preserve_order = options.preserve_order
        super().start(options)

    def num_outputs_total(self) -> Optional[int]:
        num_outputs = 0
        for input_op in self.input_dependencies:
            op_num_outputs = input_op.num_outputs_total()
            # If at least one of the input ops has an unknown number of outputs,
            # the number of outputs of the union operator is unknown.
            if op_num_outputs is None:
                return None
            num_outputs += op_num_outputs
        return num_outputs

    def add_input(self, refs: RefBundle, input_index: int) -> None:
        assert not self.completed()
        assert 0 <= input_index <= len(self._input_dependencies), input_index

        curr_input_op = self._input_dependencies[input_index]
        if not self._preserve_order:
            self._output_buffer.append(refs)
        else:
            if input_index == self._input_idx_to_output:
                print(f"===> adding {input_index} to output")
                self._output_buffer.append(refs)
                if curr_input_op.completed():
                    next_input_idx = input_index + 1
                    print(f"===> input op {input_index} finished,")
                    if next_input_idx < len(self._input_buffers):
                        print(f"===>  moving into {next_input_idx}")
                        self._output_buffer.extend(self._input_buffers[next_input_idx])
                        self._input_buffers[next_input_idx].clear()
                        self._input_idx_to_output += 1
            else:
                print(f"===> adding at index {input_index}")
                self._input_buffers[input_index].append(refs)

    def inputs_done(self) -> None:
        # Note that in the case where order is not preserved, all inputs
        # are directly added to the output buffer as soon as they are received,
        # so there is no need to clear any intermediary buffers.
        if self._preserve_order:
            # Add any remaining blocks from the final input dependency to the
            # output buffer.
            self._output_buffer.extend(self._input_buffers[self._input_idx_to_output])
            self._input_buffers[self._input_idx_to_output].clear()
            for idx, input_buffer in enumerate(self._input_buffers):
                assert (
                    len(input_buffer) == 0
                ), f"Input at index {idx} still has {len(input_buffer)} blocks remaining."
        super().inputs_done()

    def has_next(self) -> bool:
        # Check if the output buffer still contains at least one block.
        return len(self._output_buffer) > 0

    def get_next(self) -> RefBundle:
        return self._output_buffer.pop(0)

    def get_stats(self) -> StatsDict:
        return self._stats
