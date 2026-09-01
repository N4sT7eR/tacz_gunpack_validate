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
| `TaCZValidator-cli-vX.Y.Z.exe` | コマンドライン版。CI や自動化向け |
| `checksums-sha256.txt` | ダウンロードの検証用 |

### 使いはじめ（4ステップ）

1. ZIP をダウンロードし、**任意の場所に展開する**
2. 展開したフォルダの中の `TaCZValidator-vX.Y.Z.exe` を起動する
3. Gunpack の **ZIP かフォルダをウィンドウにドラッグ＆ドロップ**する（`ZIP を選択...` ボタンでも可）
4. 結果を確認し、必要なら `CSV を保存` / `Markdown を保存` で出力する

Gunpack の ZIP は展開せずにそのまま検証できます。表示言語は OS の設定に従い、画面右上のプルダウンで英語／日本語を切り替えられます（次回起動時も選択した言語で開きます）。

> **フォルダごと展開してください。** `TaCZValidator-vX.Y.Z.exe` は同じフォルダ内のファイルを使って動作するため、EXE だけを取り出すと起動しません。デスクトップに置きたい場合は、EXE を右クリック →「ショートカットの作成」をご利用ください。

> **バージョンの見分け方。** EXE のファイル名にバージョンが入っています（`TaCZValidator-v1.0.0.exe`）。
> ファイルのプロパティ（右クリック →「プロパティ」→「詳細」）にも同じ値が埋め込まれているほか、
> コマンドライン版は `TaCZValidator-cli-vX.Y.Z.exe --version` でも確認できます。
> **更新時は EXE の名前が変わるため、以前に作成したショートカットは作り直してください。**

> 署名を付けていないため、Windows が警告を表示することがあります。その場合は「詳細情報」→「実行」を選択してください。ダウンロードしたファイルが正規のものか確認したい場合は、`checksums-sha256.txt` の値と照合できます（PowerShell で `Get-FileHash <ファイル> -Algorithm SHA256`）。

