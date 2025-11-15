# Pythonのベースイメージを使用
FROM python:3.11-slim

# アプリケーションコードを作業ディレクトリにコピー
WORKDIR /app
COPY . /app

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# ポートを指定 (fly.tomlで設定した8080に合わせる)
ENV PORT 8080

# アプリケーションの起動コマンド
CMD gunicorn MySoccerNoteApp:app -b 0.0.0.0:8080