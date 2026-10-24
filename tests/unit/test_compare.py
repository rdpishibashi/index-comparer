"""品目名称の書式変換・一致判定と、「整合性」「図面台帳品目名称」・台帳のみ行の組み立てを守る。"""
import pytest

from conftest import catalog_row, make_ledger_df
from model.compare import (LEDGER_ONLY, NAME_DIFF, NO_LEDGER, NO_LEDGER_NAME, NO_MARK, OK,
                           TRUNCATION_MIN_CHARS, EMPTY_LABEL, build_catalog_list, filter_by_integrity, names_match, to_catalog_name_format)

TITLE = 'ELECTRICAL SCHEMATIC DIAGRAM'
SUB = 'DG MONITOR B1'
FULL = 'ＤＧ＿ＭＯＮＩＴＯＲ＿Ｂ１＿ＥＬＥＣＴＲＩＣＡＬ＿ＳＣＨＥＭＡＴＩＣ＿ＤＩＡＧＲＡＭ'
SHIBAN = 'ME26-9603-0'


def test_name_format_joins_subtitle_then_title_with_underscore_uppercase_fullwidth():
    assert to_catalog_name_format(SUB, TITLE) == FULL


@pytest.mark.parametrize('sub, title, expected', [
    ('Ａ  Ｂ', 'c', 'Ａ＿Ｂ＿Ｃ'),      # 全角空白・連続空白は1つの _、小文字は大文字化
    ('', TITLE, 'ＥＬＥＣＴＲＩＣＡＬ＿ＳＣＨＥＭＡＴＩＣ＿ＤＩＡＧＲＡＭ'),
    ('S', '', 'Ｓ'),
    ('', '', ''),
    ('I/F BOX', 'X', 'Ｉ／Ｆ＿ＢＯＸ＿Ｘ'),  # 記号も全角
])
def test_name_format_edge_cases(sub, title, expected):
    assert to_catalog_name_format(sub, title) == expected


def test_names_match_truncated_catalog_name_boundary_is_40_chars():
    """目録が39文字なら前方一致でも不一致、40文字なら一致扱い（目録側の途中切れ）。"""
    ledger = 'Ａ' * 50
    assert TRUNCATION_MIN_CHARS == 40
    assert not names_match('Ａ' * 39, ledger)
    assert names_match('Ａ' * 40, ledger)
    assert names_match(ledger, ledger)
    assert not names_match('Ｂ' * 40, ledger)


def test_names_match_empty_ledger_name_never_matches():
    assert not names_match('Ａ' * 45, '')
    assert not names_match('', '')


LEDGER = make_ledger_df([
    ('EE1-1A', SUB, TITLE),                      # 一致
    ('EE2-2A', 'MODULE B1 DIAGRAM LIST', TITLE),  # 目録が途中で切れている（一致扱い）
    ('EE3-3A', 'SENSOR LINE B1', 'ELECTRICAL SCHEMATICDIAGRAM'),  # 不一致
    ('EE4-4A', '', ''),                           # 台帳に名称なし
    ('EE9-9A', 'ONLY LEDGER', TITLE),             # 台帳のみ（目録に図番なし）
])
LONG = to_catalog_name_format('MODULE B1 DIAGRAM LIST', TITLE)
MISMATCH_NAME = to_catalog_name_format('SENSOR LINE B1', 'ELECTRICAL SCHEMATICDIAGRAM')


def _build(rows):
    return build_catalog_list(rows, LEDGER, SHIBAN)


def _rows(df):
    return df.set_index('図面番号', drop=False)


def test_marked_rows_integrity_and_ledger_name():
    """▼行: 一致／途中切れ=完全一致（台帳名称は空）、不一致・台帳に名称なし=品目名称不一致、台帳に図番なし=台帳なし▼。"""
    df = _rows(_build([
        catalog_row('EE1-1A', FULL, '▼'),
        catalog_row('EE2-2A', LONG[:44], '▼'),
        catalog_row('EE3-3A', 'ＸＸ', '▼'),
        catalog_row('EE4-4A', 'ＸＸ', '▼'),
        catalog_row('EE5-5A', 'ＸＸ', '▼'),
    ]))
    assert list(df['整合性'].iloc[:5]) == [OK, OK, NAME_DIFF, NAME_DIFF, NO_LEDGER]
    assert df.loc['EE1-1A', '図面台帳品目名称'] == ''
    assert df.loc['EE2-2A', '図面台帳品目名称'] == ''   # 途中切れは一致扱い＝台帳側は記載しない
    assert df.loc['EE3-3A', '図面台帳品目名称'] == MISMATCH_NAME
    assert df.loc['EE4-4A', '図面台帳品目名称'] == NO_LEDGER_NAME
    assert df.loc['EE5-5A', '図面台帳品目名称'] == ''


