"""出図目録と図面台帳の比較（streamlit 非依存）。"""
import re

import pandas as pd

MARK = '▼'
TRUNCATION_MIN_CHARS = 40  # これ以上の長さで台帳文字列の先頭と一致すれば「目録側が途中で切れているだけ」とみなす
NO_LEDGER_NAME = '（台帳に名称なし）'

LIST_COLUMNS = ['指図番号', '改', '品目名称', '図面番号', 'SZ', '備考',
                '整合性', '図面台帳品目名称', 'ファイル名', 'ページ']

# 「整合性」列の値
OK = '完全一致'
NAME_DIFF = '品目名称不一致'
NO_LEDGER = '台帳なし▼'
NO_MARK = '▼なし'
LEDGER_ONLY = '台帳のみ'


def to_catalog_name_format(subtitle, title):
    """Subtitle と Title を、出図目録の品目名称と同じ書式の文字列にする。

    半角空白で連結 → 空白類（全角含む。連続は1つ）を `_` に → 大文字 → 半角英数記号を全角に。
    """
    joined = ' '.join(p.strip() for p in (subtitle, title) if p and p.strip())
    joined = re.sub(r'[ 　]+', '_', joined).upper()
    return ''.join(chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in joined)


def names_match(catalog_name, ledger_name):
    """完全一致、または目録側が途中で切れているだけ（40文字以上で台帳文字列の先頭と一致）なら True。"""
    if not ledger_name:
        return False
    if catalog_name == ledger_name:
        return True
    return len(catalog_name) >= TRUNCATION_MIN_CHARS and ledger_name.startswith(catalog_name)


def _ledger_lookup(ledger_df):
    return {r.Child: to_catalog_name_format(r.Subtitle, r.Title) for r in ledger_df.itertuples()}


def build_catalog_list(catalog_rows, ledger_df, shiban):
    """出図目録の全行に「整合性」「図面台帳品目名称」を付け、台帳にしかない図番の行を末尾に足す。

    - 整合性: 図番が空の行（購入部品）と、▼なしで台帳にも無い図番の行は空欄
    - 図面台帳品目名称: 台帳に図番があり、品目名称が一致しない場合のみ台帳側を目録書式で記載
    """
    lookup = _ledger_lookup(ledger_df)
    out = []
    for row in catalog_rows:
        number = row['図面番号']
        in_ledger = bool(number) and number in lookup  # 空の図番は台帳と突き合わせない
        ledger_name = lookup.get(number, '') if in_ledger else ''
        name_ok = in_ledger and names_match(row['品目名称'], ledger_name)
        note = '' if (not in_ledger or name_ok) else (ledger_name or NO_LEDGER_NAME)
        if not number:
            integrity = ''
        elif row['改'] == MARK:
            integrity = (OK if name_ok else NAME_DIFF) if in_ledger else NO_LEDGER
        else:
            integrity = NO_MARK if in_ledger else ''
        out.append({**row, '整合性': integrity, '図面台帳品目名称': note})

    in_catalog = {r['図面番号'] for r in catalog_rows if r['図面番号']}
    for child in sorted(set(lookup) - in_catalog):
        out.append({'指図番号': shiban, '改': '', '品目名称': '', '図面番号': child, 'SZ': '', '備考': '',
                    '整合性': LEDGER_ONLY, '図面台帳品目名称': lookup[child] or NO_LEDGER_NAME,
                    'ファイル名': '', 'ページ': None})
    df = pd.DataFrame(out, columns=LIST_COLUMNS)
    # 台帳のみの行は「ページ」が空。int と None の混在列は Arrow 変換で警告になるため nullable 整数にそろえる
    df['ページ'] = df['ページ'].astype('Int64')
    return df
