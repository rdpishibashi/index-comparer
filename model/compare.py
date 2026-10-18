"""出図目録と図面台帳の比較（streamlit 非依存）。"""
import re

import pandas as pd

MARK = '▼'
TRUNCATION_MIN_CHARS = 40  # これ以上の長さで台帳文字列の先頭と一致すれば「目録側が途中で切れているだけ」とみなす
PREFIX_MARK = '【前方一致】'
NO_LEDGER_NAME = '（台帳に名称なし）'

LIST_COLUMNS = ['指図番号', '改', '品目名称', '図面番号', 'SZ', '備考',
                '図面台帳図番', '図面台帳品目名称', 'ファイル名', 'ページ']

STATE_BOTH = '両方'
STATE_CATALOG_ONLY = '出図目録のみ'
STATE_LEDGER_ONLY = '図面台帳のみ'


def to_catalog_name_format(subtitle, title):
    """Subtitle と Title を、出図目録の品目名称と同じ書式の文字列にする。

    半角空白で連結 → 空白類（全角含む。連続は1つ）を `_` に → 大文字 → 半角英数記号を全角に。
    """
    joined = ' '.join(p.strip() for p in (subtitle, title) if p and p.strip())
    joined = re.sub(r'[ 　]+', '_', joined).upper()
    return ''.join(chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in joined)


def judge_name(catalog_name, ledger_name):
    """'match' / 'prefix' / 'mismatch'。"""
    if catalog_name == ledger_name and ledger_name:
        return 'match'
    if (ledger_name and len(catalog_name) >= TRUNCATION_MIN_CHARS
            and ledger_name.startswith(catalog_name)):
        return 'prefix'
    return 'mismatch'


def _ledger_lookup(ledger_df):
    return {r.Child: to_catalog_name_format(r.Subtitle, r.Title) for r in ledger_df.itertuples()}


def build_catalog_list(catalog_rows, ledger_df):
    """出図目録の全行に「図面台帳図番」「図面台帳品目名称」を付けたDataFrame。

    内部列 `_status`（▼の行のみ both/name_diff/catalog_only）と `_name_judge` を持つ。
    """
    lookup = _ledger_lookup(ledger_df)
    out = []
    for row in catalog_rows:
        number = row['図面番号']
        in_ledger = bool(number) and number in lookup  # 空の図番（購入部品）は台帳と突き合わせない
        note, judge, status = '', '', ''
        if in_ledger:
            ledger_name = lookup[number]
            judge = judge_name(row['品目名称'], ledger_name)
            if judge == 'prefix':
                note = PREFIX_MARK + ledger_name
            elif judge == 'mismatch':
                note = ledger_name or NO_LEDGER_NAME
        if row['改'] == MARK:
            status = 'catalog_only' if not in_ledger else ('name_diff' if judge == 'mismatch' else 'both')
        out.append({**row, '図面台帳図番': 'Y' if in_ledger else '', '図面台帳品目名称': note,
                    '_status': status, '_name_judge': judge})
    return pd.DataFrame(out, columns=LIST_COLUMNS + ['_status', '_name_judge'])


_JUDGE_LABEL = {'match': '一致', 'prefix': '前方一致', 'mismatch': '不一致', '': '—'}


def build_drawing_comparison(catalog_df, ledger_df):
    """▼の図番と台帳 Child の和集合（1図番1行）。画面表示用。"""
    lookup = _ledger_lookup(ledger_df)
    marked = catalog_df[(catalog_df['改'] == MARK) & (catalog_df['図面番号'] != '')]
    unmarked_numbers = set(catalog_df.loc[(catalog_df['改'] != MARK) & (catalog_df['図面番号'] != ''), '図面番号'])

    rows = []
    for number in sorted(set(marked['図面番号']) | set(lookup)):
        sub = marked[marked['図面番号'] == number]
        ledger_name = lookup.get(number)
        if len(sub) and ledger_name is not None:
            state = STATE_BOTH
        elif len(sub):
            state = STATE_CATALOG_ONLY
        else:
            state = STATE_LEDGER_ONLY
        catalog_name = sub['品目名称'].iloc[0] if len(sub) else ''
        judge = judge_name(catalog_name, ledger_name) if state == STATE_BOTH else ''
        if state == STATE_LEDGER_ONLY:
            listed = '▼なしで記載' if number in unmarked_numbers else '記載なし'
        else:
            listed = '▼で記載'
        rows.append({
            '図面番号': number, '状態': state,
            '出図目録での記載': listed,
            '出図目録 品目名称': catalog_name,
            '図面台帳 品目名称（目録書式）': ledger_name or '',
            '品目名称判定': _JUDGE_LABEL[judge],
            '出図目録ファイル': ', '.join(dict.fromkeys(sub['ファイル名'])),
        })
    order = {STATE_BOTH: 0, STATE_CATALOG_ONLY: 1, STATE_LEDGER_ONLY: 2}
    rows.sort(key=lambda r: (order[r['状態']], r['図面番号']))
    return pd.DataFrame(rows)
