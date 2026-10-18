"""出図目録 ⇔ 図面台帳 比較（Streamlit Cloud アプリ）。View層。処理は model/ にある。"""
import os

import pandas as pd
import streamlit as st

from model.catalog_pdf import parse_catalog_pdf
from model.compare import LEDGER_ONLY, NAME_DIFF, NO_LEDGER, NO_MARK, OK, build_catalog_list
from model.excel_export import INTEGRITY_COLORS, create_excel
from model.ledger import load_ledger, parse_ledger_filename

st.set_page_config(page_title="出図目録 比較", page_icon="📑", layout="wide")

# 日本語だけ英数字より小さく表示する（unicode-range + size-adjust）。streamlit スキル §11
st.markdown("""
    <style>
    @font-face {
        font-family: "AppMixedFont";
        src: local("Hiragino Kaku Gothic ProN"), local("Yu Gothic UI"),
             local("Yu Gothic"), local("Meiryo");
        unicode-range: U+3000-303F, U+3040-30FF, U+FF00-FFEF, U+4E00-9FFF, U+3400-4DBF;
        size-adjust: 94%;
    }
    @font-face {
        font-family: "AppMixedFont";
        src: local("Source Sans Pro"), local("Helvetica Neue"), local("Arial");
    }
    .stApp, .stApp p, .stApp li, .stApp label, .stApp td, .stApp th,
    .stApp h1, .stApp h2, .stApp h3, .stApp input, .stApp button {
        font-family: "AppMixedFont", sans-serif !important;
    }
    </style>
""", unsafe_allow_html=True)


def _input_signature(pdfs, ledger):
    """入力が変わったら結果を破棄するためのキー（名前とサイズ）。"""
    return (tuple(sorted((f.name, f.size) for f in pdfs)), (ledger.name, ledger.size) if ledger else None)


def _color_rows(df, colors):
    """colors: 行ごとの (背景, 文字) または None。"""
    def style_row(row):
        color = colors[row.name]
        return [f'background-color: {color[0]}; color: {color[1]}' if color else '' for _ in row]
    return df.style.apply(style_row, axis=1)


def run_comparison(pdfs, ledger_file, shiban):
    ledger_df, error = load_ledger(ledger_file.getvalue())
    if error:
        st.error(error)
        return None

    rows, excluded, skipped, errors = [], [], [], []
    placeholder = st.empty()
    bar = placeholder.progress(0.0, text="出図目録を読み込んでいます...")
    for i, f in enumerate(pdfs, start=1):
        parsed = parse_catalog_pdf(f.getvalue(), f.name)
        if parsed.status == 'skipped':
            skipped.append(f.name)
        elif parsed.status == 'error':
            errors.append(f"{f.name}: {parsed.message}")
        elif parsed.order_no != shiban:
            excluded.append(f"{f.name}（指図番号 {parsed.order_no or '不明'}）")
        else:
            rows += parsed.rows
        bar.progress(i / len(pdfs), text=f"{i}/{len(pdfs)}件を読み込み中...")
    placeholder.empty()

    if not rows:
        st.error(f"指番 {shiban} の出図目録を読み込めませんでした。")
        _show_warnings(excluded, skipped, errors)
        return None

    catalog_df = build_catalog_list(rows, ledger_df, shiban)
    return {
        'shiban': shiban, 'catalog_df': catalog_df,
        'excel': create_excel(catalog_df),
        'excluded': excluded, 'skipped': skipped, 'errors': errors,
        'pdf_count': len(pdfs) - len(excluded) - len(skipped) - len(errors),
    }


def _show_warnings(excluded, skipped, errors):
    if excluded:
        with st.expander(f"⚠️ 除外した出図目録（指番不一致）: {len(excluded)}件", expanded=True):
            st.write("台帳ファイル名の指番と異なる出図目録は比較対象から除外しました。")
            for name in excluded:
                st.write(f"- {name}")
    if errors:
        with st.expander(f"⚠️ 読み込めなかったPDF: {len(errors)}件", expanded=True):
            for message in errors:
                st.write(f"- {message}")
    if skipped:
        with st.expander(f"ℹ️ 出図目録ではないPDF（スキップ）: {len(skipped)}件"):
            for name in skipped:
                st.write(f"- {name}")


def show_result(result):
    catalog_df = result['catalog_df']
    counts = catalog_df['整合性'].value_counts()
    st.info(
        f"出図目録 {result['pdf_count']}ファイル・{(catalog_df['整合性'] != LEDGER_ONLY).sum()}行 ／ 整合性: "
        + "・".join(f"{label} {counts.get(label, 0)}件" for label in (OK, NAME_DIFF, NO_LEDGER, NO_MARK, LEDGER_ONLY))
    )
    _show_warnings(result['excluded'], result['skipped'], result['errors'])

    with st.expander("出図目録と図面台帳比較プレビュー", expanded=False):
        st.dataframe(_color_rows(catalog_df, [INTEGRITY_COLORS.get(v) for v in catalog_df['整合性']]),
                     width='stretch', hide_index=True)

    st.download_button(
        "Excelをダウンロード", data=result['excel'],
        file_name=f"{result['shiban']}_出図目録一覧.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


st.title("出図目録 ⇔ 図面台帳 比較")
st.caption("出図目録（PDF）の図面情報が、DXF-diff-manager で作成した図面管理台帳と一致しているかを確認します。")

st.subheader("入力ファイル")
# type= は指定しない（フォルダD&Dで他種のファイルが混ざっても読み込みが欠落しないように。streamlit スキル §3）
uploaded = st.file_uploader("出図目録（PDF・複数可・フォルダ可）", accept_multiple_files=True, key="pdf_files")
pdfs = [f for f in (uploaded or []) if f.name.lower().endswith('.pdf')]
ledger_file = st.file_uploader("図面管理台帳（Excel）", type=['xlsx'], key="ledger_file")

shiban = None
if ledger_file:
    shiban, _, _ = parse_ledger_filename(ledger_file.name)
    if shiban:
        st.info(f"台帳ファイル名から指番を取得しました: {shiban}")
    else:
        st.error("台帳ファイル名から指番を取得できません。ファイル名は「指番_モジュール_サイド.xlsx」"
                 "（例: ME26-9603-0_na_405.xlsx）にしてください。")

signature = _input_signature(pdfs, ledger_file)
result = st.session_state.get('result')
if result is not None and st.session_state.get('result_signature') != signature:
    st.session_state.pop('result', None)  # 入力が変わったら古い結果は出さない
    result = None

can_run = bool(pdfs) and bool(shiban)
if st.button("比較を実行", type="secondary" if result else "primary", disabled=not can_run):
    result = run_comparison(pdfs, ledger_file, shiban)
    if result is not None:
        st.session_state['result'] = result
        st.session_state['result_signature'] = signature
        st.rerun()  # ボタンの色（次にすべき操作）を新しい状態で描画し直す

if result is not None:
    st.divider()
    show_result(result)
