import ray
from ray import train
from ray.train import DataConfig, ScalingConfig
from ray.train.torch import TorchTrainer
from ray.data.datasource import file_based_datasource

import torch.distributed as dist
import numpy as np

from benchmark import Benchmark, BenchmarkMetric

from PIL import Image

import time
import torchvision
import torch

from dataset_benchmark_util import get_prop_parquet_paths, get_prop_raw_image_paths


# This benchmark does the following:
# 1) Read files (images or parquet) with ray.data
# 2) Apply preprocessing with map()
# 3) Train TorchTrainer on processed data
# Metrics recorded to the output file are:
# - ray.torchtrainer.fit: Throughput of the final epoch in
#   TorchTrainer.fit() (step 3 above)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--data-root", type=str, help="Root of data directory")
    parser.add_argument(
        "--read-local",
        action="store_true",
        default=False,
        help="Whether to read from local fs for default datasource (S3 otherwise)",
    )
    parser.add_argument(
        "--file-type",
        default="image",
        type=str,
        help="Input file type; choose from: ['image', 'parquet']",
    )
    parser.add_argument(
        "--repeat-ds",
        default=1,
        type=int,
        help="Read the input dataset n times, used to increase the total data size.",
    )
    parser.add_argument(
        "--target-worker-gb",
        default=4,
        type=int,
        help="Number of GB per worker for selecting a subset from default dataset",
    )
    parser.add_argument(
        "--read-task-cpus",
        default=1,
        type=int,
        help="Number of CPUs specified for read task",
    )
    parser.add_argument(
        "--batch-size",
        default=32,
        type=int,
        help="Batch size to use.",
    )
    parser.add_argument(
        "--num-epochs",
        # Use 3 epochs and report the throughput of the last epoch, in case
        # there is warmup in the first epoch.
        default=3,
        type=int,
        help="Number of epochs to run. The throughput for the last epoch will be kept.",
    )
    parser.add_argument(
        "--num-workers",
        default=1,
        type=int,
        help="Number of workers.",
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        default=False,
        help="Whether to use GPU with TorchTrainer.",
    )
    parser.add_argument(
        "--local-shuffle-buffer-size",
        default=200,
        type=int,
        help="Parameter into ds.iter_batches(local_shuffle_buffer_size=...)",
    )
    parser.add_argument(
        "--preserve-order",
        action="store_true",
        default=False,
        help="Whether to configure Train with preserve_order flag.",
    )
    args = parser.parse_args()

    if args.data_root is None:
        # use default datasets if data root is not provided
        if args.file_type == "image":
            args.data_root = get_prop_raw_image_paths(
                num_workers=args.num_workers, target_worker_gb=args.target_worker_gb
            )
        elif args.file_type == "parquet":
            args.data_root = get_prop_parquet_paths(
                num_workers=args.num_workers, target_worker_gb=args.target_worker_gb
            )
        else:
            raise Exception(
                f"Unknown file type {args.file_type}; "
                "expected one of: ['image', 'parquet']"
            )
        if args.repeat_ds > 1:
            args.data_root = [args.data_root] * args.repeat_ds
    return args


# Constants and utility methods for image-based benchmarks.
DEFAULT_IMAGE_SIZE = 224


def get_transform(to_torch_tensor):
    # Note(swang): This is a different order from tf.data.
    # torch: decode -> randCrop+resize -> randFlip
    # tf.data: decode -> randCrop -> randFlip -> resize
    transform = torchvision.transforms.Compose(
        [
            torchvision.transforms.RandomResizedCrop(
                size=DEFAULT_IMAGE_SIZE,
                scale=(0.05, 1.0),
                ratio=(0.75, 1.33),
            ),
            torchvision.transforms.RandomHorizontalFlip(),
        ]
        + ([torchvision.transforms.ToTensor()] if to_torch_tensor else [])
    )
    return transform


def crop_and_flip_image(row):
    transform = get_transform(False)
    # Make sure to use torch.tensor here to avoid a copy from numpy.
    row["image"] = transform(torch.tensor(np.transpose(row["image"], axes=(2, 0, 1))))
    return row


def decode_image_crop_and_flip(row):
    transform = get_transform(False)
    row["image"] = Image.frombytes("RGB", (row["height"], row["width"]), row["image"])
    del row["width"]
    del row["height"]
    # Convert back np to avoid storing a np.object array.
    row["image"] = np.array(transform(row["image"]))
    return row


