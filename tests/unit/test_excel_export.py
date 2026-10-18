"""出力Excelの列順（備考とファイル名の間に台帳2列）・値・色を守る。"""
import io

import openpyxl

from conftest import catalog_row, make_ledger_df
from model.compare import PREFIX_MARK, build_catalog_list, to_catalog_name_format
from model.excel_export import COLOR_DIFF, COLOR_ONLY_A, COLOR_SAME, SHEET_NAME, create_excel

EXPECTED_HEADER = ['指図番号', '改', '品目名称', '図面番号', 'SZ', '備考',
                   '図面台帳図番', '図面台帳品目名称', 'ファイル名', 'ページ']
TITLE = 'ELECTRICAL SCHEMATIC DIAGRAM'


def _open(df):
    return openpyxl.load_workbook(io.BytesIO(create_excel(df)))[SHEET_NAME]


def _bg(cell):
    return '#' + cell.fill.fgColor.rgb[-6:]


def _sheet():
    ledger = make_ledger_df([('EE1-1A', 'A', TITLE), ('EE2-2A', 'B', TITLE)])
    long_name = to_catalog_name_format('B', TITLE)
    rows = [catalog_row('EE1-1A', to_catalog_name_format('A', TITLE), '▼'),
            catalog_row('EE2-2A', 'ＸＸ', '▼'),
            catalog_row('EE5-5A', 'ＸＸ', '▼'),
            catalog_row('EE2-2A', 'ＸＸ', '')]
    return _open(build_catalog_list(rows, ledger)), long_name


def test_header_has_ledger_columns_between_note_and_filename_and_no_internal_columns():
    ws, _ = _sheet()
    assert [c.value for c in ws[1]] == EXPECTED_HEADER
    assert ws.freeze_panes == 'A2' and ws.auto_filter.ref


def test_values_y_and_ledger_name_only_where_they_differ():
    ws, long_name = _sheet()
    y = [ws.cell(r, 7).value for r in range(2, 6)]
    names = [ws.cell(r, 8).value for r in range(2, 6)]
    assert y == ['Y', 'Y', None, 'Y']
    assert names == [None, long_name, None, long_name]


def test_marked_rows_colored_by_status_and_unmarked_rows_plain():
    ws, _ = _sheet()
    assert _bg(ws.cell(2, 3)) == COLOR_SAME[0]      # both
    assert _bg(ws.cell(3, 3)) == COLOR_DIFF[0]      # name_diff
    assert _bg(ws.cell(4, 3)) == COLOR_ONLY_A[0]    # catalog_only
    assert ws.cell(5, 3).fill.fill_type is None     # ▼なし


def test_ledger_name_cell_color_overrides_row_color_even_for_unmarked_rows():
    ws, _ = _sheet()
    assert _bg(ws.cell(5, 8)) == COLOR_ONLY_A[0]


def test_prefix_ledger_name_cell_is_light_yellow():
    ledger = make_ledger_df([('EE1-1A', 'A' * 30, TITLE)])
    full = to_catalog_name_format('A' * 30, TITLE)
    ws = _open(build_catalog_list([catalog_row('EE1-1A', full[:44], '▼')], ledger))
    assert ws.cell(2, 8).value.startswith(PREFIX_MARK) and _bg(ws.cell(2, 8)) == COLOR_DIFF[0]
