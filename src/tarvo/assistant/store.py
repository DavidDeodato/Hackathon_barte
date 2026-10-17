from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from tarvo.storage.sqlite import utc_now


class AssistantError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)


class ConversationStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,context TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,request_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL, UNIQUE(conversation_id,request_id));
              CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,data TEXT NOT NULL,status TEXT NOT NULL,result TEXT);
              CREATE INDEX IF NOT EXISTS conversation_messages ON messages(conversation_id,created_at);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, context):
        identifier, now = 'chat-' + uuid4().hex, utc_now()
        with self.db() as db:
            db.execute('INSERT INTO conversations VALUES (?,?,?,?,?)', (identifier, 'Nova conversa', json.dumps(context), now, now))
        return self.get(identifier)

    def list(self):
        with self.db() as db:
            rows = db.execute('SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 100').fetchall()
        return [{**dict(r), 'context': json.loads(r['context'])} for r in rows]

    def get(self, identifier):
        with self.db() as db:
            row = db.execute('SELECT * FROM conversations WHERE id=?', (identifier,)).fetchone()
            if row is None:
                raise AssistantError('CONVERSATION_NOT_FOUND', 'Conversa não encontrada.', 404)
            messages = [json.loads(r['data']) for r in db.execute('SELECT data FROM messages WHERE conversation_id=? ORDER BY created_at,rowid', (identifier,))]
            actions = {r['id']: dict(status=r['status'], result=json.loads(r['result']) if r['result'] else None) for r in db.execute('SELECT * FROM actions WHERE conversation_id=?', (identifier,))}
        for message in messages:
            for action in message.get('actions', []):
                action.update(actions.get(action['id'], {}))
        return {**dict(row), 'context': json.loads(row['context']), 'messages': messages, 'scope': 'workspace_tarvo'}

    def add(self, conversation, request_id, data):
        data = dict(id='msg-' + uuid4().hex, created_at=utc_now(), **data)
        with self.db() as db:
            db.execute('INSERT INTO messages VALUES (?,?,?,?,?)', (data['id'], conversation, request_id, json.dumps(data, ensure_ascii=False), data['created_at']))
            db.execute('UPDATE conversations SET updated_at=? WHERE id=?', (data['created_at'], conversation))
            if data['role'] == 'user':
                db.execute("UPDATE conversations SET title=? WHERE id=? AND title='Nova conversa'", (data['content'][:70], conversation))
        return data

    def has_request(self, conversation, request_id):
        with self.db() as db:
            return db.execute('SELECT 1 FROM messages WHERE conversation_id=? AND request_id=?', (conversation, request_id)).fetchone() is not None

    def action(self, conversation, data):
        data = dict(id='action-' + uuid4().hex, status='proposed', **data)
        with self.db() as db:
            db.execute('INSERT INTO actions VALUES (?,?,?,?,NULL)', (data['id'], conversation, json.dumps(data), 'proposed'))
        return data

    def execute(self, conversation, identifier, callback):
        # Serialize across processes. A crash after dispatch leaves executing,
        # never an automatic second close. The operator can inspect /api/runs.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM actions WHERE id=? AND conversation_id=?', (identifier, conversation)).fetchone()
            if row is None:
                raise AssistantError('ACTION_NOT_FOUND', 'Ação não encontrada.', 404)
            if row['status'] == 'completed':
                return json.loads(row['result'])
            if row['status'] != 'proposed':
                raise AssistantError('ACTION_ALREADY_SENT', 'Ação já enviada. Consulte as execuções antes de criar outra.')
            db.execute("UPDATE actions SET status='executing' WHERE id=?", (identifier,))
            data = json.loads(row['data'])
        try:
            result = callback(data)
        except Exception:
            with self.db() as db:
                db.execute("UPDATE actions SET status='failed' WHERE id=?", (identifier,))
            raise
        with self.db() as db:
            db.execute("UPDATE actions SET status='completed',result=? WHERE id=?", (json.dumps(result), identifier))
        return result
