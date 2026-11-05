"""出図目録一覧のExcel出力（streamlit 非依存）。"""
import io

import pandas as pd

from model.compare import LEDGER_ONLY, LIST_COLUMNS, NAME_DIFF, NO_LEDGER, NO_MARK, OK

SHEET_NAME = '出図目録一覧'

# 淡色セット（HostPL-comparer と同じ4色。背景, 文字）
COLOR_PINK = ('#FEF1F5', '#9C0006')    # 薄い赤
COLOR_BLUE = ('#EAF1FB', '#1F4E79')    # 薄い青
COLOR_YELLOW = ('#FFF6D5', '#9C6500')  # 薄い黄
COLOR_GREEN = ('#EAF7EC', '#006100')   # 薄い緑

# 「整合性」の値 → 行の色（ユーザー指定）。空欄の行は色を付けない
INTEGRITY_COLORS = {OK: COLOR_GREEN, NAME_DIFF: COLOR_YELLOW, NO_LEDGER: COLOR_BLUE,
                    NO_MARK: COLOR_PINK, LEDGER_ONLY: COLOR_PINK}

COLUMN_WIDTHS = {'指図番号': 14, '区分': 6, '改': 5, '品目名称': 60, '図面番号': 18, 'SZ': 5, '備考': 50,
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
