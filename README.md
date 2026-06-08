# AI Image Metadata Cleaner

Stable Diffusion や画像生成 AI サイトで作成した画像からメタデータを削除し、PNG/JPEG に一括変換するデスクトップアプリです。

## 主な機能

- PNG / JPEG / WebP / BMP / TIFF の読み込み
- PNG または JPEG への一括変換
- メタデータを引き継がずに保存
- 選択した単発画像のメタデータ表示
- メタデータがない画像は「メタデータはありません」と表示
- PNG -> PNG はピクセルを維持してロスレス保存
- JPEG 品質、PNG 圧縮レベルの指定
- ファイルまたはフォルダの追加
- ドラッグ&ドロップ追加
- 保存名の一括リネーム
- 任意で簡易画質改善
  - シャープ
  - コントラスト
  - 彩度

## 開発実行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## 配布用ビルド

単体 exe として配布する場合はこちらを使います。

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --onefile --name AIImageMetadataCleaner app.py
```

生成物は `dist\AIImageMetadataCleaner.exe` に出力されます。

フォルダ形式で配布する場合はこちらです。

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --name AIImageMetadataCleaner app.py
```

生成物は `dist\AIImageMetadataCleaner\AIImageMetadataCleaner.exe` に出力されます。この形式では、`_internal` フォルダも exe と一緒に配布してください。
既存の出力先がロックされている場合は、次のように別フォルダへ出力できます。

```powershell
pyinstaller --noconfirm --windowed --name AIImageMetadataCleaner --distpath dist_updated app.py
```

## 動作確認

```powershell
.\.venv\Scripts\Activate.ps1
python -m py_compile app.py
python tests\smoke_convert.py
```

## 注意

- JPEG は形式上、再保存時に非可逆圧縮になります。
- PNG -> PNG は画像ピクセルを変更せずに保存します。ただし「画質改善」を有効にした場合は画像処理を行うため、ピクセルは変化します。
- メタデータ削除は Pillow で画像を読み込み、EXIF / PNG info などを保存時に渡さない方式です。
