"""very simple visualizations
cases covered:
* single attribute, get distribution
* two attributes, bar, scatter, or line
"""
from typing import Optional, Dict
from pandas import DataFrame
from pandas.api.types import is_string_dtype, is_numeric_dtype, is_bool_dtype, is_datetime64_any_dtype

from .errors import type_check_with_warning, check_not_null, InternalLogicalError
from .vega_gen.bar_chart import gen_bar_chart_spec
from .vega_gen.scatter_plot import gen_scatterplot_spec
from .vega_gen.line_chart import gen_linechart_spec
from .vega_gen.data_processing import get_categorical_distribution, \
    get_numeric_distribution, set_data_attr
from .vega_gen.defaults import COUNT_COL_NAME

from .types import ChartInfo, ChartType, Channel, DfTransform

def gen_spec(df: DataFrame) -> Optional[ChartInfo]:
    """Implements basic show me like feature
        if there is only one column, try to do a distribution with reasonable binning
        if one categorical, one numeric, barchart
        if two numeric, scatter, unless if one is time, then line (line, todo)

    TODO:
    [ ] if the numeric value has a limited number of unique values, treat as bar chart!
    [ ] also add line chart
    """
    type_check_with_warning(df, DataFrame)
    # error if df has no column
    df_len = len(df.columns)
    df_to_visualize: DataFrame = None
    chart_type: Optional[ChartType] = None
    encoding: Optional[Dict[Channel, str]] = None
    additional_transforms: Optional[DfTransform] = None
    if (df_len == 0):
        raise Exception("DataFrame has too few columns")
    elif (df_len == 1):
        first_col = df.columns.values[0]
        if (is_string_dtype(df[first_col])):
            additional_transforms = DfTransform.categorical_distribution
            df_to_visualize = get_categorical_distribution(df[first_col], first_col)
            chart_type = ChartType.bar_categorical
        elif (is_datetime64_any_dtype(df[first_col])):
            additional_transforms = DfTransform.categorical_distribution
            df_to_visualize = get_categorical_distribution(df[first_col], first_col)
            chart_type = ChartType.line
        else:
            additional_transforms = DfTransform.numeric_distribution
            df_to_visualize = get_numeric_distribution(df[first_col], first_col)
            chart_type = ChartType.bar_linear
        encoding = {
            Channel.x: first_col,
            Channel.y: COUNT_COL_NAME
        }
    else:
        first_col = df.columns.values[0]
        # fow now let's just take the frist two columns
        second_col = df.columns.values[1]
        df_to_visualize = df[[first_col, second_col]]
        if (is_string_dtype(df[first_col]) & is_numeric_dtype(df[second_col])):
            chart_type = ChartType.bar_categorical
            encoding = {
                Channel.x: first_col,
                Channel.y: second_col
            }
        elif (is_numeric_dtype(df[first_col]) & is_string_dtype(df[second_col])):
            chart_type = ChartType.bar_categorical
            encoding = {
                Channel.x: second_col,
                Channel.y: first_col
            }
        elif (is_numeric_dtype(df[first_col]) & is_numeric_dtype(df[second_col])):
            chart_type = ChartType.scatter
            encoding = {
                Channel.x: first_col,
                Channel.y: second_col
            }
            
    if chart_type:
        if encoding:
            if df_to_visualize is not None:
                return _gen_spec_helper(chart_type, encoding, df_to_visualize, additional_transforms)
    raise InternalLogicalError(f"Failed to generate spec:\nchart_type {chart_type}\nencoding: {encoding}\ndf_to_visualize:{df_to_visualize}")


def _gen_spec_helper(chart_type: ChartType, encoding: Dict[Channel, str], data: DataFrame, additional_transforms: Optional[DfTransform]) -> ChartInfo:
    if (chart_type == ChartType.bar_linear) or (chart_type == ChartType.bar_categorical):
        vega_spec = gen_bar_chart_spec(encoding[Channel.x], encoding[Channel.y], data)
    elif (chart_type == ChartType.scatter):
        vega_spec = gen_scatterplot_spec(encoding[Channel.x], encoding[Channel.y], data)
    else:
        vega_spec = gen_linechart_spec(encoding[Channel.x], encoding[Channel.y], data)

    return ChartInfo(chart_type, encoding, vega_spec, additional_transforms)
