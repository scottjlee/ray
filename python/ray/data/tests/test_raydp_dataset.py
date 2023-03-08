import pytest
import ray
import torch
from ray.data.tests.conftest import *  # noqa


# RayDP tests require Ray Java. Make sure ray jar is built before running this test.
def test_raydp_roundtrip(spark):
    spark_df = spark.createDataFrame([(1, "a"), (2, "b"), (3, "c")], ["one", "two"])
    rows = [(r.one, r.two) for r in spark_df.take(3)]
    ds = ray.data.from_spark(spark_df)
    values = [(r["one"], r["two"]) for r in ds.take(6)]
    assert values == rows
    df = ds.to_spark(spark)
    rows_2 = [(r.one, r.two) for r in df.take(3)]
    assert values == rows_2


def test_raydp_to_spark(spark):
    n = 5
    ds = ray.data.range_table(n)
    values = [r["value"] for r in ds.take(5)]
    df = ds.to_spark(spark)
    rows = [r.value for r in df.take(5)]
    assert values == rows


def test_raydp_to_torch_iter(spark):
    spark_df = spark.createDataFrame([(1, 0), (2, 0), (3, 1)], ["feature", "label"])
    data_size = spark_df.count()
    features = [r["feature"] for r in spark_df.take(data_size)]
    features = torch.tensor(features).reshape(data_size, 1)
    labels = [r["label"] for r in spark_df.take(data_size)]
    labels = torch.tensor(labels).reshape(data_size, 1)
    ds = ray.data.from_spark(spark_df)
    dataset = ds.to_torch(label_column="label", batch_size=3)
    data_features, data_labels = next(dataset.__iter__())
    assert torch.equal(data_features, features) and torch.equal(data_labels, labels)


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-v", __file__]))
