import json
from pandas import DataFrame
from numbers import Number
import logging
import re
import logging
from typing import (
    List,
    Dict,
    Optional,
)
from datetime import datetime, timedelta

ISO_8601_FORMAT: str = '%Y-%m-%dT%H:%M:%S'

def calc_col_lengths(df: DataFrame) -> Dict[str, int]:
    """
    Get largest length of values for each column in given DataFrame.

    :param df: DataFrame,
        Pandas DataFrame.
    :return: dict,
        Mapping of column names to length values
    """
    if df.empty:
        return dict()

    df_cols = list(df.columns)
    col_lengths_map = dict()

    def _to_literal(
        val: str,  # val is already stringify-ed and nulls ignored
    ) -> str:
        """
        Convert value to literal value using repr.

        :param val: str,
        :return: str,
            Literal value.
        """
        ans = repr(val)
        ans = ans[1:-1].encode('utf-8')
        return ans

    for col in df_cols:
        max_length = (
            df[~df[col].isnull()][col]
            .astype('str')
            .apply(_to_literal)
            .str.len()
            .max()
        )

        # Buffer Percentage of 1 for max size
        buffer_percentage = 0.01

        if isinstance(max_length, Number):
            try:
                col_lengths_map[col] = int(
                    max_length + max_length * buffer_percentage
                )
            except ValueError:
                col_lengths_map[col] = 0

    return col_lengths_map

def load_json(file_path):
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f]

def pd_preview(
    df: DataFrame,
    cols: Optional[List[str]] = None,
    num_rows: Optional[int] = 1,
    columns_only: bool = False,
    tag: Optional[str] = None,
    calculate_lengths: bool = False,
):
    """
    Prints values and other useful information from a DataFrame.

    :param df: DataFrame,
        Pandas DataFrame.
    :param cols: Optional[List[str]],
        Column names to be previewed, default option will include all cols.
    :param num_rows: Optional[int], default = 1,
        Number of rows to preview.  Use None to preview all data.
    :param columns_only: bool, default: False,
        If True, will only print column names, not values. This is useful for
        creating SQL, etc.
    :param tag: Optional[str],
        Message to include with preview (helps identify placement of preview)
    :param calculate_lengths: bool, default=False,
        Flag to control whether to include column lengths for string columns.
    :return: DataFrame,
        Original input DataFrame.
    """
    if cols is None:
        cols = list(df.columns)

    df_cols = list(df.columns)
    df_types = list(df.dtypes)

    if tag:
        print_lines = [f'\n----- DATAFRAME PREVIEW (tag: {tag}) -----']
    else:
        print_lines = ['\n----- DATAFRAME PREVIEW -----']

    print_lines.append(f'DF shape: {df.shape}')
    if df.index.name:
        print_lines.append(f'Index name: {df.index.name}')
    else:
        print_lines.append('No index name defined')

    col_lengths_map = {}
    if calculate_lengths:
        df_copy = df.copy()
        if num_rows is not None:
            df_copy = df.head(num_rows)

        col_lengths_map = calc_col_lengths(df_copy)

    for idx, _row in df.head(num_rows).iterrows():
        print_lines.append(f'Row: {idx}')

        col_counter = 0
        for col, dtype in zip(df_cols, df_types):
            col_counter += 1
            if col not in cols:
                continue

            try:
                val = df.at[idx, col]
            except ValueError as exc:
                msg = f'Could not get value at ({idx}, {col}).'
                if not df.index.is_unique:
                    msg += (
                        ' Index is not unique; you may need to specify a '
                        'different index column(s) or set index_col=False when '
                        'creating the DataFrame.'
                    )
                if not df.columns.is_unique:
                    msg += (
                        f' Column names are not unique; you may need to rename '
                        f'duplicate columns or specify fixed column names when '
                        f'creating the DataFrame: {sorted(df.columns)}.'
                    )
                raise ValueError(msg) from exc

            if columns_only:
                print_lines.append(f"    '{col}',")
            else:
                if calculate_lengths:
                    print_lines.append(
                        f"    {col_counter}. '{col}' ({dtype}: "
                        f"{col_lengths_map.get(col, 0)}): {repr(val)}"
                    )
                else:
                    print_lines.append(
                        f"    {col_counter}. '{col}' ({dtype}): {repr(val)}"
                    )

    logging.info('\n'.join(print_lines))

    return df

def pd_cols_remove_special_characters(
    df: DataFrame,
    cols: Optional[List[str]] = None,
    remove_characters: Optional[str] = '#@&$%^()-/\\\\',
    replace_char: str = '_',
) -> DataFrame:
    """
    Remove special characters in columns for given DataFrame

    :param df: DataFrame,
        Pandas DataFrame.
    :param cols: Optional[List[str]],
        Column names to replace spaces in the input DataFrame.
    :param remove_characters: Optional[str],
        String of special characters to replace in the column names of the
        input DataFrame.
    :param replace_char: str, default='_',
        Replacement character.
    :return: DataFrame
        DataFrame with spaces in columns replaced.
    """
    if not list(df.columns):
        logging.warning(
            'Empty dataframe, skipping [pd_cols_remove_special_characters]'
        )
        return df

    logging.info('Removing special characters in DataFrame columns')

    if not cols:
        df_cols = list(df.columns)
        cols = df_cols

    rename_map = {}
    for col in cols:
        pattern = f"[{remove_characters}]"
        new_col = re.sub(pattern, replace_char, col)
        rename_map[col] = new_col

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    return df

def pd_rename_cols(
    df: DataFrame,
    rename_map: dict,
    override: bool = False,
    ignore_missing: bool = False,
) -> DataFrame:
    """
    Rename but also check that the keys exist in the dataframe.  Can optionally
    override if new columns already exist.

    :param df: DataFrame,
        Pandas DataFrame.
    :param rename_map: dict,
        Dictionary mapping column names to new column names.
    :param override: bool, default=False,
        Flag to control whether to override any existing columns that have
        column names matching the new column names.
    :param ignore_missing: bool, default=False,
        Flag to control whether to ignore columns from rename_map not in the df,
        or raise an Exception.
    :return: DataFrame,
        DataFrame with renamed columns.
    """
    if not list(df.columns):
        logging.warning('Empty dataframe, skipping [pd_rename_cols]')
        return df

    df_cols = set(df.columns)

    if override:
        for out_col in rename_map.values():
            if out_col in df_cols:
                del df[out_col]
    else:
        for out_col in rename_map.values():
            if out_col in df_cols:
                logging.warning(
                    f'Out column already exists [{out_col}], rename will '
                    'create dupe'
                )

    missing_keys = [k for k in rename_map if k not in df_cols]
    if missing_keys:
        if ignore_missing:
            for key in missing_keys:
                del rename_map[key]
        else:
            raise Exception(f"Missing keys: {missing_keys}, cannot rename")

    df.rename(columns=rename_map, inplace=True)
    return df

def convert_epoch_to_datetime(epoch: float, format=ISO_8601_FORMAT) -> str:
    """
    Converts epoch date to UTC datetime string value.
    :param epoch: float,
        Epoch value.
    :param format: str,
        Output datetime format.
    :return:
    """

    if not epoch:
        return
    epoch = float(epoch) / 1000
    # Convert milliseconds to seconds
    datetime_converted = datetime(1970, 1, 1) + timedelta(seconds=epoch)
    return datetime_converted.strftime(format)