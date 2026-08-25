"""
One-time migration script: SQLite -> Firestore.
Reads all records from database/flashcards.db and writes them into Firestore collections.
Idempotent: uses existing integer SQLite IDs as document IDs in Firestore so re-running overwrites.
"""

import os
import sqlite3
from google.cloud import firestore

def migrate():
    db_path = os.path.join("database", "flashcards.db")
    if not os.path.exists(db_path):
        print(f"No SQLite database found at {db_path}. Skipping migration.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    firestore_client = firestore.Client()

    tables = ["users", "decks", "cards", "study_sessions", "mock_exams", "exam_questions"]
    counts = {}

    print("Starting migration from SQLite to Firestore...")

    for table in tables:
        # Check if table exists in SQLite
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cur.fetchone():
            counts[table] = 0
            continue

        cur = conn.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in cur.fetchall()]
        counts[table] = len(rows)

        collection_ref = firestore_client.collection(table)
        
        # Batch write in chunks of 400 documents (Firestore batch limit is 500)
        chunk_size = 400
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            batch = firestore_client.batch()
            for doc_dict in chunk:
                doc_id = str(doc_dict["id"])
                doc_ref = collection_ref.document(doc_id)
                batch.set(doc_ref, doc_dict)
            batch.commit()

        print(f"  - Collection '{table}': {len(rows)} documents migrated.")

    conn.close()
    print("\nMigration Complete Summary:")
    for table, count in counts.items():
        print(f"  {table}: {count} records")

if __name__ == "__main__":
    migrate()
