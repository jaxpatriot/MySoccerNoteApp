import os
import json
import datetime # <--- datetime モジュールをインポート
from datetime import datetime, timedelta # <--- datetime と timedelta をインポート
from flask import Flask, render_template, request, redirect, url_for, flash, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, delete, func 
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL')
basedir = os.path.abspath(os.path.dirname(__file__))
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'soccer_note.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a_very_secret_key_for_testing_csrf'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
db = SQLAlchemy(app) 
login_manager = LoginManager()
login_manager.init_app(app) 
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.before_request
def before_request():
    g.user = current_user

# ----------------------------------------------------
# モデル定義
# ----------------------------------------------------
class User(UserMixin, db.Model): 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    members = db.relationship('Member', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    layouts = db.relationship('Layout', backref='creator', lazy='dynamic', cascade='all, delete-orphan')
    matches = db.relationship('Match', backref='creator', lazy='dynamic', cascade='all, delete-orphan')
    practices = db.relationship('Practice', backref='creator', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) 
    
    def get_id(self):
        return str(self.id)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    number = db.Column(db.String(5), nullable=True)
    position = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Member {self.name}>'
        
class Practice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False) 
    date = db.Column(db.DateTime, nullable=False) 
    location = db.Column(db.String(100), nullable=True) 
    menu = db.Column(db.Text, nullable=True) 
    notes = db.Column(db.Text, nullable=True) 

    def __repr__(self):
        return f'<Practice {self.title} on {self.date.strftime("%Y-%m-%d")}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.Integer, db.ForeignKey('practice.id', ondelete='CASCADE'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='unknown')
    
    practice = db.relationship('Practice', backref=db.backref('attendances', lazy='dynamic', cascade='all, delete-orphan'))
    member = db.relationship('Member', backref=db.backref('attendances', lazy='dynamic', cascade='all, delete-orphan'))
    
    __table_args__ = (db.UniqueConstraint('practice_id', 'member_id', name='_practice_member_uc'),)

    def __repr__(self):
        return f'<Attendance P:{self.practice_id} M:{self.member_id} Status:{self.status}>'

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    opponent = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    result = db.Column(db.String(50), nullable=True) 
    notes = db.Column(db.Text, nullable=True)
    own_score = db.Column(db.Integer, default=0)
    opponent_score = db.Column(db.Integer, default=0)
    duration_minutes = db.Column(db.Integer, default=90, nullable=False) 
    is_finished = db.Column(db.Boolean, default=False) # 試合終了フラグを追加

    def __repr__(self):
        return f'<Match {self.opponent} on {self.date.strftime("%Y-%m-%d")}>'

class Layout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id', ondelete='CASCADE'), nullable=True) 
    layout_name = db.Column(db.String(100), nullable=False)
    player_data = db.Column(db.Text, nullable=False) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    match = db.relationship('Match', backref=db.backref('layouts', cascade='all, delete-orphan')) 

    def __repr__(self):
        return f'<Layout {self.layout_name}>'
        
class MatchLineup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id', ondelete='CASCADE'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id', ondelete='CASCADE'), nullable=False)
    is_starter = db.Column(db.Boolean, default=True) 
    match = db.relationship('Match', backref=db.backref('lineups', cascade="all, delete-orphan"))
    member = db.relationship('Member') 
    __table_args__ = (db.UniqueConstraint('match_id', 'member_id', name='_match_member_uc'),)

    def __repr__(self):
        return f'<Lineup Match:{self.match_id} Member:{self.member_id}>'

class MatchGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id', ondelete='CASCADE'), nullable=False)
    team = db.Column(db.String(10), nullable=False) 
    time_period = db.Column(db.String(50), nullable=False) 
    time_minute = db.Column(db.Integer, nullable=False) 
    scorer_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=True)
    scorer = db.relationship('Member', foreign_keys=[scorer_id], backref=db.backref('goals_scored', lazy='dynamic'))
    assist_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=True)
    assister = db.relationship('Member', foreign_keys=[assist_id], backref=db.backref('goals_assisted', lazy='dynamic'))
    match = db.relationship('Match', backref=db.backref('goals', lazy='dynamic', cascade='all, delete-orphan')) 

    def __repr__(self):
        return f'<MatchGoal {self.id} - Match:{self.match_id} {self.team} at {self.time_period}{self.time_minute}min>'


# ----------------------------------------------------
# ユーティリティ関数
# ----------------------------------------------------

