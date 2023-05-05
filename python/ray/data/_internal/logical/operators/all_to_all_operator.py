from typing import Any, Dict, List, Optional

from ray.data._internal.logical.interfaces import LogicalOperator
from ray.data._internal.progress_bar import ProgressBar
from ray.data.aggregate import AggregateFn


class AbstractAllToAll(LogicalOperator):
    """Abstract class for logical operators should be converted to physical
    AllToAllOperator.
    """

    def __init__(
        self,
        name: str,
        input_op: LogicalOperator,
        num_outputs: Optional[int] = None,
        sub_progress_bar_names: Optional[List[str]] = None,
        ray_remote_args: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            name: Name for this operator. This is the name that will appear when
                inspecting the logical plan of a Datastream.
            input_op: The operator preceding this operator in the plan DAG. The outputs
                of `input_op` will be the inputs to this operator.
            num_outputs: The number of expected output bundles outputted by this
                operator.
            ray_remote_args: Args to provide to ray.remote.
        """
        super().__init__(name, [input_op])
        self._num_outputs = num_outputs
        self._ray_remote_args = ray_remote_args or {}
        self._sub_progress_bar_names = sub_progress_bar_names
        self._sub_progress_bar_dict = None

    def num_outputs_total(self) -> Optional[int]:
        if self._num_outputs:
            return self._num_outputs
        return getattr(self.input_op, "_num_outputs", 0)
    
    def initialize_sub_progress_bars(self, position: int) -> int:
        """Initialize all internal sub progress bars, and return the number of bars."""
        if self._sub_progress_bar_names is not None:
            self._sub_progress_bar_dict = {}
            for name in self._sub_progress_bar_names:
                print(
                    f"===> initialinzing subprog bar {name} with {self.num_outputs_total()} total outputs:"
                )
                bar = ProgressBar(name, self.num_outputs_total() or 1, position)
                # NOTE: call `set_description` to trigger the initial print of progress
                # bar on console.
                bar.set_description(f"  *- {name}")
                self._sub_progress_bar_dict[name] = bar
                position += 1
            return len(self._sub_progress_bar_dict)
        else:
            return 0

    def close_sub_progress_bars(self):
        """Close all internal sub progress bars."""
        if self._sub_progress_bar_dict is not None:
            for sub_bar in self._sub_progress_bar_dict.values():
                sub_bar.close()


class RandomizeBlocks(AbstractAllToAll):
    """Logical operator for randomize_block_order."""

    def __init__(
        self,
        input_op: LogicalOperator,
        seed: Optional[int] = None,
    ):
        super().__init__(
            "RandomizeBlocks",
            input_op,
        )
        self._seed = seed


class RandomShuffle(AbstractAllToAll):
    """Logical operator for random_shuffle."""

    def __init__(
        self,
        input_op: LogicalOperator,
        seed: Optional[int] = None,
        num_outputs: Optional[int] = None,
        ray_remote_args: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            "RandomShuffle",
            input_op,
            num_outputs=num_outputs,
            sub_progress_bar_names=["Shuffle Map", "Shuffle Reduce"],
            ray_remote_args=ray_remote_args,
        )
        self._seed = seed


class Repartition(AbstractAllToAll):
    """Logical operator for repartition."""

    def __init__(
        self,
        input_op: LogicalOperator,
        num_outputs: int,
        shuffle: bool,
    ):
        super().__init__(
            "Repartition",
            input_op,
            num_outputs=num_outputs,
            sub_progress_bar_names=["Shuffle Map", "Shuffle Reduce"],
        )
        self._shuffle = shuffle


class Sort(AbstractAllToAll):
    """Logical operator for sort."""

    def __init__(
        self,
        input_op: LogicalOperator,
        key: Optional[str],
        descending: bool,
    ):
        super().__init__(
            "Sort",
            input_op,
            sub_progress_bar_names=["Sort Sample", "Shuffle Map", "Shuffle Reduce"],
        )
        self._key = key
        self._descending = descending


class Aggregate(AbstractAllToAll):
    """Logical operator for aggregate."""

    def __init__(
        self,
        input_op: LogicalOperator,
        key: Optional[str],
        aggs: List[AggregateFn],
    ):
        super().__init__(
            "Aggregate",
            input_op,
        )
        self._key = key
        self._aggs = aggs
