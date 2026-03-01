#!/bin/bash
# ============================================================
# HGVS Demo Setup Script
# Run this before recording your demo video
# ============================================================

cd "$(dirname "$0")"
source venv/bin/activate

echo ""
echo "============================================"
echo "  HGVS - Hand Gesture Voting System"
echo "  Demo Setup"
echo "============================================"
echo ""

# 1. Kill any existing server on port 8080
echo "[1/5] Clearing port 8080..."
lsof -ti:8080 | xargs kill -9 2>/dev/null
sleep 1
echo "  Done."
echo ""

# 2. Reset database and seed dummy voters + votes
echo "[2/5] Preparing database..."
python -c "
from db import init_db, get_db_connection
from datetime import datetime, timedelta
import random

init_db()

conn = get_db_connection()

# Clear existing votes and reset voter status
conn.execute('UPDATE voters SET has_voted = 0')
conn.execute('DELETE FROM votes')

# Remove old dummy voters (keep real registered voters with photos)
conn.execute(\"DELETE FROM voters WHERE voter_id LIKE 'DV%'\")

# Add dummy voters to make the database look populated
# These are marked as already voted so they don't interfere with face auth
dummy_voters = [
    ('DV001', 'Rajesh Kumar'),
    ('DV002', 'Priya Sharma'),
    ('DV003', 'Amit Patel'),
    ('DV004', 'Sneha Reddy'),
    ('DV005', 'Vikram Singh'),
    ('DV006', 'Ananya Iyer'),
    ('DV007', 'Karthik Nair'),
    ('DV008', 'Meera Joshi'),
    ('DV009', 'Arjun Menon'),
]

for vid, name in dummy_voters:
    conn.execute(
        'INSERT OR IGNORE INTO voters (voter_id, name, photo_path, has_voted) VALUES (?, ?, ?, 1)',
        (vid, name, 'voter_data/dummy.jpg', )
    )

# Seed 99 votes per party (spread over past few hours for realism)
parties = ['BJP', 'ADMK', 'DMK', 'Congress', 'TDP']
base_time = datetime.now() - timedelta(hours=3)
for party in parties:
    for i in range(99):
        ts = base_time + timedelta(seconds=random.randint(0, 10800))
        conn.execute(
            'INSERT INTO votes (party, timestamp) VALUES (?, ?)',
            (party, ts.isoformat())
        )

conn.commit()
conn.close()
print('  Database ready. 99 votes seeded per party.')
"
echo ""

# 3. Show registered voters
echo "[3/5] Registered Voters:"
python register_voter.py list
echo ""

# 4. Show current vote counts
echo "[4/5] Current Vote Counts:"
python register_voter.py results
echo ""

# 5. Start server
echo "[5/5] Starting HGVS server..."
echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Open: http://localhost:8080"
echo "============================================"
echo ""
echo "  After voting, run:"
echo "    python register_voter.py results"
echo "  to see the updated counts."
echo ""

python main.py