def calculate_absence_summary(start_date, end_date):
    """
    指定された期間の欠席集計をDBクエリで行う
    """
    # ログインチェックは /absence_summary ルートハンドラで行われているはずですが、関数内にも残します
    if not current_user.is_authenticated:
        return {'period': 'ログイン必須', 'total_absences': 0, 'members_data': []}

    user_id = current_user.id
    
    # datetime.combine() が必要です。Practice.dateがDatetime型の場合に必要
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    # 期間内の練習数をカウント
    total_practices_in_period = Practice.query.filter(
        Practice.user_id == user_id,
        Practice.date >= start_dt,
        Practice.date <= end_dt
    ).count()

    if total_practices_in_period == 0:
        return {
            'period': f'{start_date.strftime("%Y/%m/%d")} 〜 {end_date.strftime("%Y/%m/%d")}',
            'total_absences': 0,
            'members_data': []
        }

    # 期間内の Practice ID を取得
    practice_ids = [p.id for p in Practice.query.filter(
        Practice.user_id == user_id,
        Practice.date >= start_dt,
        Practice.date <= end_dt
    ).all()]

    # 期間内の欠席 (status == 'absent') を集計
    absence_counts = db.session.query(
        Attendance.member_id,
        func.count(Attendance.id).label('absences')
    ).filter(
        Attendance.practice_id.in_(practice_ids),
        Attendance.status == 'absent'
    ).group_by(Attendance.member_id).all()

    all_members = Member.query.filter_by(user_id=user_id).order_by(Member.number, Member.name).all()
    
    summary_members = []
    total_absences_sum = 0
    absence_map = {item.member_id: item.absences for item in absence_counts}

    for member in all_members:
        absences = absence_map.get(member.id, 0)
        present_count = total_practices_in_period - absences
        
        # 参加率を計算
        participation_rate = (present_count / total_practices_in_period) * 100 if total_practices_in_period > 0 else 0
        
        summary_members.append({
            'id': member.id,
            'name': member.name,
            'number': member.number,
            'absences': absences,
            'rate': f'{participation_rate:.0f}%' # 参加率 (Participation Rate)
        })
        total_absences_sum += absences
    
    return {
        'period': f'{start_date.strftime("%Y/%m/%d")} 〜 {end_date.strftime("%Y/%m/%d")}',
        'total_absences': total_absences_sum,
        'members_data': summary_members
    }

def get_interval_index(time_period, time_minute):
    try:
        minute = int(time_minute)
    except ValueError:
        return -1 
        
    if time_period in ['1H', '前半']:
        if 1 <= minute <= 45:
            return (minute - 1) // 5 # 5分刻み 0-8
        elif 46 <= minute <= 50:
             return 9 # 9 (前半AT)
            
    elif time_period in ['2H', '後半']:
        # 後半は45分から計算を始めるか、通算の46分から数えるか。ここでは通算の46分からを想定。
        if 46 <= minute <= 90:
            return 9 + (minute - 46) // 5 
        elif 91 <= minute <= 95:
             return 18 # 18 (後半AT)

    # 既存のロジック（10分刻み）
    if time_period in ['1H', '2H', '前半', '後半']:
        if 1 <= minute <= 90:
            return (minute - 1) // 10 
            
    elif time_period in ['1HAT', '前半AT']:
        return 9
        
    elif time_period in ['2HAT', '後半AT']:
        return 10
        
    return -1


# ----------------------------------------------------
# ルート定義
# ----------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', title='メインメニュー', current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        if not username:
            error = 'ユーザー名が必要です。'
        elif not password:
            error = 'パスワードが必要です。'
        elif db.session.execute(db.select(User).filter_by(username=username)).first() is not None:
            error = f'ユーザー {username} は既に登録されています。'
        if error is None:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('登録が完了しました。ログインしてください。', 'success')
            return redirect(url_for('login'))
        flash(error, 'danger')
    return render_template('register.html', title='ユーザー登録')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if user is None:
            error = 'ユーザー名またはパスワードが正しくありません。'
        elif not user.check_password(password):
            error = 'ユーザー名またはパスワードが正しくありません。'
        if error is None:
            login_user(user)
            flash('ログインに成功しました。', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash(error, 'danger')
        return render_template('login.html', title='ログイン')
    return render_template('login.html', title='ログイン')

@app.route('/logout')
@login_required 
def logout():
    logout_user()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('index'))

# ----------------------------------------------------
# メンバー管理
# ----------------------------------------------------

@app.route('/members', methods=['GET', 'POST'])
@login_required
def member_list():
    if request.method == 'POST':
        name = request.form['name']
        number = request.form['number']
        position = request.form['position']
        if not name:
            flash('選手名を入力してください。', 'danger')
        else:
            new_member = Member(user_id=current_user.id, name=name, number=number, position=position)
            db.session.add(new_member)
            db.session.commit()
            flash(f'{name}をメンバーに追加しました。', 'success')
        return redirect(url_for('member_list'))
    members = db.session.execute(db.select(Member).filter_by(user_id=current_user.id).order_by(Member.number)).scalars().all()
    return render_template('member_list.html', members=members, title='メンバーリスト')
    
