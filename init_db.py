import os
from MySoccerNoteApp import db, app

# 環境変数チェックとURI修正は MySoccerNoteApp.py で行われているため、
# ここではアプリコンテキストを設定して db.create_all() を実行するだけ
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")