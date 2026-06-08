# metadata-easy-cleaner

AI画像からメタデータを削除し、PNG / JPEG に一括変換できる Windows 向けデスクトップアプリです。

Stable Diffusion や各種画像生成AIサービスで作成した画像には、プロンプト、生成設定、EXIF、PNG info などのメタデータが含まれることがあります。metadata-easy-cleaner は、画像を配布・投稿する前にメタデータを確認し、必要に応じて削除したクリーンな画像として保存するためのツールです。

## Features

- PNG / JPEG / WebP / BMP / TIFF の読み込み
- PNG または JPEG への一括変換
- 保存時に EXIF / PNG info などのメタデータを引き継がない
- 選択した単発画像のメタデータ表示
- メタデータがない画像は「メタデータはありません」と表示
- PNG -> PNG は画質改善をオフにすればピクセルを維持して保存
- JPEG 品質、PNG 圧縮レベルの指定
- ファイル追加、フォルダ追加、ドラッグ&ドロップ追加
- 前回選んだ保存先を次回起動時に復元
- 元画像と同じフォルダへの保存
- 変換後フォルダを開く
- 保存名の一括リネーム
- 簡易画質改善
  - シャープ
  - コントラスト
  - 彩度

## Download

GitHub Releases から `AIImageMetadataCleaner.exe` をダウンロードして起動してください。

ソースコード込みで確認・改造したい場合は、`AIImageMetadataCleaner-0.1.0-open-source.zip` を使ってください。

## Usage

1. `AIImageMetadataCleaner.exe` を起動します。
2. 「ファイル追加」または「フォルダ追加」で画像を追加します。
3. 必要に応じて「メタデータ表示」で選択画像のメタデータを確認します。
4. 出力形式、保存先、保存名、品質設定を選びます。
   - 「元画像と同じフォルダに保存する」をオンにすると、保存先欄ではなく各元画像のフォルダに保存します。
   - 「変換後フォルダを開く」をオンにすると、変換完了後に保存先フォルダを開きます。
5. 「変換開始」を押します。

## Rename Pattern

保存名には次のプレースホルダーが使えます。

```text
{name}    元ファイル名
{index}   連番
{number}  ゼロ埋め連番
{ext}     出力拡張子
```

例:

```text
{name}_clean
image_{number}
```

## Development

Windows + Python 3.11 を推奨します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Test

```powershell
.\.venv\Scripts\Activate.ps1
python -m py_compile app.py tests\smoke_convert.py
python tests\smoke_convert.py
```

## Build

単体 exe として配布する場合:

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --onefile --name AIImageMetadataCleaner app.py
```

生成物:

```text
dist\AIImageMetadataCleaner.exe
```

フォルダ形式で配布する場合:

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --name AIImageMetadataCleaner app.py
```

この形式では、`dist\AIImageMetadataCleaner\_internal` フォルダも exe と一緒に配布してください。

## Notes

- JPEG は形式上、再保存時に非可逆圧縮になります。
- PNG -> PNG は画質改善をオフにしていればピクセルを維持します。
- 画質改善をオンにした場合は画像処理を行うため、ピクセルは変化します。
- メタデータ削除は Pillow で画像を読み込み、保存時に EXIF / PNG info などを渡さない方式です。

## License

MIT License
