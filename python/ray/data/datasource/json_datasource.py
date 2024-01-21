from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from ray.data._internal.dataset_logger import DatasetLogger
from ray.data.datasource.file_based_datasource import FileBasedDatasource
from ray.util.annotations import PublicAPI

if TYPE_CHECKING:
    import pyarrow

logger = DatasetLogger(__name__)


@PublicAPI
class JSONDatasource(FileBasedDatasource):
    """JSON datasource, for reading and writing JSON and JSONL files."""

    _FILE_EXTENSIONS = ["json", "jsonl"]

    def __init__(
        self,
        paths: Union[str, List[str]],
        *,
        arrow_json_args: Optional[Dict[str, Any]] = None,
        **file_based_datasource_kwargs,
    ):
        from pyarrow import json

        super().__init__(paths, **file_based_datasource_kwargs)

        if arrow_json_args is None:
            arrow_json_args = {}

        self.read_options = arrow_json_args.pop(
            "read_options", json.ReadOptions(use_threads=False)
        )
        self.arrow_json_args = arrow_json_args

    # TODO(ekl) The PyArrow JSON reader doesn't support streaming reads.
    def _read_stream(self, f: "pyarrow.NativeFile", path: str):
        from io import BytesIO

        import pyarrow as pa

        buffer = f.read_buffer()

        try:
            yield pa.json.read_json(
                BytesIO(buffer),
                read_options=self.read_options,
                **self.arrow_json_args,
            )
        except pa.ArrowInvalid as e:
            logger.get_logger().warning(
                f"Error reading with pyarrow.json.read_json(). "
                f"Falling back to native json.load(), which may be slower. "
                f"PyArrow error was:\n{e}"
            )
            import json

            parsed_json = json.load(BytesIO(buffer))
            yield pa.Table.from_pylist(parsed_json)