def train_loop_per_worker():
    it = train.get_dataset_shard("train")
    device = train.torch.get_device()

    for i in range(args.num_epochs):
        print(f"Epoch {i+1} of {args.num_epochs}")
        num_rows = 0
        start_t = time.time()
        for batch in it.iter_torch_batches(
            batch_size=args.batch_size,
        ):
            num_rows += args.batch_size
        end_t = time.time()

    # Workaround to report the final epoch time from each worker, so that we
    # can sum up the times at the end when calculating throughput.
    # See: https://github.com/ray-project/ray/issues/39277
    world_size = ray.train.get_context().get_world_size()
    all_workers_time_list = [
        torch.zeros((2), dtype=torch.double, device=device) for _ in range(world_size)
    ]
    curr_worker_time = torch.tensor([start_t, end_t], dtype=torch.double, device=device)
    dist.all_gather(all_workers_time_list, curr_worker_time)

    all_num_rows = [
        torch.zeros((1), dtype=torch.int32, device=device) for _ in range(world_size)
    ]
    curr_num_rows = torch.tensor([num_rows], dtype=torch.int32, device=device)
    dist.all_gather(all_num_rows, curr_num_rows)

    train.report(
        {
            "time_final_epoch": [tensor.tolist() for tensor in all_workers_time_list],
            "num_rows": [tensor.item() for tensor in all_num_rows],
        }
    )


def benchmark_code(
    args,
    cache_output_ds=False,
    cache_input_ds=False,
):
    """
    - cache_output_ds: Cache output dataset (ds.materialize()) after preprocessing fn.
    - cache_input_ds: Cache input dataset, then apply a preprocessing fn.
    """
    assert (
        sum([cache_output_ds, cache_input_ds]) <= 1
    ), "Can only test one caching variant at a time"

    # 1) Read in data with read_images() / read_parquet()
    if args.file_type == "image":
        ray_dataset = ray.data.read_images(
            args.data_root,
            mode="RGB",
            ray_remote_args={"num_cpus": args.read_task_cpus},
        )
    elif args.file_type == "parquet":
        ray_dataset = ray.data.read_parquet(
            args.data_root,
            ray_remote_args={"num_cpus": args.read_task_cpus},
        )
    else:
        raise Exception(f"Unknown file type {args.file_type}")

    if cache_input_ds:
        ray_dataset = ray_dataset.materialize()

    # 2) Preprocess data by applying transformation with map/map_batches()
    if args.file_type == "image":
        ray_dataset = ray_dataset.map(crop_and_flip_image, num_cpus=args.read_task_cpus)
    elif args.file_type == "parquet":
        ray_dataset = ray_dataset.map(decode_image_crop_and_flip)
    if cache_output_ds:
        ray_dataset = ray_dataset.materialize()

    # 3) Train TorchTrainer on processed data
    options = DataConfig.default_ingest_options()
    options.preserve_order = args.preserve_order

    if args.num_workers == 1 or args.use_gpu:
        torch_trainer = TorchTrainer(
            train_loop_per_worker,
            datasets={"train": ray_dataset},
            scaling_config=ScalingConfig(
                num_workers=args.num_workers,
                use_gpu=args.use_gpu,
            ),
            dataset_config=ray.train.DataConfig(
                execution_options=options,
            ),
        )
    else:
        torch_trainer = TorchTrainer(
            train_loop_per_worker,
            datasets={"train": ray_dataset},
            # In the multi-node case without GPUs, we use a SPREAD placement strategy
            # to ensure that tasks are spread across nodes. We reserve one worker
            # for the driver.
            scaling_config=ScalingConfig(
                num_workers=args.num_workers - 1,
                use_gpu=args.use_gpu,
                placement_strategy="STRICT_SPREAD",
            ),
            dataset_config=ray.train.DataConfig(
                execution_options=options,
            ),
        )

    result = torch_trainer.fit()

    # Report the throughput of the last epoch, sum runtime across all workers.
    time_start_last_epoch, time_end_last_epoch = zip(
        *result.metrics["time_final_epoch"]
    )
    runtime_last_epoch = max(time_end_last_epoch) - min(time_start_last_epoch)
    num_rows_last_epoch = sum(result.metrics["num_rows"])
    tput_last_epoch = num_rows_last_epoch / runtime_last_epoch

    return {
        BenchmarkMetric.THROUGHPUT.value: tput_last_epoch,
    }


if __name__ == "__main__":
    # Workaround for FileBasedDatasource parallel read issue when reading many sources.
    file_based_datasource.FILE_SIZE_FETCH_PARALLELIZATION_THRESHOLD = 1000
    args = parse_args()
    benchmark_name = (
        f"read_{args.file_type}_repeat{args.repeat_ds}_train_{args.num_workers}workers"
    )
    if args.preserve_order:
        benchmark_name = f"{benchmark_name}_preserve_order"

    benchmark = Benchmark(benchmark_name)

    benchmark.run_fn("cache-none", benchmark_code, args=args)
    benchmark.run_fn("cache-output", benchmark_code, args=args, cache_output_ds=True)
    benchmark.run_fn("cache-input", benchmark_code, args=args, cache_input_ds=True)
    # TODO: enable after implementing prepartition case.
    # benchmark.run_fn(
    # "prepartition-ds", benchmark_code, args=args, prepartition_ds=True,
    # )
    benchmark.write_result("/tmp/multi_node_train_benchmark.json")
