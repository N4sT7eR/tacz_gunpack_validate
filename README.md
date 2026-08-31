# tacz_gunpack_validate

[![Latest release](https://img.shields.io/github/v/release/akanekocat1-prog/tacz_gunpack_validate?label=%E6%9C%80%E6%96%B0%E7%89%88&sort=semver)](https://github.com/akanekocat1-prog/tacz_gunpack_validate/releases/latest)
[![CI](https://github.com/akanekocat1-prog/tacz_gunpack_validate/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/akanekocat1-prog/tacz_gunpack_validate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

TaCZ (Timeless and Classics Zero) の Gunpack を、**Minecraft を起動せずに** 検証するツールです。

JSON の構文チェックに留まらず、TaCZ 独自のファイル構造・リソース参照・命名規則・数値の妥当性まで検査し、
「行番号・エラー内容・修正案」を一覧で出力します。

> A validator for TaCZ gunpacks. Reports JSON syntax errors, broken resource
> references, invalid identifiers and out-of-range values with line numbers and
> suggested fixes. English and Japanese output.

## ダウンロード

### ➜ [最新版をダウンロード](https://github.com/akanekocat1-prog/tacz_gunpack_validate/releases/latest)

Windows 用の実行ファイルです。Python のインストールは不要で、**ダウンロードしてそのまま起動できます**。

| ファイル | 用途 |
|---|---|
| `TaCZValidator.exe` | GUI 版。通常はこちらを使ってください |
| `TaCZValidator-cli.exe` | コマンドライン版。CI や自動化向け |

### 使いはじめ（3ステップ）

1. `TaCZValidator.exe` を起動する
2. Gunpack の **ZIP かフォルダをウィンドウにドラッグ＆ドロップ**する（`ZIP を選択...` ボタンでも可）
3. 結果を確認し、必要なら `CSV を保存` / `Markdown を保存` で出力する

ZIP は展開せずにそのまま検証できます。表示言語は OS の設定に従い、画面右上のプルダウンで英語／日本語を切り替えられます（次回起動時も選択した言語で開きます）。

> Windows Defender が署名のない実行ファイルに警告を出すことがあります。その場合は「詳細情報」→「実行」を選択してください。

開発中のビルドを試したい場合は、[Actions](https://github.com/akanekocat1-prog/tacz_gunpack_validate/actions) の各実行ページ下部にある **Artifacts** から取得できます（GitHub へのログインが必要、保持期間 90 日）。

## 検出できるもの

| 分類 | 例 |
|---|---|
| JSON 構文 | カンマ抜け、括弧不足、文字列の閉じ忘れ、重複キー |
| 命名規則 | namespace / リソース ID / ファイル名の大文字・空白・不正文字 |
| 参照切れ | `display` / `data` / model / texture / animation / sound の参照先が存在しない |
| 大文字小文字の不一致 | `m4a1` を参照しているのに実ファイルが `M4A1.png` |
| スキーマ | 必須キーの欠落、型の誤り、未知の `type` や `bolt` の値（typo 候補を提示） |
| 数値 | `rpm` が範囲外、`ammo_amount` が 0 以下 など |
| 翻訳 | `name` / `tooltip` の翻訳キーが言語ファイルに無い |

TaCZ 公式デフォルトパック（1.1.8）に対して **ERROR 0 件**になるよう調整しています。
仕様が不明な項目を ERROR にしない、という方針です。

## GUI（Windows 向け）

ボタンひとつで検証できる画面を同梱しています。

```bash
pip install -e ".[gui]"
tacz-validate-gui          # または python -m tacz_validator.gui
```

- **Gunpack の指定**：ZIP／フォルダを選択ボタンで指定、または**ウィンドウへドラッグ＆ドロップ**（ドロップ時は自動で検証開始）
- **ZIP のまま検証**：展開不要です
- **言語**：初回は OS の言語を自動判定し、以後は選択した言語を記憶します（再検証なしで即時切替）
- **結果一覧**：重要度・コード・ファイル・行・内容・修正案。重要度チェックとテキストで絞り込み可能
- **出力**：出力先フォルダを選択し、`CSV を保存` / `Markdown を保存`。ファイル名は `<パック名>_<日時>.csv` の形式で自動生成されます
- **中止**：大きなパックの検証中も画面は固まらず、`中止` ボタンで停止できます

## インストール

ソースから使う場合（EXE を使うなら不要です）:

```bash
git clone https://github.com/akanekocat1-prog/tacz_gunpack_validate.git
cd tacz_gunpack_validate
pip install -e .
```

## 使い方

フォルダでも ZIP でも、そのまま指定できます。

```bash
tacz-validate path/to/my_gunpack
tacz-validate my_gunpack_v1.0.0.zip --lang ja
```

出力例:

```text
ERROR   REF001  assets/scgun/display/ammo/65x52_display.json:2:12
  モデルが見つかりません: scgun:ammo/65x52_geo
  → 想定されるファイル: assets/scgun/geo_models/ammo/65x52_geo.json

エラー 2 件、警告 1 件、情報 0 件  （48 ファイル / 0.02 秒）
```

### レポートの出力

```bash
tacz-validate my_pack.zip --lang ja --format csv -o report.csv   # Excel で開けます（BOM 付き UTF-8）
tacz-validate my_pack.zip --lang ja --format md  -o report.md
tacz-validate my_pack.zip --format json -o findings.json         # CI 用
```

### 主なオプション

| オプション | 説明 |
|---|---|
| `--lang {en,ja}` | 出力言語 |
| `--severity {error,warning,info}` | 表示する最低の重要度 |
| `--ignore CODE` | 特定のコードを抑制（例: `--ignore LANG001`） |
| `--disable CHECK` | 検査単位で無効化（例: `--disable localization`） |
| `--external NAMESPACE` | 他パックが提供する namespace として扱う |
| `--strict-json` | コメントや末尾カンマも報告する |
| `--list-checks` | 検査の一覧を表示 |

終了コードは、ERROR が 1 件でもあれば `1`、それ以外は `0` です（CI で利用できます）。

## 対応バージョン

TaCZ 1.20.1 系（デフォルトパック 1.1.8 基準）。

ルールはコードではなく [`src/tacz_validator/rules/`](src/tacz_validator/rules/) の JSON に外出ししてあるため、
別バージョンへの対応はルールファイルの追加で行えます。

## 開発

```bash
python -m unittest discover -s tests -t .   # テスト（GUI 分は PySide6 未導入なら自動スキップ）
python -m tacz_validator.cli --list-checks  # 検査一覧
```

GUI のテストはヘッドレスで実行されます。

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -t .
```

構成:

```text
src/tacz_validator/
  core/         JSONC パーサ、インデックス、参照解決、パイプライン
  rules/        バージョン別ルール（JSON）
  validators/   各検査
  reporting/    text / CSV / Markdown / JSON 出力
  locales/      英語・日本語のメッセージ
  cli/          コマンドライン
  gui/          PySide6 の画面（設定の永続化・非同期実行を含む）
tests/data/     検証用の自作サンプルパック
```

## ブランチ運用

| ブランチ | 内容 |
|---|---|
| `develop` | 開発用。テスト（`tests/`）を含みます |
| `main` | リリース用。**テストは含みません**（利用者が実行するものだけを置きます） |
| `release/vX.Y` | 各リリース時点のスナップショット |

main への反映はスクリプトで行います。develop をマージしつつ `tests/` を除外するため、
main は develop の子孫のまま保たれ、次回以降のマージも競合しません。

```bash
packaging/release_to_main.sh          # main を更新するだけ
packaging/release_to_main.sh v1.0.0   # あわせてタグも作成
```

タグ（`v*`）を push すると、GitHub Actions が EXE を添付した Release を作成します。

## ライセンス

MIT License。

このリポジトリには TaCZ 本体や配布 Gunpack のファイルは含まれていません。
`tests/data/` のサンプルは、検証用に本プロジェクトで作成したものです。