@app.route('/members/edit/<int:member_id>', methods=['GET', 'POST'])
@login_required
def member_edit(member_id):
    member = db.session.get(Member, member_id)
    if member is None or member.user_id != current_user.id:
        flash('指定されたメンバーが見つからないか、編集する権限がありません。', 'danger')
        return redirect(url_for('member_list'))
    if request.method == 'POST':
        name = request.form['name']
        number = request.form['number']
        position = request.form['position']
        if not name:
            flash('選手名を入力してください。', 'danger')
            return render_template('member_edit.html', member=member, title='メンバー編集')
        try:
            member.name = name
            member.number = number
            member.position = position
            db.session.commit()
            flash(f'メンバー「{name}」の情報を更新しました。', 'success')
            return redirect(url_for('member_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新中にエラーが発生しました: {e}', 'danger')
    return render_template('member_edit.html', member=member, title='メンバー編集')

@app.route('/members/delete/<int:member_id>', methods=['POST'])
@login_required
def member_delete(member_id):
    member = db.session.get(Member, member_id)
    
    if member is None or member.user_id != current_user.id:
        flash('指定されたメンバーが見つからないか、削除する権限がありません。', 'danger')
        return redirect(url_for('member_list'))
        
    try:
        db.session.delete(member)
        db.session.commit()
        flash(f'メンバー「{member.name}」を削除しました。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'メンバーの削除中にエラーが発生しました。このメンバーが試合記録に紐づいている可能性があります: {e}', 'danger')
        
    return redirect(url_for('member_list'))
    
# ----------------------------------------------------
# 試合管理
# ----------------------------------------------------

@app.route('/matches')
@login_required
def match_list():
    search_query = request.args.get('search', '').strip()
    
    query = db.select(Match).filter_by(user_id=current_user.id)
    
    if search_query:
        query = query.filter(
            or_(
                Match.opponent.ilike(f'%{search_query}%'), 
                db.cast(Match.date, db.String).ilike(f'%{search_query}%') 
            )
        )
    
    query = query.order_by(Match.date.desc())
    
    matches = db.session.execute(query).scalars().all()
    
    return render_template('match_list.html', matches=matches, search_query=search_query, title='試合一覧')
    
@app.route('/match/info', methods=['GET', 'POST'])
@login_required
def match_info_create():
    if request.method == 'POST':
        opponent = request.form['opponent']
        date_str = request.form['date']
        result = request.form['result'] 
        notes = request.form['notes']
        duration_minutes_str = request.form.get('match_duration')
        
        try:
            match_date = datetime.strptime(date_str, '%Y-%m-%d')
            duration_minutes = int(duration_minutes_str) if duration_minutes_str else 90 
        except ValueError:
            flash('日付または試合時間の形式が正しくありません。', 'danger')
            return redirect(url_for('match_info_create'))

        if not opponent:
            flash('対戦相手は必須です。', 'danger')
            return redirect(url_for('match_info_create'))

        initial_result = result if result else '未確定'
        
        new_match = Match(
            user_id=current_user.id,
            opponent=opponent,
            date=match_date,
            result=initial_result, 
            notes=notes,
            own_score=0, 
            opponent_score=0, 
            duration_minutes=duration_minutes 
        )
        db.session.add(new_match)
        db.session.commit()
        flash(f'{opponent} との試合を記録しました。次はラインナップ登録へ。', 'success')
        
        return redirect(url_for('match_lineup_create', match_id=new_match.id))
        
    return render_template('match_info_create.html', title='試合情報作成')

@app.route('/match/lineup/<int:match_id>', methods=['GET', 'POST'])
@login_required
def match_lineup_create(match_id):
    match = db.session.get(Match, match_id)
    
    if match is None or match.user_id != current_user.id:
        flash('指定された試合にアクセスする権限がありません。', 'danger')
        return redirect(url_for('match_list'))
        
    members = db.session.execute(db.select(Member).filter_by(user_id=current_user.id)).scalars().all()

    if request.method == 'POST':
        starter_ids_str = request.form.get('starters_ids', '')
        sub_ids_str = request.form.get('subs_ids', '')

        starter_ids = [int(id.strip()) for id in starter_ids_str.split(',') if id.strip().isdigit()]
        sub_ids = [int(id.strip()) for id in sub_ids_str.split(',') if id.strip().isdigit()]

        db.session.execute(delete(MatchLineup).where(MatchLineup.match_id == match_id))

        for member_id in starter_ids:
            lineup = MatchLineup(match_id=match_id, member_id=member_id, is_starter=True)
            db.session.add(lineup)
        
        for member_id in sub_ids:
            lineup = MatchLineup(match_id=match_id, member_id=member_id, is_starter=False)
            db.session.add(lineup)
        
        db.session.commit()
        flash('ラインナップを登録しました。', 'success')
        return redirect(url_for('match_detail', match_id=match_id)) 
        
    return render_template('match_create.html', match=match, members=members, title=f'ラインナップ登録: {match.opponent}戦')

@app.route('/match/<int:match_id>')
@login_required
def match_detail(match_id):
    match = db.session.get(Match, match_id)
    
    if match is None or match.user_id != current_user.id:
        flash('指定された試合が見つからないか、アクセスする権限がありません。', 'danger')
        return redirect(url_for('match_list'))

    # 1. レイアウト取得 (変更なし)
    match_layouts = db.session.execute(
        db.select(Layout).filter_by(match_id=match_id).order_by(Layout.timestamp.desc())
    ).scalars().all()
    
    # 2. ラインナップメンバーの効率的な取得 (修正: メンバーを一度のクエリで取得)
    # MatchLineup.member リレーションシップが設定されている前提
    lineups_query = db.select(MatchLineup).filter_by(match_id=match_id).options(db.joinedload(MatchLineup.member))
    lineups = db.session.execute(lineups_query).scalars().all()

    starters = [lineup.member for lineup in lineups if lineup.is_starter]
    subs = [lineup.member for lineup in lineups if not lineup.is_starter]
    participating_members = starters + subs # 統計計算に使用

    # 3. ゴールイベントの取得 (✅ N+1クエリ解消の最大の修正点)
    # MatchGoal.scorer と MatchGoal.assister を同時にロード
    goals_query = db.select(MatchGoal).filter_by(match_id=match_id).order_by(MatchGoal.time_minute)
    
    # 💥 修正点: MatchGoal.assist を MatchGoal.assister に変更
    goals_query = goals_query.options(db.joinedload(MatchGoal.scorer), db.joinedload(MatchGoal.assister)) 
    
    goals = db.session.execute(goals_query).scalars().all()
    
    # 4. 全メンバーの取得 (変更なし、得点・アシストの選択肢用)
    all_members = db.session.execute(
        db.select(Member).filter_by(user_id=current_user.id).order_by(Member.number)
    ).scalars().all()

    # 以降の統計処理は変更なし
    member_stats = {}
    
    for member in all_members: 
        member_stats[member.id] = {
            'name': member.name,
            'number': member.number,
            'goals': 0,
            'assists': 0,
        }
    
    # participating_members を使って、ラインナップにいるメンバーの stats を初期化
    
    for goal in goals:
        if goal.team == 'OWN':
            if goal.scorer_id and goal.scorer_id in member_stats:
                member_stats[goal.scorer_id]['goals'] += 1
            if goal.assist_id and goal.assist_id in member_stats:
                member_stats[goal.assist_id]['assists'] += 1
        
    member_stats_list = []
    for member in participating_members:
        # participating_members から生成することで、ラインナップにいるメンバーに限定
        stat = member_stats.get(member.id, {'name': member.name, 'number': member.number, 'goals': 0, 'assists': 0})
        stat['name'] = member.name
        stat['number'] = member.number
        member_stats_list.append(stat)

    sorted_member_stats = sorted(member_stats_list, 
                                 key=lambda x: int(x['number']) if x['number'] and str(x['number']).isdigit() else 999)

    # タイムインターバル処理 (変更なし)
    NUM_INTERVALS = 11
    time_interval_data = {
        'own_goals': [0] * NUM_INTERVALS,
        'opponent_goals': [0] * NUM_INTERVALS
    }

    # get_interval_index 関数が利用可能であることを前提
    for goal in goals:
        index = get_interval_index(goal.time_period, goal.time_minute)
        
        if 0 <= index < NUM_INTERVALS:
            if goal.team == 'OWN':
                time_interval_data['own_goals'][index] += 1
            else:
                time_interval_data['opponent_goals'][index] += 1
    
    return render_template('match_detail.html', 
        match=match, 
        layouts=match_layouts, 
        starters=starters, 
        subs=subs, 
        goals=goals,
        all_members=all_members,
        member_stats=sorted_member_stats, 
        time_interval_data=time_interval_data, 
        title=f'{match.opponent}との試合詳細')


@app.route('/match/<int:match_id>/delete_goal/<int:goal_id>', methods=['POST'])
@login_required
def delete_goal(match_id, goal_id):
    match = Match.query.filter_by(id=match_id, user_id=current_user.id).first()
    if not match:
        flash('指定された試合にアクセスする権限がありません。', 'danger')
        return redirect(url_for('match_list'))

    goal = MatchGoal.query.get(goal_id) 
    if not goal or goal.match_id != match_id:
        flash('削除対象のゴールイベントが見つかりません。', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))

    db.session.delete(goal)
    db.session.commit()
    
    match.own_score = MatchGoal.query.filter_by(match_id=match_id, team='OWN').count()
    match.opponent_score = MatchGoal.query.filter_by(match_id=match_id, team='OPPONENT').count()
    
    own_goals = match.own_score
    opponent_goals = match.opponent_score
    
    # 試合終了フラグの更新は finish_match 関数に任せるか、スコア変更で自動更新するロジックを追加
    # 今回はシンプルにスコア再計算と結果文字列更新のみ行う
    
    if own_goals > opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 勝利'
    elif own_goals < opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 敗北'
    else:
        match.result = f'{own_goals}-{opponent_goals} 引き分け'

    db.session.commit()

    flash('✅ ゴールイベントを削除しました。スコアが更新されました。', 'success')
    return redirect(url_for('match_detail', match_id=match_id))

@app.route('/delete_match/<int:match_id>', methods=['POST'])
@login_required
def delete_match(match_id):
    match = Match.query.filter_by(id=match_id, user_id=current_user.id).first() 

    if not match:
        flash('指定された試合記録が見つからないか、削除する権限がありません。', 'danger')
        return redirect(url_for('match_list')) 

    try:
        db.session.delete(match)
        db.session.commit()
        flash(f'{match.opponent}戦 の試合記録を削除しました。', 'success')
        return redirect(url_for('match_list')) 
    except Exception as e:
        db.session.rollback()
        print(f"試合削除エラー: {e}")
        flash('試合記録の削除中にエラーが発生しました。', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))

