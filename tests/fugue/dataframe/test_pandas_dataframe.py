import json
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from pytest import raises
from triad.collections.schema import Schema

import fugue.api as fa
from fugue.dataframe import ArrowDataFrame, PandasDataFrame
from fugue.dataframe.array_dataframe import ArrayDataFrame
from fugue.dataframe.utils import _df_eq as df_eq
from fugue_test.dataframe_suite import DataFrameTests


class PandasDataFrameTests(DataFrameTests.Tests):
    def df(self, data: Any = None, schema: Any = None) -> PandasDataFrame:
        return PandasDataFrame(data, schema)

    def test_num_partitions(self):
        assert fa.get_num_partitions(self.df([[0, 1]], "a:int,b:int")) == 1

    def test_api_as_local(self):
        assert fa.is_local(self.df([[0, 1]], "a:int,b:int"))


class NativePandasDataFrameTests(DataFrameTests.NativeTests):
    def df(self, data: Any = None, schema: Any = None) -> pd.DataFrame:
        return ArrowDataFrame(data, schema).as_pandas()

    def to_native_df(self, pdf: pd.DataFrame) -> Any:  # pragma: no cover
        return pdf

    def test_num_partitions(self):
        assert fa.get_num_partitions(self.df([[0, 1]], "a:int,b:int")) == 1

    def test_map_type(self):
        pass


def test_init():
    df = PandasDataFrame(schema="a:str,b:int")
    assert df.is_bounded
    assert df.count() == 0
    assert df.schema == "a:str,b:int"
    assert Schema(df.native) == "a:str,b:int"

    pdf = pd.DataFrame([["a", 1], ["b", 2]])
    raises(Exception, lambda: PandasDataFrame(pdf))
    df = PandasDataFrame(pdf, "a:str,b:str")
    assert [["a", "1"], ["b", "2"]] == df.native.values.tolist()
    df = PandasDataFrame(pdf, "a:str,b:int")
    assert [["a", 1], ["b", 2]] == df.native.values.tolist()
    df = PandasDataFrame(pdf, "a:str,b:double")
    assert [["a", 1.0], ["b", 2.0]] == df.native.values.tolist()

    pdf = pd.DataFrame([["a", 1], ["b", 2]], columns=["a", "b"])["b"]
    assert isinstance(pdf, pd.Series)
    df = PandasDataFrame(pdf, "b:str")
    assert [["1"], ["2"]] == df.native.values.tolist()
    df = PandasDataFrame(pdf, "b:double")
    assert [[1.0], [2.0]] == df.native.values.tolist()

    pdf = pd.DataFrame([["a", 1], ["b", 2]], columns=["x", "y"])
    df = PandasDataFrame(pdf)
    assert df.schema == "x:str,y:long"
    df = PandasDataFrame(pdf, "y:str,x:str")
    assert [["1", "a"], ["2", "b"]] == df.native.values.tolist()
    ddf = PandasDataFrame(df)
    assert [["1", "a"], ["2", "b"]] == ddf.native.values.tolist()
    assert df.native is ddf.native  # no real copy happened

    df = PandasDataFrame([["a", 1], ["b", "2"]], "x:str,y:double")
    assert [["a", 1.0], ["b", 2.0]] == df.native.values.tolist()

    df = PandasDataFrame([], "x:str,y:double")
    assert [] == df.native.values.tolist()

    raises(Exception, lambda: PandasDataFrame(123))


def test_simple_methods():
    df = PandasDataFrame([], "a:str,b:int")
    assert df.as_pandas() is df.native
    assert df.empty
    assert 0 == df.count()
    assert df.is_local

    df = PandasDataFrame([["a", 1], ["b", "2"]], "x:str,y:double")
    assert df.as_pandas() is df.native
    assert not df.empty
    assert 2 == df.count()
    assert ["a", 1.0] == df.peek_array()
    assert dict(x="a", y=1.0) == df.peek_dict()


def test_nested():
    # data = [[dict(a=1, b=[3, 4], d=1.0)], [json.dumps(dict(b=[30, "40"]))]]
    # df = PandasDataFrame(data, "a:{a:str,b:[int]}")
    # a = df.as_array(type_safe=True)
    # assert [[dict(a="1", b=[3, 4])], [dict(a=None, b=[30, 40])]] == a

    data = [[[json.dumps(dict(b=[30, "40"]))]]]
    df = PandasDataFrame(data, "a:[{a:str,b:[int]}]")
    a = df.as_array(type_safe=True)
    assert [[[dict(a=None, b=[30, 40])]]] == a


