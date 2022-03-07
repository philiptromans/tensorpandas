from __future__ import annotations
from typing import List

import numpy as np
import pandas.core.internals
from pandas._libs import lib
from pandas.core.dtypes.common import is_sparse
from pandas.core.dtypes.generic import ABCDataFrame
from pandas.core.dtypes.missing import isna
from pandas.core.internals.blocks import ABCIndex, ABCSeries, Block, extract_bool_array

# patch format
from pandas.io.formats import format


# # This fixes casting issues BlockManager.where()
def where(self, other, cond, errors="raise") -> List[Block]:

    cond = extract_bool_array(cond)
    assert not isinstance(other, (ABCIndex, ABCSeries, ABCDataFrame))

    if isinstance(other, np.ndarray) and other.ndim == 2:
        # TODO(EA2D): unnecessary with 2D EAs
        assert other.shape[1] == 1
        other = other[:, 0]

    if isinstance(cond, np.ndarray) and cond.ndim == 2:
        # TODO(EA2D): unnecessary with 2D EAs
        assert cond.shape[1] == 1
        cond = cond[:, 0]

    if lib.is_scalar(other) and isna(other):
        # The default `other` for Series / Frame is np.nan
        # we want to replace that with the correct NA value
        # for the type
        other = self.dtype.na_value

    if is_sparse(self.values):
        # TODO(SparseArray.__setitem__): remove this if condition
        # We need to re-infer the type of the data after doing the
        # where, for cases where the subtypes don't match
        dtype = None
    else:
        dtype = self.dtype

    result = self.values.copy()
    icond = ~cond
    if lib.is_scalar(other) or self.dtype.is_dtype("Tensor"):
        set_other = other
    else:
        set_other = other[icond]
    try:
        result[icond] = set_other
    except (NotImplementedError, TypeError):
        # NotImplementedError for class not implementing `__setitem__`
        # TypeError for SparseArray, which implements just to raise
        # a TypeError
        result = type(self.values)._from_sequence(np.where(cond, self.values, other), dtype=dtype)

    return [self.make_block_same_class(result)]


pandas.core.internals.blocks.ExtensionBlock.where = where


# formatting now goes through ExtensionArrayFormatter regardless of dtype (incl. datetimes)
def _format_strings(self) -> list[str]:
    values = format.extract_array(self.values, extract_numpy=True)

    formatter = self.formatter
    if formatter is None:
        # error: Item "ndarray" of "Union[Any, Union[ExtensionArray, ndarray]]" has
        # no attribute "_formatter"
        formatter = values._formatter(boxed=True)  # type: ignore[union-attr]

    if isinstance(values, format.Categorical):
        # Categorical is special for now, so that we can preserve tzinfo
        array = values._internal_get_values()
    elif values.dtype.is_dtype("Tensor"):
        # transform to 1D object array
        array = np.empty((len(values),), dtype=object)
        array[:] = list(values)
    else:
        array = np.asarray(values)

    fmt_values = format.format_array(
        array,
        formatter,
        float_format=self.float_format,
        na_rep=self.na_rep,
        digits=self.digits,
        space=self.space,
        justify=self.justify,
        decimal=self.decimal,
        leading_space=self.leading_space,
        quoting=self.quoting,
    )
    return fmt_values


format.ExtensionArrayFormatter._format_strings = _format_strings
