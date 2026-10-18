"""出力Excelの列順（備考とファイル名の間に「整合性」「図面台帳品目名称」）・値・色を守る。"""
import io

import openpyxl

from conftest import catalog_row, make_ledger_df
from model.compare import build_catalog_list, to_catalog_name_format
from model.excel_export import COLOR_DIFF, COLOR_ONLY_A, COLOR_ONLY_B, COLOR_SAME, SHEET_NAME, create_excel

EXPECTED_HEADER = ['指図番号', '改', '品目名称', '図面番号', 'SZ', '備考',
                   '整合性', '図面台帳品目名称', 'ファイル名', 'ページ']
TITLE = 'ELECTRICAL SCHEMATIC DIAGRAM'


def _bg(cell):
    return '#' + cell.fill.fgColor.rgb[-6:]


def _sheet():
    ledger = make_ledger_df([('EE1-1A', 'A', TITLE), ('EE2-2A', 'B', TITLE), ('EE9-9A', 'C', TITLE)])
    rows = [catalog_row('EE1-1A', to_catalog_name_format('A', TITLE), '▼', page=2),   # 完全一致
            catalog_row('EE2-2A', 'ＸＸ', '▼'),                                         # 品目名称不一致
            catalog_row('EE5-5A', 'ＸＸ', '▼'),                                         # 台帳なし▼
            catalog_row('EE2-2A', 'ＸＸ', '')]                                          # ▼なし
    df = build_catalog_list(rows, ledger, 'ME26-9603-0')                               # 末尾に台帳のみ(EE9-9A)
    return openpyxl.load_workbook(io.BytesIO(create_excel(df)))[SHEET_NAME]


def test_header_and_ledger_columns_sit_between_note_and_filename():
    ws = _sheet()
    assert [c.value for c in ws[1]] == EXPECTED_HEADER
    assert ws.freeze_panes == 'A2' and ws.auto_filter.ref


def test_integrity_values_and_ledger_name_per_row():
    ws = _sheet()
    assert [ws.cell(r, 7).value for r in range(2, 7)] == ['完全一致', '品目名称不一致', '台帳なし▼', '▼なし', '台帳のみ']
    assert ws.cell(2, 8).value is None
    assert ws.cell(3, 8).value == to_catalog_name_format('B', TITLE)
    assert ws.cell(6, 8).value == to_catalog_name_format('C', TITLE)


def test_ledger_only_row_has_blank_page_and_filename_and_a_numeric_page_elsewhere():
    ws = _sheet()
    assert ws.cell(2, 10).value == 2
    assert ws.cell(6, 4).value == 'EE9-9A' and ws.cell(6, 9).value is None and ws.cell(6, 10).value is None


def test_row_colors_follow_integrity_and_no_mark_rows_are_plain():
    ws = _sheet()
    assert [_bg(ws.cell(r, 3)) for r in (2, 3, 4)] == [COLOR_SAME[0], COLOR_DIFF[0], COLOR_ONLY_A[0]]
    assert ws.cell(5, 3).fill.fill_type is None
    assert _bg(ws.cell(6, 3)) == COLOR_ONLY_B[0]