@app.route('/match/<int:match_id>/finish', methods=['POST'])
@login_required
def finish_match(match_id):
    match = Match.query.filter_by(id=match_id, user_id=current_user.id).first()
    
    if not match:
        flash('指定された試合にアクセスする権限がありません。', 'danger')
        return redirect(url_for('match_list'))

    own_goals = MatchGoal.query.filter_by(match_id=match_id, team='OWN').count()
    opponent_goals = MatchGoal.query.filter_by(match_id=match_id, team='OPPONENT').count()
    
    match.own_score = own_goals
    match.opponent_score = opponent_goals
    match.is_finished = True
    
    if own_goals > opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 勝利'
    elif own_goals < opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 敗北'
    else:
        match.result = f'{own_goals}-{opponent_goals} 引き分け'

    db.session.commit()
    
    flash('✅ 試合を終了済みとしてマークしました。', 'success')
    return redirect(url_for('match_detail', match_id=match_id))

@app.route('/match/<int:match_id>/record_goal', methods=['POST'])
@login_required
def record_goal(match_id):
    match = db.session.get(Match, match_id)
    if match is None or match.user_id != current_user.id:
        flash('無効な試合です。', 'danger')
        return redirect(url_for('match_list'))

    team = request.form.get('team')
    time_period = request.form.get('time_period')
    time_minute = request.form.get('time_minute')
    scorer_id = request.form.get('scorer_id')
    assist_id = request.form.get('assist_id')

    if not all([team, time_period, time_minute]):
        flash('得点・失点の記録に必要な情報が不足しています。', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))

    try:
        time_minute = int(time_minute)
    except ValueError:
        flash('時間が不正な値です。', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))

    final_scorer_id = int(scorer_id) if scorer_id and scorer_id.isdigit() and team == 'OWN' and scorer_id != 'None' else None
    final_assist_id = int(assist_id) if assist_id and assist_id.isdigit() and team == 'OWN' and assist_id != 'None' else None
    
    if final_scorer_id and db.session.get(Member, final_scorer_id) is None: final_scorer_id = None
    if final_assist_id and db.session.get(Member, final_assist_id) is None: final_assist_id = None

    new_goal = MatchGoal(
        match_id=match_id,
        team=team,
        time_period=time_period,
        time_minute=time_minute,
        scorer_id=final_scorer_id,
        assist_id=final_assist_id,
    )

    db.session.add(new_goal)
    db.session.commit()
    
    own_goals = MatchGoal.query.filter_by(match_id=match_id, team='OWN').count()
    opponent_goals = MatchGoal.query.filter_by(match_id=match_id, team='OPPONENT').count()
    
    match.own_score = own_goals
    match.opponent_score = opponent_goals
    
    if own_goals > opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 勝利'
    elif own_goals < opponent_goals:
        match.result = f'{own_goals}-{opponent_goals} 敗北'
    else:
        match.result = f'{own_goals}-{opponent_goals} 引き分け'

    db.session.commit()

    flash(f'{match.opponent} 戦の試合記録に新しい得点/失点を記録しました。', 'success')
    return redirect(url_for('match_detail', match_id=match_id))