def test_rename():
    df = PandasDataFrame([["a", 1]], "a:str,b:int")
    df2 = df.rename(columns=dict(a="aa"))
    assert isinstance(df, PandasDataFrame)
    df_eq(df2, [["a", 1]], "aa:str,b:int", throw=True)
    df_eq(df, [["a", 1]], "a:str,b:int", throw=True)


def test_as_array():
    df = PandasDataFrame([], "a:str,b:int")
    assert [] == df.as_array()
    assert [] == df.as_array(type_safe=True)
    assert [] == list(df.as_array_iterable())
    assert [] == list(df.as_array_iterable(type_safe=True))

    df = PandasDataFrame([["a", 1]], "a:str,b:int")
    assert [["a", 1]] == df.as_array()
    assert [["a", 1]] == df.as_array(["a", "b"])
    assert [[1, "a"]] == df.as_array(["b", "a"])

    # prevent pandas auto type casting
    df = PandasDataFrame([[1.0, 1.1]], "a:double,b:int")
    assert [[1.0, 1]] == df.as_array()
    assert isinstance(df.as_array()[0][0], float)
    assert isinstance(df.as_array()[0][1], int)
    assert [[1.0, 1]] == df.as_array(["a", "b"])
    assert [[1, 1.0]] == df.as_array(["b", "a"])

    df = PandasDataFrame([[np.float64(1.0), 1.1]], "a:double,b:int")
    assert [[1.0, 1]] == df.as_array()
    assert isinstance(df.as_array()[0][0], float)
    assert isinstance(df.as_array()[0][1], int)

    df = PandasDataFrame([[pd.Timestamp("2020-01-01"), 1.1]], "a:datetime,b:int")
    # df.native["a"] = pd.to_datetime(df.native["a"])
    assert [[datetime(2020, 1, 1), 1]] == df.as_array()
    assert isinstance(df.as_array()[0][0], datetime)
    # assert not isinstance(df.as_array()[0][0], pd.Timestamp)
    assert isinstance(df.as_array()[0][1], int)

    df = PandasDataFrame([[1.0, 1.1]], "a:double,b:int")
    assert [[1.0, 1]] == df.as_array(type_safe=True)
    assert isinstance(df.as_array()[0][0], float)
    assert isinstance(df.as_array()[0][1], int)


def test_as_dict_iterable():
    df = PandasDataFrame([[pd.NaT, 1.1]], "a:datetime,b:int")
    assert [dict(a=None, b=1)] == list(df.as_dict_iterable())
    df = PandasDataFrame([["2020-01-01", 1.1]], "a:datetime,b:int")
    assert [dict(a=datetime(2020, 1, 1), b=1)] == list(df.as_dict_iterable())


def test_nan_none():
    df = ArrayDataFrame([[None, None]], "b:str,c:double")
    assert df.as_pandas().iloc[0, 0] is None
    arr = PandasDataFrame(df.as_pandas(), df.schema).as_array()[0]
    assert arr[0] is None
    assert math.isnan(arr[1])

    df = ArrayDataFrame([[None, None]], "b:int,c:bool")
    arr = PandasDataFrame(df.as_pandas(), df.schema).as_array(type_safe=True)[0]
    assert arr[0] is None
    assert arr[1] is None

    df = ArrayDataFrame([["a", 1.1], [None, None]], "b:str,c:double")
    arr = PandasDataFrame(df.as_pandas(), df.schema).as_array(type_safe=True)[1]
    assert arr[0] is None
    assert arr[1] is None


def _test_as_array_perf():
    s = Schema()
    arr = []
    for i in range(100):
        s.append(f"a{i}:int")
        arr.append(i)
    for i in range(100):
        s.append(f"b{i}:int")
        arr.append(float(i))
    for i in range(100):
        s.append(f"c{i}:str")
        arr.append(str(i))
    data = []
    for i in range(5000):
        data.append(list(arr))
    df = PandasDataFrame(data, s)
    res = df.as_array()
    res = df.as_array(type_safe=True)
    nts, ts = 0.0, 0.0
    for i in range(10):
        t = datetime.now()
        res = df.as_array()
        nts += (datetime.now() - t).total_seconds()
        t = datetime.now()
        res = df.as_array(type_safe=True)
        ts += (datetime.now() - t).total_seconds()
    print(nts, ts)
