"""出図目録PDFの表 → 行データ変換と、PDFの判定（出図目録か／壊れていないか）を守る。"""
import pytest

from model.catalog_pdf import ROW_COLUMNS, is_catalog_tables, parse_catalog_pdf, parse_tables, reason_kind, render_pdf_pages

HEADER = [['指図番号', None, 'ｻｲﾄﾞ', '図面番号'], ['ME26-9603-0', None, '405', 'EE7319-421-09A']]
ITEM_HEAD = ['', '改', '符号', '品目名称', '図面番号', 'SZ', 'ﾒｰｶ名', '備考']


def item_table(*rows):
    return [ITEM_HEAD, *rows]


def test_parse_tables_extracts_columns_by_header_name_and_joins_wrapped_lines():
    """セル内改行（列幅による折り返し）は除去して連結し、列はヘッダ名で引く。"""
    table = item_table(['', '▼', '*', 'ＭＯＤＵＬＥ＿Ｂ１\n＿ＤＩＡＧＲＡＭ', 'EE7319-421-09A', 'A3', '', '変更|EE6763\n変更。'])
    rows = parse_tables([[HEADER, table]], 'x.pdf')
    assert list(rows[0]) == ROW_COLUMNS
    assert rows[0] == {'指図番号': 'ME26-9603-0', '区分': '', '改': '▼', '品目名称': 'ＭＯＤＵＬＥ＿Ｂ１＿ＤＩＡＧＲＡＭ',
                       '図面番号': 'EE7319-421-09A', 'SZ': 'A3', '備考': '変更|EE6763変更。',
                       'ファイル名': 'x.pdf', 'ページ': 1}


def test_parse_tables_keeps_purchased_parts_with_empty_drawing_number_and_drops_blank_rows():
    """購入部品（図面番号・SZ が空）は残し、全項目が空の行だけ捨てる。ページ番号は1始まり。"""
    t1 = item_table(['', '', 'CABLE', 'フッ素樹脂チュ−ブ', '', '', 'ニッタ', ''], ['', '', '', '', '', '', '', ''])
    t2 = item_table(['', '', '006', 'ＵＮＩＴ', 'EE5443-006-01B', 'A3', '', ''])
    rows = parse_tables([[HEADER, t1], [HEADER, t2]], 'x.pdf')
    assert [(r['図面番号'], r['ページ']) for r in rows] == [('', 1), ('EE5443-006-01B', 2)]


def test_parse_tables_ignores_pages_without_catalog_tables():
    assert parse_tables([[[['出図ID', 'X']]]], 'x.pdf') == []


def test_is_catalog_tables_requires_both_header_and_item_tables():
    assert is_catalog_tables([HEADER, item_table()])
    assert not is_catalog_tables([HEADER])
    assert not is_catalog_tables([])


def test_parse_catalog_pdf_returns_error_for_broken_bytes_without_raising():
    """壊れたPDFは例外にせず error として返す（他のPDFの処理を止めない）。"""
    result = parse_catalog_pdf(b'not a pdf', 'broken.pdf')
    assert result.status == 'error' and result.filename == 'broken.pdf' and result.rows == []


def test_render_pdf_pages_returns_one_image_per_page():
    """画面表示用に、PDFの全ページを1ページ1枚の画像にする。"""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    pdf.new_page(200, 100)
    pdf.new_page(200, 100)
    import io
    buf = io.BytesIO()
    pdf.save(buf)
    images = render_pdf_pages(buf.getvalue(), width=300)
    assert len(images) == 2 and all(im.size[0] == 300 for im in images)   # 横幅は指定どおり


def _header_with_reason(value):
    # 実PDFのヘッダ表の形（見出し行の次の行の同じ列に値が入る）
    return [*HEADER, ['ﾓｼﾞｭｰﾙ', '承認依頼者', None, '改造理由', None, '発注数'], ['ZMB1', '', None, value, None, '1']]


@pytest.mark.parametrize('value, expected', [
    ('新規', '新規'),
    ('変更|DCDCBD型式変更、D40ZをD40Aに変更。', '変更'),
    ('新規|追加\n図面', '新規'),
    ('', ''),
    ('その他', ''),
    ('図面を新規作成', ''),   # 冒頭が「新規」「変更」でなければ区分なし
])
def test_reason_kind_reads_the_start_of_the_reason_cell_by_header_name(value, expected):
    assert reason_kind(_header_with_reason(value)) == expected


def test_reason_kind_is_empty_when_header_has_no_reason_column():
    assert reason_kind(HEADER) == ''


def test_parse_tables_attaches_reason_kind_per_page():
    """区分はページ単位で読む（1ページ目は変更・2ページ目は新規のPDFで、行ごとに区分が違う）。"""
    row = ['', '', '006', 'ＵＮＩＴ', 'EE5443-006-01B', 'A3', '', '']
    rows = parse_tables([[_header_with_reason('変更|x'), item_table(row)], [_header_with_reason('新規'), item_table(row)]], 'x.pdf')
    assert [r['区分'] for r in rows] == ['変更', '新規'] and list(rows[0])[:2] == ['指図番号', '区分']