# ----------------------------------------------------
# 全体分析
# ----------------------------------------------------

@app.route('/analysis')
@login_required
def analysis_overview():
    all_matches = Match.query.filter_by(user_id=current_user.id).all()
    
    total_stats = {
        'wins': 0, 'losses': 0, 'draws': 0, 
        'goals_for': 0, 'goals_against': 0, 'goal_difference': 0
    }
    
    for match in all_matches:
        total_stats['goals_for'] += match.own_score
        total_stats['goals_against'] += match.opponent_score
        
        if match.own_score > match.opponent_score:
            total_stats['wins'] += 1
        elif match.own_score < match.opponent_score:
            total_stats['losses'] += 1
        else:
            total_stats['draws'] += 1
            
    total_stats['goal_difference'] = total_stats['goals_for'] - total_stats['goals_against']
    
    match_ids = [match.id for match in all_matches]

    if match_ids:
        all_goals = MatchGoal.query.filter(MatchGoal.match_id.in_(match_ids)).all()
    else:
        all_goals = []
    
    all_members = Member.query.filter_by(user_id=current_user.id).order_by(Member.number).all()

    total_member_stats = {
        member.id: {'name': member.name, 'number': member.number, 'goals': 0, 'assists': 0}
        for member in all_members
    }
    
    for goal in all_goals:
        if goal.team == 'OWN':
            if goal.scorer_id and goal.scorer_id in total_member_stats:
                total_member_stats[goal.scorer_id]['goals'] += 1
            if goal.assist_id and goal.assist_id in total_member_stats:
                total_member_stats[goal.assist_id]['assists'] += 1

    goal_ranking = sorted([
        stat for stat in total_member_stats.values() if stat['goals'] > 0], 
        key=lambda x: (x['goals'], x['assists']), reverse=True)

    assist_ranking = sorted([
        stat for stat in total_member_stats.values() if stat['assists'] > 0], 
        key=lambda x: (x['assists'], x['goals']), reverse=True)

    NUM_INTERVALS = 11 
    
    total_time_interval_data = {
        'own_goals': [0] * NUM_INTERVALS,
        'opponent_goals': [0] * NUM_INTERVALS
    }

    for goal in all_goals:
        index = get_interval_index(goal.time_period, goal.time_minute)
        
        if 0 <= index < NUM_INTERVALS: 
            if goal.team == 'OWN':
                total_time_interval_data['own_goals'][index] += 1
            else:
                total_time_interval_data['opponent_goals'][index] += 1
                
    return render_template('analysis.html', 
        total_goals_ranking=goal_ranking,
        total_assists_ranking=assist_ranking,
        total_time_interval_data=total_time_interval_data, 
        total_stats=total_stats,
        total_matches_count=len(all_matches),
        title='全体分析')

# ----------------------------------------------------
# 練習管理
# ----------------------------------------------------

@app.route('/practices')
@login_required
def practice_calendar():
    return render_template('practice_calendar.html', title='練習カレンダー')

