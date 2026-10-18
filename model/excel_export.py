"""出図目録一覧のExcel出力（streamlit 非依存）。"""
import io

import pandas as pd

from model.compare import LEDGER_ONLY, LIST_COLUMNS, NAME_DIFF, NO_LEDGER, OK

SHEET_NAME = '出図目録一覧'

# 淡色4色セット（Tools/CLAUDE.md「Excel Output Pattern」。背景, 文字）
COLOR_ONLY_A = ('#FEF1F5', '#9C0006')   # 出図目録のみ（淡ピンク）
COLOR_ONLY_B = ('#EAF1FB', '#1F4E79')   # 図面台帳のみ（淡青）
COLOR_DIFF = ('#FFF6D5', '#9C6500')     # 両方にあるが名称が違う（淡黄）
COLOR_SAME = ('#EAF7EC', '#006100')     # 両方にあり一致（淡緑）

# 「整合性」の値 → 行の色。「▼なし」と空欄は色を付けない
INTEGRITY_COLORS = {OK: COLOR_SAME, NAME_DIFF: COLOR_DIFF, NO_LEDGER: COLOR_ONLY_A, LEDGER_ONLY: COLOR_ONLY_B}

COLUMN_WIDTHS = {'指図番号': 14, '改': 5, '品目名称': 60, '図面番号': 18, 'SZ': 5, '備考': 50,
                 '整合性': 14, '図面台帳品目名称': 60, 'ファイル名': 40, 'ページ': 6}


def create_excel(catalog_df):
    """`build_catalog_list()` の結果 → Excel のバイト列。"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        catalog_df[LIST_COLUMNS].to_excel(writer, sheet_name=SHEET_NAME, index=False)
        ws = writer.sheets[SHEET_NAME]

        header_fmt = wb.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1})
        for c, name in enumerate(LIST_COLUMNS):
            ws.write(0, c, name, header_fmt)
            ws.set_column(c, c, COLUMN_WIDTHS[name])

        def fmt(color=None):
            props = {'valign': 'top', 'text_wrap': True}
            if color:
                props.update(bg_color=color[0], font_color=color[1])
            return wb.add_format(props)

        plain = fmt()
        by_integrity = {k: fmt(v) for k, v in INTEGRITY_COLORS.items()}
        columns = list(catalog_df.columns)
        value_idx = [columns.index(name) for name in LIST_COLUMNS]
        integrity_idx = columns.index('整合性')
        for r, values in enumerate(catalog_df.itertuples(index=False), start=1):
            row_fmt = by_integrity.get(values[integrity_idx], plain)
            for c, vi in enumerate(value_idx):
                value = values[vi]
                ws.write(r, c, None if pd.isna(value) else value, row_fmt)

        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(catalog_df), len(LIST_COLUMNS) - 1)
    return output.getvalue()
