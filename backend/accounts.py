from werkzeug.security import check_password_hash, generate_password_hash


def initialize_accounts(db, username, password):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_rides (
            owner_id INTEGER NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_id, date)
        );
        CREATE TABLE IF NOT EXISTS user_journals (
            owner_id INTEGER NOT NULL, date TEXT NOT NULL, payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_id, date)
        );
        CREATE TABLE IF NOT EXISTS user_ai_config (
            owner_id INTEGER PRIMARY KEY, base_url TEXT NOT NULL,
            api_key TEXT NOT NULL, model TEXT NOT NULL,
            story_schemes TEXT NOT NULL DEFAULT '{}'
        );
    """)
    db.execute("BEGIN IMMEDIATE")
    admin = db.execute("SELECT id, password_hash FROM users WHERE is_admin = 1").fetchone()
    if admin is None:
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            (username, generate_password_hash(password, method="pbkdf2:sha256:600000")),
        )
        admin = db.execute("SELECT id FROM users WHERE is_admin = 1").fetchone()
    elif not check_password_hash(admin[1], password):
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password, method="pbkdf2:sha256:600000"), admin[0]))
    admin_id = admin[0]
    for table in ("story_records", "story_tasks"):
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if "owner_id" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN owner_id INTEGER")
        db.execute(f"UPDATE {table} SET owner_id = ? WHERE owner_id IS NULL", (admin_id,))
    for old, new in (("rides", "user_rides"), ("ride_journals", "user_journals")):
        db.execute(
            f"INSERT OR IGNORE INTO {new} (owner_id, date, payload, updated_at) "
            f"SELECT ?, date, payload, updated_at FROM {old}", (admin_id,),
        )
    db.execute(
        "INSERT OR IGNORE INTO user_ai_config (owner_id, base_url, api_key, model, story_schemes) "
        "SELECT ?, base_url, api_key, model, story_schemes FROM ai_config", (admin_id,),
    )
    db.execute("CREATE INDEX IF NOT EXISTS story_records_owner ON story_records (owner_id)")
    db.execute("CREATE INDEX IF NOT EXISTS story_tasks_owner_date ON story_tasks (owner_id, date, status)")
