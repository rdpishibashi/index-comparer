import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def make_ledger_df(rows):
    """rows: (Child, Subtitle, Title) → load_ledger() の戻りと同じ形のDataFrame。"""
    return pd.DataFrame([{'Child': c, 'Subtitle': s, 'Title': t} for c, s, t in rows])


def make_ledger_xlsx(sheets):
    """sheets: {シート名: DataFrame} → xlsx のバイト列。"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def catalog_row(number='', name='', mark='', filename='a_目録.pdf', page=1, order='ME26-9603-0', size='', note=''):
    return {'指図番号': order, '改': mark, '品目名称': name, '図面番号': number, 'SZ': size,
            '備考': note, 'ファイル名': filename, 'ページ': page}


@pytest.fixture
def make_ledger():
    return make_ledger_df
