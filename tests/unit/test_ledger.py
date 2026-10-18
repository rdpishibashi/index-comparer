"""台帳ファイル名の指番抽出と、台帳Excelの読み込み（シート名非依存・欠損・重複Child）を守る。"""
import pandas as pd
import pytest

from model.ledger import load_ledger, parse_ledger_filename
from conftest import make_ledger_xlsx


@pytest.mark.parametrize('name, expected', [
    ('ME26-9603-0_na_405.xlsx', ('ME26-9603-0', 'na', '405')),
    ('ME26-9603-0_ZMB1_405.xlsx', ('ME26-9603-0', 'ZMB1', '405')),
    ('ME26-9603-0_na_405_2.xlsx', ('ME26-9603-0', 'na', '405')),
    ('ME26-9603-0_na_405-v2.xlsx', ('ME26-9603-0', 'na', '405')),
    ('ledger.xlsx', (None, None, None)),
    ('ME26-9603-0.xlsx', (None, None, None)),
    ('', (None, None, None)),
])
def test_parse_ledger_filename(name, expected):
    assert parse_ledger_filename(name) == expected


def test_load_ledger_finds_child_sheet_regardless_of_sheet_name():
    """シート名（Master／旧 Diff List 等）に依存せず Child 列を持つシートを使う。"""
    data = make_ledger_xlsx({
        'Summary': pd.DataFrame({'エンティティ統計': ['a']}),
        'RenamedSheet': pd.DataFrame({'Child': ['EE1-1'], 'Title': ['T'], 'Subtitle': ['S']}),
    })
    df, error = load_ledger(data)
    assert error is None and df.to_dict('records') == [{'Child': 'EE1-1', 'Title': 'T', 'Subtitle': 'S'}]


def test_load_ledger_error_when_no_child_column():
    df, error = load_ledger(make_ledger_xlsx({'Sheet1': pd.DataFrame({'x': [1]})}))
    assert df is None and 'Child' in error


def test_load_ledger_error_for_non_excel_bytes():
    df, error = load_ledger(b'garbage')
    assert df is None and error


def test_load_ledger_missing_title_values_become_empty_not_nan_string():
    """NaN を astype(str) すると 'nan' になる。欠損は空文字にする。"""
    data = make_ledger_xlsx({'Master': pd.DataFrame({'Child': ['EE1-1'], 'Title': [None], 'Subtitle': ['S']})})
    df, _ = load_ledger(data)
    assert df.loc[0, 'Title'] == '' and df.loc[0, 'Subtitle'] == 'S'


def test_load_ledger_works_without_title_and_subtitle_columns():
    df, error = load_ledger(make_ledger_xlsx({'Master': pd.DataFrame({'Child': ['EE1-1']})}))
    assert error is None and df.loc[0, 'Title'] == '' and df.loc[0, 'Subtitle'] == ''


def test_load_ledger_duplicate_child_uses_first_row_that_has_a_name():
    """同じ Child が複数行（RevUp と流用など）あるとき、名前のある最初の行を採用する。"""
    data = make_ledger_xlsx({'Master': pd.DataFrame({
        'Child': ['EE1-1', 'EE1-1', 'EE2-2'], 'Title': [None, 'T1', 'T2'], 'Subtitle': [None, 'S1', 'S2']})})
    df, _ = load_ledger(data)
    assert df.set_index('Child').loc['EE1-1', 'Title'] == 'T1' and len(df) == 2


def test_load_ledger_drops_rows_with_empty_child():
    df, _ = load_ledger(make_ledger_xlsx({'Master': pd.DataFrame({'Child': ['EE1-1', None], 'Title': ['a', 'b']})}))
    assert list(df['Child']) == ['EE1-1']
