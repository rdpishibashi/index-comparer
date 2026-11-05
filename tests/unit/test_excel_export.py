"""出力Excelの列順（備考とファイル名の間に「整合性」「図面台帳品目名称」）・値・色を守る。"""
import io

import openpyxl

from conftest import catalog_row, make_ledger_df
from model.compare import build_catalog_list, to_catalog_name_format, to_halfwidth
from model.excel_export import COLOR_BLUE, COLOR_GREEN, COLOR_PINK, COLOR_YELLOW, SHEET_NAME, create_excel

EXPECTED_HEADER = ['指図番号', '区分', '改', '品目名称', '図面番号', 'SZ', '備考',
                   '整合性', '図面台帳品目名称', 'ファイル名', 'ページ']
TITLE = 'ELECTRICAL SCHEMATIC DIAGRAM'


def _bg(cell):
    return '#' + cell.fill.fgColor.rgb[-6:]


def _sheet():
    ledger = make_ledger_df([('EE1-1A', 'A', TITLE), ('EE2-2A', 'B', TITLE), ('EE9-9A', 'C', TITLE)])
    rows = [catalog_row('EE1-1A', to_catalog_name_format('A', TITLE), '▼', page=2),   # 完全一致
            catalog_row('EE2-2A', 'ＸＸ', '▼'),                                         # 品目名称不一致
            catalog_row('EE5-5A', 'ＸＸ', '▼'),                                         # 台帳なし
            catalog_row('EE2-2A', 'ＸＸ', '')]                                          # ▼なし
    df = build_catalog_list(rows, ledger, 'ME26-9603-0')                               # 末尾に台帳のみ(EE9-9A)
    return openpyxl.load_workbook(io.BytesIO(create_excel(df)))[SHEET_NAME]


def test_header_and_ledger_columns_sit_between_note_and_filename():
    ws = _sheet()
    assert [c.value for c in ws[1]] == EXPECTED_HEADER
    assert ws.freeze_panes == 'A2' and ws.auto_filter.ref


def test_integrity_values_and_ledger_name_per_row():
    ws = _sheet()
    assert [ws.cell(r, 8).value for r in range(2, 7)] == ['完全一致', '品目名称不一致', '台帳なし', '▼なし', '台帳のみ']
    assert ws.cell(2, 9).value is None
    assert ws.cell(3, 9).value == to_halfwidth(to_catalog_name_format('B', TITLE))   # 台帳側の名称は半角で出力
    assert ws.cell(6, 9).value == to_halfwidth(to_catalog_name_format('C', TITLE))
    assert ws.cell(2, 4).value == 'A_ELECTRICAL_SCHEMATIC_DIAGRAM'                     # 品目名称も半角


def test_ledger_only_row_has_blank_page_and_filename_and_a_numeric_page_elsewhere():
    ws = _sheet()
    assert ws.cell(2, 11).value == 2
    assert ws.cell(6, 5).value == 'EE9-9A' and ws.cell(6, 10).value is None and ws.cell(6, 11).value is None


def test_row_colors_follow_integrity_value():
    """完全一致=緑、品目名称不一致=黄、台帳なし=青、▼なし・台帳のみ=赤（薄い色。ユーザー指定）。"""
    ws = _sheet()
    assert [_bg(ws.cell(r, 3)) for r in range(2, 7)] == [
        COLOR_GREEN[0], COLOR_YELLOW[0], COLOR_BLUE[0], COLOR_PINK[0], COLOR_PINK[0]]


def test_rows_with_blank_integrity_have_no_color():
    ledger = make_ledger_df([('EE1-1A', 'A', TITLE)])
    df = build_catalog_list([catalog_row('', 'ボルト'), catalog_row('EE7-7A', 'ＸＸ')], ledger, 'ME26-9603-0')
    ws = openpyxl.load_workbook(io.BytesIO(create_excel(df)))[SHEET_NAME]
    assert ws.cell(2, 3).fill.fill_type is None and ws.cell(3, 3).fill.fill_type is None