@app.route('/practice/create', methods=['GET', 'POST'])
@login_required
def practice_create():
    if request.method == 'GET':
        selected_date_str = request.args.get('date')
        initial_date = None
        if selected_date_str:
             try:
                datetime.strptime(selected_date_str, '%Y-%m-%d')
                initial_date = selected_date_str
             except ValueError:
                flash('日付の形式が正しくありません。', 'danger')
                
        return render_template('practice_create.html', title='練習計画作成', initial_date=initial_date)
        
    if request.method == 'POST':
        title = request.form['title']
        date_str = request.form['date']
        time_str = request.form.get('time', '00:00') 
        location = request.form.get('location')
        menu = request.form.get('menu')
        notes = request.form.get('notes')
        
        try:
            practice_datetime = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        except ValueError:
            flash('日付または時刻の形式が不正です。', 'danger')
            return redirect(url_for('practice_create')) 

        if not title or not date_str:
            flash('タイトルと日付は必須です。', 'danger')
            return redirect(url_for('practice_create'))

        new_practice = Practice(
            user_id=current_user.id,
            title=title,
            date=practice_datetime,
            location=location,
            menu=menu,
            notes=notes
        )
        db.session.add(new_practice)
        db.session.commit()
        flash(f'練習 "{title}" を記録しました。', 'success')
        return redirect(url_for('practice_detail', practice_id=new_practice.id))
        
    return render_template('practice_create.html', title='練習計画作成')

@app.route('/practice/<int:practice_id>', methods=['GET', 'POST'])
@login_required
def practice_detail(practice_id):
    practice = db.session.get(Practice, practice_id)
    
    if practice is None or practice.user_id != current_user.id:
        flash('指定された練習記録にアクセスする権限がありません。', 'danger')
        return redirect(url_for('practice_calendar'))
        
    if request.method == 'POST':
        title = request.form['title']
        date_str = request.form['date']
        time_str = request.form.get('time', '00:00') 
        location = request.form.get('location')
        menu = request.form.get('menu')
        notes = request.form.get('notes')
        
        try:
            practice_datetime = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        except ValueError:
            flash('日付または時刻の形式が不正です。更新できませんでした。', 'danger')
            return redirect(url_for('practice_detail', practice_id=practice_id))

        if not title or not date_str:
            flash('タイトルと日付は必須です。更新できませんでした。', 'danger')
            return redirect(url_for('practice_detail', practice_id=practice_id))

        practice.title = title
        practice.date = practice_datetime
        practice.location = location
        practice.menu = menu
        practice.notes = notes
        
        db.session.commit()
        flash(f'練習日誌 "{title}" を更新しました。', 'success')
        return redirect(url_for('practice_detail', practice_id=practice_id))

    return render_template('practice_detail.html', practice=practice, title=f'練習日誌: {practice.title}')

@app.route('/practice/delete/<int:practice_id>', methods=['POST'])
@login_required
def practice_delete(practice_id):
    practice = db.session.get(Practice, practice_id)

    if practice is None or practice.user_id != current_user.id:
        flash('指定された練習記録が存在しないか、削除する権限がありません。', 'danger')
        return redirect(url_for('practice_calendar'))

    try:
        db.session.delete(practice)
        db.session.commit()
        flash('練習記録を削除しました。', 'success')
        return redirect(url_for('practice_calendar'))
    except Exception as e:
        db.session.rollback()
        flash(f'削除中にエラーが発生しました: {e}', 'danger')
        return redirect(url_for('practice_detail', practice_id=practice_id))

# ----------------------------------------------------
# 欠席/出欠管理
# ----------------------------------------------------

@app.route('/practice/attendance/<int:practice_id>', methods=['GET', 'POST'])
@login_required
def absence_management(practice_id): 
    practice = db.session.get(Practice, practice_id)

    if practice is None or practice.user_id != current_user.id:
        flash('指定された練習記録にアクセスする権限がありません。', 'danger')
        return redirect(url_for('practice_calendar'))

    all_members = Member.query.filter_by(user_id=current_user.id).order_by(Member.number, Member.name).all()
    
    existing_attendances = Attendance.query.filter_by(practice_id=practice_id).all()
    attendance_map = {att.member_id: att.status for att in existing_attendances}
    
    # --- 💡 欠席回数集計ロジック (全期間の欠席回数を取得) ---
    members_with_status = []
    
    for member in all_members:
        # 該当メンバーの、全期間における 'absent' のレコード数をカウント
        absence_count = db.session.query(Attendance).filter(
            Attendance.member_id == member.id,
            Attendance.status == 'absent'
        ).count()
        
        members_with_status.append({
            'id': member.id,
            'name': member.name,
            'number': member.number,
            'status': attendance_map.get(member.id, 'unknown'),
            'absence_count': absence_count # 👈 個別に取得した欠席回数
        })
    # -------------------------------------------------------------
        
    if request.method == 'POST':
        db.session.execute(delete(Attendance).where(Attendance.practice_id == practice_id))
        db.session.commit()

        # 新しい出欠情報を登録
        try:
            for member in all_members:
                status = request.form.get(f'status_{member.id}')
                
                if status in ['present', 'absent', 'late', 'unknown']: # late は 'unknown' として扱う
                    new_attendance = Attendance(
                        practice_id=practice_id,
                        member_id=member.id,
                        status=status
                    )
                    db.session.add(new_attendance)
            
            db.session.commit()
            flash('✅ 出欠情報を更新しました。', 'success')
            return redirect(url_for('practice_detail', practice_id=practice_id))
        except Exception as e:
            db.session.rollback()
            flash(f'出欠情報の更新中にエラーが発生しました: {e}', 'danger')
            return redirect(url_for('absence_management', practice_id=practice_id))


    return render_template('absence_management.html', 
                             practice_id=practice_id, 
                             members=members_with_status, 
                             practice=practice, # テンプレートで practice.title や practice.date を使うために追加
                             title=f'出欠管理: {practice.title}')

