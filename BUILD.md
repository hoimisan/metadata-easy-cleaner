# Build Guide

## 開発環境

Windows + Python 3.11 を推奨します。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## テスト

```powershell
.\.venv\Scripts\Activate.ps1
python -m py_compile app.py tests\smoke_convert.py
python tests\smoke_convert.py
```

## 単体 exe ビルド

配布しやすい単体 exe を作る場合はこちらです。

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --onefile --name AIImageMetadataCleaner app.py
```

生成物:

```text
dist\AIImageMetadataCleaner.exe
```

## フォルダ形式ビルド

起動が速く、依存ファイルを展開済みにする形式です。

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller --noconfirm --windowed --name AIImageMetadataCleaner app.py
```

生成物:

```text
dist\AIImageMetadataCleaner\AIImageMetadataCleaner.exe
dist\AIImageMetadataCleaner\_internal\
```

この形式では `_internal` フォルダも必ず一緒に配布してください。
