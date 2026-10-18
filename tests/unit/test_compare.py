"""品目名称の書式変換・判定と、目録一覧／図番比較の組み立てを守る。"""
import pytest

from conftest import catalog_row, make_ledger_df
from model.compare import (NO_LEDGER_NAME, PREFIX_MARK, TRUNCATION_MIN_CHARS, build_catalog_list,
                           build_drawing_comparison, judge_name, to_catalog_name_format)

TITLE = 'ELECTRICAL SCHEMATIC DIAGRAM'
SUB = 'DG MONITOR B1'
FULL = 'ＤＧ＿ＭＯＮＩＴＯＲ＿Ｂ１＿ＥＬＥＣＴＲＩＣＡＬ＿ＳＣＨＥＭＡＴＩＣ＿ＤＩＡＧＲＡＭ'


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


def test_judge_name_prefix_boundary_is_40_chars():
    """目録が39文字なら前方一致でも不一致、40文字なら前方一致（目録側の途中切れ）。"""
    ledger = 'Ａ' * 50
    assert TRUNCATION_MIN_CHARS == 40
    assert judge_name('Ａ' * 39, ledger) == 'mismatch'
    assert judge_name('Ａ' * 40, ledger) == 'prefix'
    assert judge_name(ledger, ledger) == 'match'
    assert judge_name('Ｂ' * 40, ledger) == 'mismatch'


def test_judge_name_empty_ledger_name_is_mismatch():
    assert judge_name('Ａ' * 45, '') == 'mismatch'
    assert judge_name('', '') == 'mismatch'


LEDGER = make_ledger_df([
    ('EE1-1A', SUB, TITLE),                      # 一致
    ('EE2-2A', 'MODULE B1 DIAGRAM LIST', TITLE),  # 前方一致（下で目録を切る）
    ('EE3-3A', 'SENSOR LINE B1', 'ELECTRICAL SCHEMATICDIAGRAM'),  # 不一致
    ('EE4-4A', '', ''),                           # 台帳に名称なし
    ('EE9-9A', 'ONLY LEDGER', TITLE),             # 台帳のみ
])
LONG = to_catalog_name_format('MODULE B1 DIAGRAM LIST', TITLE)


def _build(rows):
    return build_catalog_list(rows, LEDGER).set_index('図面番号', drop=False)


def test_catalog_list_marked_rows_status_and_columns():
    """▼行: 一致=both・前方一致=both＋目印・不一致=name_diff・台帳に無い=catalog_only。"""
    df = _build([
        catalog_row('EE1-1A', FULL, '▼'),
        catalog_row('EE2-2A', LONG[:44], '▼'),
        catalog_row('EE3-3A', 'ＳＥＮＳＯＲ＿ＬＩＮＥ＿Ｂ１＿ＥＬＥＣＴＲＩＣＡＬ＿ＳＣＨＥＭＡＴＩＣ＿ＤＩＡＧＲＡＭ', '▼'),
        catalog_row('EE4-4A', 'ＸＸ', '▼'),
        catalog_row('EE5-5A', 'ＸＸ', '▼'),
    ])
    assert list(df['図面台帳図番']) == ['Y', 'Y', 'Y', 'Y', '']
    assert list(df['_status']) == ['both', 'both', 'name_diff', 'name_diff', 'catalog_only']
    assert df.loc['EE1-1A', '図面台帳品目名称'] == ''
    assert df.loc['EE2-2A', '図面台帳品目名称'] == PREFIX_MARK + LONG
    assert df.loc['EE3-3A', '図面台帳品目名称'] == to_catalog_name_format('SENSOR LINE B1', 'ELECTRICAL SCHEMATICDIAGRAM')
    assert df.loc['EE4-4A', '図面台帳品目名称'] == NO_LEDGER_NAME
    assert df.loc['EE5-5A', '図面台帳品目名称'] == ''


def test_catalog_list_unmarked_rows_get_y_and_name_but_no_status():
    """▼なしの行も Y／名称の判定は行うが、行の色分け用 _status は付けない。"""
    df = build_catalog_list([catalog_row('EE3-3A', 'ＸＸ'), catalog_row('EE1-1A', FULL)], LEDGER)
    assert list(df['図面台帳図番']) == ['Y', 'Y']
    assert list(df['_status']) == ['', '']
    assert df.loc[0, '図面台帳品目名称'] != '' and df.loc[1, '図面台帳品目名称'] == ''


def test_catalog_list_empty_drawing_number_never_matches_ledger():
    """購入部品（図面番号が空）は、台帳に空の Child があっても一致扱いにしない。"""
    ledger = make_ledger_df([('', 'S', 'T'), ('EE1-1A', 'S', 'T')])
    df = build_catalog_list([catalog_row('', 'ボルト')], ledger)
    assert df.loc[0, '図面台帳図番'] == '' and df.loc[0, '図面台帳品目名称'] == ''


def test_drawing_comparison_union_states_and_files():
    """▼図番と台帳Childの和集合を1図番1行に。複数ファイルは連結、▼なし記載も区別する。"""
    cat = build_catalog_list([
        catalog_row('EE1-1A', FULL, '▼', filename='a.pdf'),
        catalog_row('EE1-1A', FULL, '▼', filename='b.pdf'),
        catalog_row('EE5-5A', 'ＸＸ', '▼', filename='a.pdf'),
        catalog_row('EE3-3A', 'ＸＸ', '', filename='c.pdf'),
    ], LEDGER)
    comp = build_drawing_comparison(cat, LEDGER).set_index('図面番号')
    assert comp.loc['EE1-1A', '状態'] == '両方' and comp.loc['EE1-1A', '品目名称判定'] == '一致'
    assert comp.loc['EE1-1A', '出図目録ファイル'] == 'a.pdf, b.pdf'
    assert comp.loc['EE5-5A', '状態'] == '出図目録のみ' and comp.loc['EE5-5A', '品目名称判定'] == '—'
    assert comp.loc['EE3-3A', '状態'] == '図面台帳のみ' and comp.loc['EE3-3A', '出図目録での記載'] == '▼なしで記載'
    assert comp.loc['EE9-9A', '出図目録での記載'] == '記載なし'
    assert list(comp['状態']) == sorted(comp['状態'], key=['両方', '出図目録のみ', '図面台帳のみ'].index)
    assert comp.index.is_unique


def test_drawing_comparison_with_no_marked_rows_lists_all_ledger_children():
    cat = build_catalog_list([catalog_row('', 'ボルト')], LEDGER)
    comp = build_drawing_comparison(cat, LEDGER)
    assert set(comp['状態']) == {'図面台帳のみ'} and len(comp) == len(LEDGER)
