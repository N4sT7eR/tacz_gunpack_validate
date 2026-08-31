# tacz_gunpack_validate

[![Latest release](https://img.shields.io/github/v/release/N4sT7eR/tacz_gunpack_validate?label=%E6%9C%80%E6%96%B0%E7%89%88&sort=semver)](https://github.com/N4sT7eR/tacz_gunpack_validate/releases/latest)
[![CI](https://github.com/N4sT7eR/tacz_gunpack_validate/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/N4sT7eR/tacz_gunpack_validate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

TaCZ (Timeless and Classics Zero) の Gunpack を、**Minecraft を起動せずに** 検証するツールです。

JSON の構文チェックに留まらず、TaCZ 独自のファイル構造・リソース参照・命名規則・数値の妥当性まで検査し、
「行番号・エラー内容・修正案」を一覧で出力します。

> A validator for TaCZ gunpacks. Reports JSON syntax errors, broken resource
> references, invalid identifiers and out-of-range values with line numbers and
> suggested fixes. English and Japanese output.

## ダウンロード

### ➜ [最新版をダウンロード](https://github.com/N4sT7eR/tacz_gunpack_validate/releases/latest)

Windows 用です。Python のインストールは不要です。

| ファイル | 用途 |
|---|---|
| `TaCZValidator-vX.Y.Z-windows.zip` | **GUI 版。通常はこちらを使ってください** |
| `TaCZValidator-cli.exe` | コマンドライン版。CI や自動化向け |
| `checksums-sha256.txt` | ダウンロードの検証用 |

### 使いはじめ（4ステップ）

1. ZIP をダウンロードし、**任意の場所に展開する**
2. 展開したフォルダの中の `TaCZValidator.exe` を起動する
3. Gunpack の **ZIP かフォルダをウィンドウにドラッグ＆ドロップ**する（`ZIP を選択...` ボタンでも可）
4. 結果を確認し、必要なら `CSV を保存` / `Markdown を保存` で出力する

Gunpack の ZIP は展開せずにそのまま検証できます。表示言語は OS の設定に従い、画面右上のプルダウンで英語／日本語を切り替えられます（次回起動時も選択した言語で開きます）。

> **フォルダごと展開してください。** `TaCZValidator.exe` は同じフォルダ内のファイルを使って動作するため、EXE だけを取り出すと起動しません。デスクトップに置きたい場合は、EXE を右クリック →「ショートカットの作成」をご利用ください。

> 署名を付けていないため、Windows が警告を表示することがあります。その場合は「詳細情報」→「実行」を選択してください。ダウンロードしたファイルが正規のものか確認したい場合は、`checksums-sha256.txt` の値と照合できます（PowerShell で `Get-FileHash <ファイル> -Algorithm SHA256`）。

開発中のビルドを試したい場合は、[Actions](https://github.com/N4sT7eR/tacz_gunpack_validate/actions) の各実行ページ下部にある **Artifacts** から取得できます（GitHub へのログインが必要、保持期間 90 日）。

## 検出できるもの

| 分類 | コード | 例 |
|---|---|---|
| JSON構文 | `JSON` | カンマ抜け、括弧不足、文字列の閉じ忘れ、重複キー |
| パック構造 | `PACK` | `gunpack.meta.json` の欠落、宣言した namespace の実体が無い |
| 命名規則 | `ID` | namespace / リソース ID / ファイル名の大文字・空白・不正文字 |
| スキーマ | `ENTRY` | 必須キーの欠落、型の誤り、未知の `type` や `bolt` の値（typo 候補を提示）、`rpm` が範囲外、`ammo_amount` が 0 以下 |
| 参照 | `REF` | `display` / `data` / model / texture / animation / sound の参照先が存在しない。`m4a1` を参照しているのに実ファイルが `M4A1.png` |
| 翻訳 | `LANG` | `name` / `tooltip` の翻訳キーが言語ファイルに無い |

TaCZ 公式デフォルトパック（1.1.8）に対して **ERROR 0 件**になるよう調整しています。
仕様が不明な項目を ERROR にしない、という方針です。

### 分類について

重要度（ERROR / WARNING / INFO）が「どれだけ壊れているか」を表すのに対し、
分類は「**どの決まりに反しているか**」を表します。
JSON そのものが壊れているのか、TaCZ 独自の構造の話なのか、命名規則なのかが一目で分かります。

分類はコードの接頭辞から決まり、結果一覧・CSV・Markdown・JSON のすべてに出力されます。
一覧は `tacz-validate --list-categories` で確認できます。

```bash
tacz-validate my_pack --category reference          # 参照切れだけを見る
tacz-validate my_pack --ignore-category localization # 翻訳の指摘を除く
```

`Luaスクリプト`（`LUA`）と `推奨`（`ASSET`）の 2 つは分類として登録済みですが、
現時点で検出する項目はありません。Lua スクリプトの静的解析は次期対応予定です。

## GUI（Windows 向け）

ボタンひとつで検証できる画面を同梱しています。

```bash
pip install -e ".[gui]"
tacz-validate-gui          # または python -m tacz_validator.gui
```

- **Gunpack の指定**：ZIP／フォルダを選択ボタンで指定、または**ウィンドウへドラッグ＆ドロップ**（ドロップ時は自動で検証開始）
- **ZIP のまま検証**：展開不要です
- **言語**：初回は OS の言語を自動判定し、以後は選択した言語を記憶します（再検証なしで即時切替）
- **結果一覧**：重要度・分類・コード・ファイル・行・内容・修正案。重要度チェック・分類のプルダウン・テキストで絞り込み可能（分類の選択は次回起動時も保持されます）
- **出力**：出力先フォルダを選択し、`CSV を保存` / `Markdown を保存`。ファイル名は `<パック名>_<日時>.csv` の形式で自動生成されます
- **中止**：大きなパックの検証中も画面は固まらず、`中止` ボタンで停止できます

## インストール

ソースから使う場合（EXE を使うなら不要です）:

```bash
git clone https://github.com/N4sT7eR/tacz_gunpack_validate.git
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
ERROR   参照      REF001  assets/scgun/display/ammo/65x52_display.json:2:12
  モデルが見つかりません: scgun:ammo/65x52_geo
  → 想定されるファイル: assets/scgun/geo_models/ammo/65x52_geo.json

エラー 2 件、警告 1 件、情報 0 件  （48 ファイル / 0.02 秒）
  参照 2 / スキーマ 1
```

最後の行は分類ごとの内訳です。どの種類のファイルを開けばよいかの当たりが付きます。

### レポートの出力

```bash
tacz-validate my_pack.zip --lang ja --format csv -o report.csv   # Excel で開けます（BOM 付き UTF-8）
tacz-validate my_pack.zip --lang ja --format md  -o report.md
tacz-validate my_pack.zip --format json -o findings.json         # CI 用
```

`--severity` や `--category` で絞り込んだ場合、ファイルに出力されるのも画面と同じ内容になります。
ただしサマリーの件数と分類ごとの内訳は、絞り込みに関わらず**常に実行全体**の数です。

> **0.10.0 での変更点**：CSV に「分類」列が `重要度` の直後に追加されました。
> **列は位置ではなくヘッダ名で読んでください。**自動処理を組んでいる場合は影響を受けます。
> JSON 出力への変更は `category` フィールドと `summary.by_category` の追加のみで、既存のフィールドはそのままです。

### 主なオプション

| オプション | 説明 |
|---|---|
| `--lang {en,ja}` | 出力言語 |
| `--severity {error,warning,info}` | 表示する最低の重要度 |
| `--ignore CODE` | 特定のコードを抑制（例: `--ignore LANG001`） |
| `--category CATEGORY` | 指定した分類だけを表示（例: `--category reference`。繰り返し可） |
| `--ignore-category CATEGORY` | 分類ごと抑制（例: `--ignore-category convention`。繰り返し可） |
| `--disable CHECK` | 検査単位で無効化（例: `--disable localization`） |
| `--external NAMESPACE` | 他パックが提供する namespace として扱う |
| `--strict-json` | コメントや末尾カンマも報告する |
| `--list-checks` | 検査の一覧を表示 |
| `--list-categories` | 分類とコード接頭辞の対応を表示 |

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