def test_unmarked_rows_are_no_mark_only_when_in_ledger_and_name_still_checked():
    """▼なしの行: 台帳にあれば「▼なし」（名称が違えば台帳側を記載）、台帳に無ければ空欄。"""
    df = _build([catalog_row('EE3-3A', 'ＸＸ'), catalog_row('EE1-1A', FULL), catalog_row('EE7-7A', 'ＸＸ')])
    assert list(df['整合性'].iloc[:3]) == [NO_MARK, NO_MARK, '']
    assert list(df['図面台帳品目名称'].iloc[:3]) == [MISMATCH_NAME, '', '']


def test_empty_drawing_number_never_matches_ledger():
    """購入部品（図面番号が空）は、台帳に空の Child があっても突き合わせず、整合性は空欄。"""
    ledger = make_ledger_df([('', 'S', 'T'), ('EE1-1A', 'S', 'T')])
    df = build_catalog_list([catalog_row('', 'ボルト', '▼')], ledger, SHIBAN)
    assert df.loc[0, '整合性'] == '' and df.loc[0, '図面台帳品目名称'] == ''


def test_ledger_only_rows_are_appended_with_ledger_name_and_shiban():
    """出図目録に図番が1行も無い台帳 Child は、末尾に「台帳のみ」の行として足す（▼なしで載っている図番は足さない）。"""
    df = _build([catalog_row('EE1-1A', FULL, '▼'), catalog_row('EE3-3A', 'ＸＸ')])
    only = df[df['整合性'] == LEDGER_ONLY]
    assert list(only['図面番号']) == ['EE2-2A', 'EE4-4A', 'EE9-9A']   # EE3-3A は目録にあるので含まれない
    assert df.index[-1] == only.index[-1] and (df.iloc[-3:]['整合性'] == LEDGER_ONLY).all()
    last = only.iloc[-1]
    assert last['指図番号'] == SHIBAN and last['品目名称'] == '' and last['ファイル名'] == ''
    assert last['図面台帳品目名称'] == to_catalog_name_format('ONLY LEDGER', TITLE)
    assert only.loc[only['図面番号'] == 'EE4-4A', '図面台帳品目名称'].iloc[0] == NO_LEDGER_NAME


def test_page_column_is_nullable_int_so_ledger_only_rows_do_not_mix_types():
    """台帳のみの行は「ページ」が空。int と空文字の混在列は st.dataframe の Arrow 変換で警告になるため Int64 にそろえる。"""
    df = _build([catalog_row('EE1-1A', FULL, '▼', page=3)])
    assert str(df['ページ'].dtype) == 'Int64'
    assert df['ページ'].iloc[0] == 3 and df['ページ'].iloc[-1] is not None and df['ページ'].isna().iloc[-1]


@pytest.mark.parametrize('selected, expected_numbers', [
    ([OK, NAME_DIFF, NO_LEDGER, NO_MARK, LEDGER_ONLY, EMPTY_LABEL], ['A', 'B', 'C', '', 'D']),  # 全選択は全行
    ([OK], ['A']),
    ([EMPTY_LABEL], ['']),            # 空欄の行は「（空欄）」で選ぶ
    ([LEDGER_ONLY], ['D']),           # ファイル名・ページが空の台帳のみ行も絞り込める
    ([OK, EMPTY_LABEL], ['A', '']),
    ([], []),                         # 空選択は0行
])
def test_filter_by_integrity_selects_rows_including_empty_value(selected, expected_numbers):
    """絞り込みは「整合性」の値（空欄は EMPTY_LABEL）で行を選び、元の並びを保つ。"""
    rows = [catalog_row('A', 'Ｘ', mark='▼'), catalog_row('B', 'Ｚ', mark='▼'),
            catalog_row('C', '', mark='▼'), catalog_row('', 'BUY')]
    ledger = make_ledger_df([('A', '', 'X'), ('B', '', 'Y'), ('D', '', 'W')])
    df = build_catalog_list(rows, ledger, SHIBAN)
    # A=完全一致, B=名称不一致, C=台帳なし▼, 購入部品=空欄, D=台帳のみ
    assert list(filter_by_integrity(df, selected)['図面番号']) == expected_numbers