@app.route('/absence_summary', methods=['GET'])
@login_required
def absence_summary():
    today = datetime.now().date()
    default_end_date = today
    default_start_date = today - timedelta(days=90) # 過去3ヶ月

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else default_start_date
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else default_end_date
    except ValueError:
        flash('日付の形式が正しくありません。デフォルトの期間を使用します。', 'danger')
        start_date = default_start_date
        end_date = default_end_date
        
    summary_data = calculate_absence_summary(start_date, end_date)
    
    return render_template('absence_summary.html', 
                             summary=summary_data,
                             start_date=start_date.isoformat(),
                             end_date=end_date.isoformat(),
                             title='欠席状況の集計')

@app.route('/api/member/absences', methods=['GET'])
@login_required
def api_member_absences():
    member_id = request.args.get('member_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not member_id:
        return jsonify({"message": "member_idが指定されていません"}), 400

    try:
        # 日付文字列をdatetimeオブジェクトに変換
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        # データベースから、指定された期間内のメンバーの欠席記録を取得
        # ※ ここで AbsenceではなくAttendanceモデルを参照するように修正
        query = db.select(Attendance).filter(
            Attendance.member_id == member_id,
            Attendance.status == 'absent' # 欠席ステータスのみをフィルタ
        )
        
        if start_date:
            # Practice モデルと Attendance モデルを結合
            query = query.join(Practice).filter(Practice.date >= start_date)
        if end_date:
            query = query.join(Practice).filter(Practice.date <= end_date)
            
        # ユーザーがそのメンバーにアクセスする権限があるかどうかのチェック
        member_check = db.session.get(Member, member_id)
        if member_check is None or member_check.user_id != current_user.id:
             return jsonify({"message": "アクセス権限がありません"}), 403

        # 日付順にソートして取得
        absences_objects = db.session.execute(
            query.order_by(Practice.date.desc())
        ).scalars().all()
        
        # JSONレスポンス用にデータを整形
        absences_data = []
        for a in absences_objects:
            # 💡 Attendance モデルを通じて Practice モデルの date にアクセス
            absences_data.append({
                'date': a.practice.date.strftime('%Y-%m-%d'),
                'reason': '' 
            })

        return jsonify(absences_data)

    except Exception as e:
        print(f"欠席履歴取得エラー: {e}")
        return jsonify({"message": "欠席履歴の取得中にエラーが発生しました"}), 500

# ----------------------------------------------------
# APIエンドポイント (カレンダー、戦術ボード関連)
# ----------------------------------------------------

@app.route('/api/practices', methods=['GET'])
@login_required
def api_get_practices():
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
        end_date = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
    except:
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2099, 12, 31)

    practices = db.session.execute(
        db.select(Practice).filter_by(user_id=current_user.id)
                             .filter(Practice.date >= start_date)
                             .filter(Practice.date < end_date)
                             .order_by(Practice.date.asc())
    ).scalars().all()
    
    events = []
    for p in practices:
        events.append({
            'id': p.id,
            'title': p.title,
            'start': p.date.isoformat(), 
            'url': url_for('practice_detail', practice_id=p.id),
            'allDay': False if p.date.time() != datetime.min.time() else True,
            'color': 'green'
        })
        
    return jsonify(events)

@app.route('/api/layout/data', methods=['GET'])
@login_required
def get_layout_data():
    layout_id = request.args.get('layout_id', type=int)
    if not layout_id:
        return jsonify({"error": "Layout ID is required"}), 400

    layout = Layout.query.get(layout_id) 

    if layout and layout.user_id == current_user.id and layout.player_data:
        return jsonify(json.loads(layout.player_data)), 200
    
    return jsonify({"error": "Layout data not found or unauthorized"}), 404

@app.route('/api/layout/list', methods=['GET'])
@login_required
def get_layout_list_simplified():
    """
    保存された配置リストを返します。
    クエリパラメータ:
    - match_id: 指定された試合配置とテンプレートを返します。
    - match_idが指定されない場合は、テンプレート（match_id=None）のみを返します。
    """
    match_id = request.args.get('match_id', type=int)
    
    query_filters = [Layout.user_id == current_user.id]

    if match_id is not None:
        # match_idが指定されている場合: その試合の配置 OR テンプレートの両方を取得
        query_filters.append(or_(Layout.match_id == match_id, Layout.match_id == None))
    else:
        # match_idが指定されていない場合: テンプレートのみを取得
        query_filters.append(Layout.match_id == None)

    try:
        layouts = db.session.execute(
            db.select(Layout)
            .filter(*query_filters)
            .order_by(Layout.timestamp.desc()) # ★ Layoutモデルに timestamp カラムがあると想定
        ).scalars().all()
        
        layout_list = [{
            'id': l.id,
            'layout_name': l.layout_name,
            'match_id': l.match_id,
            # ここでは timestamp を使用して、JavaScriptで必要な 'created_at' キー名で返す
            'created_at': l.timestamp.strftime('%Y/%m/%d %H:%M') if l.timestamp else None
        } for l in layouts]
        
        return jsonify(layout_list), 200

    except Exception as e:
        print(f"配置リストの取得中にエラーが発生しました: {e}")
        return jsonify({'message': '配置リストの取得に失敗しました。', 'error': str(e)}), 500


