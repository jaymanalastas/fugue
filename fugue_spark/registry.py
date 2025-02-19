from typing import Any, Optional, Tuple

import pyspark.rdd as pr
import pyspark.sql as ps
from pyspark import SparkContext
from pyspark.sql import SparkSession
from triad import run_at_def

from fugue import DataFrame, ExecutionEngine, register_execution_engine
from fugue.dev import (
    DataFrameParam,
    ExecutionEngineParam,
    annotated_param,
    is_pandas_or,
)
from fugue.extensions import namespace_candidate
from fugue.plugins import as_fugue_dataset, infer_execution_engine, parse_creator
from fugue_spark.dataframe import SparkDataFrame
from fugue_spark.execution_engine import SparkExecutionEngine

_is_sparksql = namespace_candidate("sparksql", lambda x: isinstance(x, str))


@infer_execution_engine.candidate(
    lambda objs: is_pandas_or(objs, (ps.DataFrame, SparkDataFrame))
    or any(_is_sparksql(obj) for obj in objs)
)
def _infer_spark_client(obj: Any) -> Any:
    return SparkSession.builder.getOrCreate()


@as_fugue_dataset.candidate(lambda df, **kwargs: isinstance(df, ps.DataFrame))
def _spark_as_fugue_df(df: ps.DataFrame, **kwargs: Any) -> SparkDataFrame:
    return SparkDataFrame(df, **kwargs)


@parse_creator.candidate(_is_sparksql)
def _parse_sparksql_creator(sql: Tuple[str, str]):
    def _run_sql(spark: SparkSession) -> ps.DataFrame:
        return spark.sql(sql[1])

    return _run_sql


def _register_engines() -> None:
    register_execution_engine(
        "spark",
        lambda conf, **kwargs: SparkExecutionEngine(conf=conf),
        on_dup="ignore",
    )
    register_execution_engine(
        SparkSession,
        lambda session, conf, **kwargs: SparkExecutionEngine(session, conf=conf),
        on_dup="ignore",
    )


@annotated_param(SparkExecutionEngine)
class _SparkExecutionEngineParam(ExecutionEngineParam):
    pass


@annotated_param(SparkSession)
class _SparkSessionParam(ExecutionEngineParam):
    def to_input(self, engine: ExecutionEngine) -> Any:
        assert isinstance(engine, SparkExecutionEngine)
        return engine.spark_session  # type:ignore


@annotated_param(SparkContext)
class _SparkContextParam(ExecutionEngineParam):
    def to_input(self, engine: ExecutionEngine) -> Any:
        assert isinstance(engine, SparkExecutionEngine)
        return engine.spark_session.sparkContext  # type:ignore


@annotated_param(ps.DataFrame)
class _SparkDataFrameParam(DataFrameParam):
    def to_input_data(self, df: DataFrame, ctx: Any) -> Any:
        assert isinstance(ctx, SparkExecutionEngine)
        return ctx.to_df(df).native

    def to_output_df(self, output: Any, schema: Any, ctx: Any) -> DataFrame:
        assert isinstance(output, ps.DataFrame)
        assert isinstance(ctx, SparkExecutionEngine)
        return ctx.to_df(output, schema=schema)

    def count(self, df: Any) -> int:  # pragma: no cover
        raise NotImplementedError("not allowed")


@annotated_param(pr.RDD)
class _RddParam(DataFrameParam):
    def to_input_data(self, df: DataFrame, ctx: Any) -> Any:
        assert isinstance(ctx, SparkExecutionEngine)
        return ctx.to_df(df).native.rdd

    def to_output_df(self, output: Any, schema: Any, ctx: Any) -> DataFrame:
        assert isinstance(output, pr.RDD)
        assert isinstance(ctx, SparkExecutionEngine)
        return ctx.to_df(output, schema=schema)

    def count(self, df: Any) -> int:  # pragma: no cover
        raise NotImplementedError("not allowed")

    def need_schema(self) -> Optional[bool]:
        return True


@run_at_def
def _register() -> None:
    """Register Spark Execution Engine

    .. note::

        This function is automatically called when you do

        >>> import fugue_spark
    """
    _register_engines()
