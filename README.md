# tacz_gunpack_validate

TaCZ (Timeless and Classics Zero) の Gunpack を、**Minecraft を起動せずに** 検証するツールです。

JSON の構文チェックに留まらず、TaCZ 独自のファイル構造・リソース参照・命名規則・数値の妥当性まで検査し、
「行番号・エラー内容・修正案」を一覧で出力します。

> A validator for TaCZ gunpacks. Reports JSON syntax errors, broken resource
> references, invalid identifiers and out-of-range values with line numbers and
> suggested fixes. English and Japanese output.

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

## インストール

```bash
git clone https://github.com/akanekocat1-prog/tacz_gunpack_validate.git
cd tacz_gunpack_validate
pip install -e .
```

Windows 用の実行ファイル（EXE）は [Releases](https://github.com/akanekocat1-prog/tacz_gunpack_validate/releases) から入手できます。

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
python -m unittest discover -s tests -t .   # テスト
python -m tacz_validator.cli --list-checks  # 検査一覧
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
tests/data/     検証用の自作サンプルパック
```

## ライセンス

MIT License。

このリポジトリには TaCZ 本体や配布 Gunpack のファイルは含まれていません。
`tests/data/` のサンプルは、検証用に本プロジェクトで作成したものです。
