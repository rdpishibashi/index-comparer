"""図面管理台帳（DXF-diff-manager 出力）の読み込み（streamlit 非依存）。"""
import io
import re

import pandas as pd

# DXF-diff-manager model/master_ledger.py の MASTER_FILENAME_PATTERN と同じ式（コピー。共有ファイルではない）
LEDGER_FILENAME_PATTERN = re.compile(
    r'^(?P<shiban>[A-Z]{2}\d{2}-\d{4}-\d)_(?P<module>[A-Z0-9]{4}|na)_(?P<side>[A-Z0-9]{3}|na)(?:[_-].*)?\.xlsx$'
)


def parse_ledger_filename(filename):
    """台帳ファイル名から (指番, モジュール, サイド) を返す。一致しなければ (None, None, None)。"""
    match = LEDGER_FILENAME_PATTERN.match(filename or '')
    if not match:
        return None, None, None
    return match['shiban'], match['module'], match['side']


def _text(series):
    # NaN を astype(str) すると文字列 "nan" になり欠損判定が効かなくなるため、notna() マスク後に変換する
    return series.where(series.notna(), '').astype(object).map(lambda v: str(v).strip() if v != '' else '')


def load_ledger(file_bytes):
    """台帳Excel → (DataFrame[Child, Title, Subtitle], エラー文字列)。

    シート名には依存せず、Child 列を持つシートを探す。
    同じ Child が複数行ある場合は、Title/Subtitle のどちらかが空でない最初の行を採用する。
    """
    try:
        sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, dtype=object)
    except Exception as exc:
        return None, f'台帳を読み込めません: {type(exc).__name__}: {exc}'

    source = next((df for df in sheets.values() if 'Child' in df.columns), None)
    if source is None:
        return None, '台帳に Child 列を持つシートがありません（DXF-diff-manager の図面管理台帳を指定してください）'

    ledger = pd.DataFrame({
        'Child': _text(source['Child']),
        'Title': _text(source['Title']) if 'Title' in source.columns else '',
        'Subtitle': _text(source['Subtitle']) if 'Subtitle' in source.columns else '',
    })
    ledger = ledger[ledger['Child'] != ''].copy()
    ledger['_has_name'] = (ledger['Title'] != '') | (ledger['Subtitle'] != '')
    # 名前のある行を先頭に寄せてから Child ごとに先頭を採用する（元の並びは保つ）
    ledger = (ledger.sort_values('_has_name', ascending=False, kind='stable')
                    .drop_duplicates('Child', keep='first')
                    .drop(columns='_has_name'))
    return ledger.reset_index(drop=True), None
