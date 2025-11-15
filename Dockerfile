# Pythonのベースイメージを使用
FROM python:3.11-slim

# アプリケーションコードを作業ディレクトリにコピー
WORKDIR /app
COPY . /app

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# アプリケーションコードを作業ディレクトリにコピー
WORKDIR /app
COPY . /app

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# ポートを指定 (fly.tomlで設定した8080に合わせる)
ENV PORT 8080

# アプリケーションの起動コマンド
CMD python -c "from MySoccerNoteApp import db, app; with app.app_context(): db.create_all();" && gunicorn MySoccerNoteApp:app -b 0.0.0.0:8080