"""出図目録PDFの読み取り（streamlit 非依存）。

pdfplumber の ``page.extract_tables()`` が返すページごとの表リストを
``parse_tables()`` で行データにする。表の列はヘッダ名で引く（位置固定にしない）。
"""
import io
from dataclasses import dataclass, field

ROW_COLUMNS = ['指図番号', '区分', '改', '品目名称', '図面番号', 'SZ', '備考', 'ファイル名', 'ページ']
_ITEM_COLUMNS = ('改', '品目名称', '図面番号', 'SZ', '備考')
_CATALOG_TITLE = '出図目録'
_REASON_HEADER = '改造理由'
NEW_KIND = '新規'
CHANGE_KIND = '変更'


@dataclass
class CatalogPdf:
    filename: str
    status: str  # 'ok' / 'skipped'（出図目録ではないPDF）/ 'error'
    order_no: str = ''
    rows: list = field(default_factory=list)
    message: str = ''


def _clean(value):
    # セル内の改行は列幅による折り返しなので、詰めて連結する
    return (value or '').replace('\n', '').strip()


def _find_header_table(tables):
    return next((t for t in tables if t and t[0] and t[0][0] == '指図番号'), None)


def _find_item_table(tables):
    return next((t for t in tables if t and t[0] and '品目名称' in t[0]), None)


def reason_kind(header):
    """ヘッダ表の「改造理由」欄の値の冒頭から区分（新規／変更）を返す。どちらでもなければ空文字。

    欄は見出し名で引く（見出し行の次の行の同じ列）。
    """
    for i, row in enumerate(header):
        if _REASON_HEADER in row and i + 1 < len(header):
            col = row.index(_REASON_HEADER)
            value = _clean(header[i + 1][col]) if col < len(header[i + 1]) else ''
            for kind in (NEW_KIND, CHANGE_KIND):
                if value.startswith(kind):
                    return kind
            return ''
    return ''


def is_catalog_tables(tables):
    return _find_header_table(tables) is not None and _find_item_table(tables) is not None


def parse_tables(tables_per_page, filename):
    """ページごとの表リスト → 行データ（dict）のリスト。

    指図番号は各ページのヘッダ表から取り、そのページの全行に付ける。
    全項目が空の行は捨てる。
    区分（新規／変更／空）はヘッダ表の「改造理由」欄からページ単位で取り、そのページの全行に付ける。
    """
    rows = []
    for page_no, tables in enumerate(tables_per_page, 1):
        header = _find_header_table(tables)
        item = _find_item_table(tables)
        if header is None or item is None:
            continue
        order_no = _clean(header[1][0]) if len(header) > 1 else ''
        kind = reason_kind(header)
        index = {name: item[0].index(name) for name in _ITEM_COLUMNS}
        for raw in item[1:]:
            record = {name: _clean(raw[i]) for name, i in index.items()}
            if not any(record.values()):
                continue
            rows.append({'指図番号': order_no, '区分': kind, **record, 'ファイル名': filename, 'ページ': page_no})
    return rows


def parse_catalog_pdf(file_bytes, filename):
    """PDFのバイト列を読む。1ページ目で出図目録かどうかを先に判定する。"""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                return CatalogPdf(filename, 'skipped', message='ページがありません')
            first_text = pdf.pages[0].extract_text() or ''
            first_tables = pdf.pages[0].extract_tables()
            if _CATALOG_TITLE not in first_text or not is_catalog_tables(first_tables):
                return CatalogPdf(filename, 'skipped', message='出図目録の形式ではありません')
            tables_per_page = [first_tables] + [p.extract_tables() for p in pdf.pages[1:]]
    except Exception as exc:  # 壊れたPDFは他ファイルの処理を止めずにエラーとして返す
        return CatalogPdf(filename, 'error', message=f'{type(exc).__name__}: {exc}')

    rows = parse_tables(tables_per_page, filename)
    order_no = rows[0]['指図番号'] if rows else ''
    return CatalogPdf(filename, 'ok', order_no=order_no, rows=rows)


def render_pdf_pages(file_bytes, resolution=110):
    """PDFの全ページを PIL 画像のリストにする（画面表示用）。"""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return [page.to_image(resolution=resolution).original for page in pdf.pages]