@app.route('/tactics_board', defaults={'match_id': None}) 
@app.route('/tactics_board/<int:match_id>') 
@login_required
def tactics_board(match_id):
    all_members_objects = db.session.execute(
        db.select(Member)
        .filter_by(user_id=current_user.id)
        .order_by(Member.number)
    ).scalars().all()

    members = [
        {
            'id': m.id,
            'name': m.name,
            'number': m.number,
            # 必要に応じて他のフィールドも追加できます
        }
        for m in all_members_objects
    ]
    
    load_id = request.args.get('load_id', type=int) 
    
    match = None
    if match_id:
        match = db.session.get(Match, match_id)
        
        if match is None or match.user_id != current_user.id:
            flash('指定された試合にアクセスする権限がありません。', 'danger')
            return redirect(url_for('index'))
            
    # 2. 辞書のリストをテンプレートに渡す
    return render_template(
        'tactics_board.html', 
        members=members, # 辞書のリストになった members を渡す
        match_id=match_id, 
        match=match, 
        load_id=load_id, 
        title='戦術ボード'
    )
    
@app.route('/api/save_layout', methods=['POST'])
@login_required
def save_layout():
    data = request.json
    layout_name = data.get('layout_name')
    player_data_obj = data.get('layout_data')
    match_id = data.get('match_id', None) 

    if not layout_name or not player_data_obj:
        return jsonify({'message': '配置名または選手データが不足しています。'}), 400

    if match_id is not None:
        match = db.session.get(Match, match_id)
        if match is None or match.user_id != current_user.id:
            match_id = None
    
    try:
        player_data_json = json.dumps(player_data_obj) 
        
        new_layout = Layout(
            user_id=current_user.id,
            match_id=match_id,
            layout_name=layout_name,
            player_data=player_data_json 
        )

        db.session.add(new_layout)
        db.session.commit()
        
        message = f"配置 '{layout_name}' を{'試合配置' if match_id else 'テンプレート'}として保存しました。"
        return jsonify({'message': message, 'layout_id': new_layout.id}), 201

    except Exception as e:
        db.session.rollback()
        print(f"配置の保存中にエラーが発生しました: {e}")
        return jsonify({'message': f'配置の保存中にエラーが発生しました: {e}'}), 500

@app.route('/match/<int:match_id>/layout/delete/<int:layout_id>', methods=['POST'])
@login_required
def delete_layout(match_id, layout_id):
    layout = Layout.query.filter_by(id=layout_id, user_id=current_user.id, match_id=match_id).first()
    
    if not layout:
        flash('指定された試合配置が見つからないか、削除する権限がありません。', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))
        
    try:
        db.session.delete(layout)
        db.session.commit()
        flash(f"試合配置 '{layout.layout_name}' を削除しました。", 'success')
        return redirect(url_for('match_detail', match_id=match_id))
    except Exception as e:
        db.session.rollback()
        flash(f'配置の削除中にエラーが発生しました: {e}', 'danger')
        return redirect(url_for('match_detail', match_id=match_id))

@app.route('/layout/delete/<int:layout_id>', methods=['POST'])
@login_required
def delete_layout_template(layout_id):
    layout = Layout.query.filter_by(id=layout_id, user_id=current_user.id).first()

    if not layout:
        flash('指定された配置が見つからないか、削除する権限がありません。', 'danger')
        return redirect(url_for('tactics_board')) 

    try:
        db.session.delete(layout)
        db.session.commit()
        
        flash(f"配置 '{layout.layout_name}' を削除しました。", 'success')
        
        if layout.match_id:
            return redirect(url_for('match_detail', match_id=layout.match_id))
        else:
            return redirect(url_for('tactics_board'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'配置の削除中にエラーが発生しました: {e}', 'danger')
        
        if layout.match_id:
            return redirect(url_for('match_detail', match_id=layout.match_id))
        else:
            return redirect(url_for('tactics_board'))

# ... (他のインポート、app/db定義、モデル定義、ルート定義など) ...

# デプロイ時の初期化専用エンドポイント（注意: 実行後は必ず削除または保護してください）
@app.route('/initialize-db')
def initialize_database():
    if os.environ.get('RENDER') != 'true':
        # RENDER環境変数がない場合はセキュリティのため拒否
        return "Not authorized outside of Render environment.", 403
    
    try:
        db.create_all()
        # 初期の管理者ユーザーや必須データをここで作成することも可能
        return "Database tables created successfully!", 200
    except Exception as e:
        return f"Database initialization failed: {str(e)}", 500

if __name__ == '__main__':
    # 💡 修正点: ローカル開発環境でのみdb.create_all()を実行する
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)