開発中のビルドを試したい場合は、[Actions](https://github.com/N4sT7eR/tacz_gunpack_validate/actions) の各実行ページ下部にある **Artifacts** から取得できます（GitHub へのログインが必要、保持期間 90 日）。`TaCZValidator-GUI-vX.Y.Z` と `TaCZValidator-CLI-vX.Y.Z` に分かれているので、必要なほうだけダウンロードしてください。

> **開発版には `-dev` が付きます。**`TaCZValidator-v1.0.0-dev.exe` のようにファイル名へ入り、
> ファイルのプロパティと `--version` の出力にも同じ値が出ます。リリース版と取り違える心配はありません。

## 検出できるもの

| 分類 | コード | 例 |
|---|---|---|
| JSON構文 | `JSON` | カンマ抜け、括弧不足、文字列の閉じ忘れ、重複キー |
| パック構造 | `PACK` | `gunpack.meta.json` の欠落、宣言した namespace の実体が無い |
| 命名規則 | `ID` | namespace / リソース ID / ファイル名の大文字・空白・不正文字 |
| スキーマ | `ENTRY` | 必須キーの欠落、型の誤り、未知の `type` や `bolt` の値（typo 候補を提示）、`rpm` が範囲外、`ammo_amount` が 0 以下 |
| 参照 | `REF` | `display` / `data` / model / texture / animation / sound の参照先が存在しない。`m4a1` を参照しているのに実ファイルが `M4A1.png` |
| 翻訳 | `LANG` | `name` / `tooltip` の翻訳キーが言語ファイルに無い |
| Luaスクリプト | `LUA` | 構文エラー、未定義のグローバル（typo 候補を提示）、サンドボックス外のライブラリ、`return` 忘れ、`require` の参照切れ、UTF-8 以外の保存 |

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

`推奨`（`ASSET`）は分類として登録済みですが、現時点で検出する項目はありません。

## Lua スクリプトの検査

TaCZ の Gunpack は `assets/<namespace>/scripts/`（状態機）と `data/<namespace>/scripts/`（銃ロジック）に
Lua を置けます。TaCZ はこれをサンドボックス化した LuaJ 3.0（Lua 5.2 相当）で実行しますが、
**Lua は間違いを黙って握りつぶします**。定数を打ち間違えれば `nil`、無いライブラリも `nil`、
`return` を忘れたモジュールは空として読み込まれる——どれもゲーム内で銃が妙な動きをするまで表面化しません。

| コード | 重要度 | 検出内容 |
|---|---|---|
| `LUA001` | ERROR | 構文エラー。行・列と、何が足りないか／余分かを示し、直し方を提示します |
| `LUA002` | WARNING | このスクリプトで定義されていない名前。TaCZ の定数に近ければ候補を提示 |
| `LUA003` | ERROR | `io` / `os` / `coroutine` / `debug` / `luajava` —— TaCZ が読み込んでいないライブラリ |
| `LUA004` | ERROR | スクリプトが値を `return` していない |
| `LUA005` | ERROR | `require` の参照先がパック内に無い |
| `LUA006` | INFO | luaparser 未導入のため検査をスキップした |
| `LUA007` | ERROR | UTF-8 以外で保存されている |

参照できる定数（`PLAY_ONCE_STOP`、`INPUT_RELOAD`、`NOT_RELOADING` など 26 個）と、
サンドボックスが導入するライブラリの一覧は、TaCZ 本体の jar から読み取って
[`rules/`](src/tacz_validator/rules/) の JSON に記載しています。

構文エラーは、原因の分かる文言に翻訳して報告します。解析ライブラリが返す
`mismatched input 'end' expecting <EOF>` のような文言をそのまま出しても直しようがないためです。

```text
ERROR   Luaスクリプト  LUA001  assets/scgun/scripts/ak47_state_machine.lua:41:5
  return の手前に then が不足しています
  → 不足している then を補ってください
```

`end` の過不足、`then` 忘れ、テーブルのカンマ抜け、文字列の閉じ忘れ、`!=` の誤用、
条件式での `=` と `==` の取り違えなどを、**すべて行・列つきで**報告します。

構文解析には `luaparser` が必要です。**任意の依存**なので、未導入なら Lua の検査は
スキップされ、その旨が `LUA006` として INFO で報告されます（黙って通過することはありません）。

```bash
pip install "tacz-gunpack-validate[lua]"
```

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

カバレッジ（設定は `pyproject.toml` にあり、GUI は除外されます）:

```bash
pip install -e ".[lua,dev]"
python -m coverage run -m pytest && python -m coverage report
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
tests/data/     検証用の自作サンプルパック（valid / broken / lua / lua_syntax）
CHANGELOG.md    バージョンごとの変更履歴
```

## ブランチ運用

| ブランチ | 内容 |
|---|---|
| `main` | リリース用。常にリリース可能な状態を保ちます |
| `develop` | 次期バージョンの開発・統合用 |
| `feature/*` | 大きめの機能追加。`develop` から分岐し `develop` へ戻します |
| `fix/*` | 通常開発中の不具合修正。`develop` から分岐し `develop` へ戻します |
| `hotfix/*` | リリース後の緊急修正。`main` から分岐し `main` と `develop` の両方へ反映します |

小規模な変更は `develop` 上で直接行って構いません。複数ファイルにまたがる変更や
既存機能への影響が大きい変更は `feature/*` に分離します。

**テストは `main` にも含めます。**`tests/` は品質維持のための正式なソースであり、
main も develop と同じスイートで検証されます。リリース前に取り除くのは、デバッグ出力や
一時的な検証コードなど、利用者に不要なものだけです。

`feature/*` `fix/*` `hotfix/*` への push でも CI と Windows ビルドが動きます。

タグと `main` 以外から作られたビルドは、バージョンに `-dev` が付きます。ファイル名・
Windows のバージョンリソース・`--version` の3か所すべてに反映されるため、開発版を
リリース版と取り違えることはありません。

変更内容は [CHANGELOG.md](CHANGELOG.md) に記録します。`main` へ昇格する前に、
そのバージョンの項目を「未リリース」から新しい見出しへ移してください。

### リリース手順

```bash
packaging/release_to_main.sh          # develop を main へマージするだけ
packaging/release_to_main.sh v1.0.0   # あわせてタグも作成
```

スクリプトは push しません。実行すべきコマンドを表示するだけです。実行前に
`pyproject.toml` と `src/tacz_validator/__init__.py` のバージョンが一致しているか、
指定したタグが未使用かを検査し、いずれかが崩れていれば中断します。

タグ（`v*`）を push すると、GitHub Actions が EXE を添付した Release を作成します。
タグを push しなければ Release は作られません。公開済みのタグは付け替えません。

バージョンは Semantic Versioning に従います。

## ライセンス

MIT License。

このリポジトリには TaCZ 本体や配布 Gunpack のファイルは含まれていません。
`tests/data/` のサンプルは、検証用に本プロジェクトで作成したものです。
