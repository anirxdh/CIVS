"""
Voter Registration CLI Tool
Usage:
    python register_voter.py --id VOTER001 --name "Anirudh" --photo /path/to/aadhar.jpg
"""
import argparse
import shutil
import os
import sys

from db import init_db, get_db_connection, get_voter_by_id

VOTER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voter_data")


def register_voter(voter_id, name, photo_src):
    os.makedirs(VOTER_DATA_DIR, exist_ok=True)

    if not os.path.exists(photo_src):
        print(f"ERROR: Photo file not found: {photo_src}")
        sys.exit(1)

    existing = get_voter_by_id(voter_id)
    if existing:
        print(f"ERROR: Voter ID '{voter_id}' is already registered as '{existing['name']}'.")
        sys.exit(1)

    ext = os.path.splitext(photo_src)[1] or ".jpg"
    dest = os.path.join(VOTER_DATA_DIR, f"{voter_id}{ext}")
    shutil.copy2(photo_src, dest)

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO voters (voter_id, name, photo_path, has_voted) VALUES (?, ?, ?, 0)",
        (voter_id, name, os.path.abspath(dest)),
    )
    conn.commit()
    conn.close()

    print(f"Voter registered successfully:")
    print(f"  ID:    {voter_id}")
    print(f"  Name:  {name}")
    print(f"  Photo: {dest}")


def list_voters():
    from db import get_all_voters
    voters = get_all_voters()
    if not voters:
        print("No voters registered.")
        return
    print(f"\n  {'Voter ID':<15} {'Status'}")
    print("  " + "-" * 30)
    for v in voters:
        status = "Voted" if v["has_voted"] else "Not Voted"
        print(f"  {v['voter_id']:<15} {status}")
    print(f"\n  Total registered voters: {len(voters)}")


def show_results():
    from db import get_vote_counts
    counts = get_vote_counts()
    total = sum(counts.values())
    if not counts:
        print("No votes recorded yet.")
        return
    print(f"\n  {'Party':<20} {'Votes':>8}   {'Percentage':>10}")
    print("  " + "-" * 45)
    for party, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = (count / total * 100) if total > 0 else 0
        bar = "#" * int(pct / 5)
        print(f"  {party:<20} {count:>8}   {pct:>5.1f}%  {bar}")
    print("  " + "-" * 45)
    print(f"  {'Total':<20} {total:>8}")
    print("\n  Note: Votes are anonymous -- no voter-to-vote mapping exists.")


def reset_votes():
    conn = get_db_connection()
    conn.execute("UPDATE voters SET has_voted = 0")
    conn.execute("DELETE FROM votes")
    conn.commit()
    conn.close()
    print("All votes have been reset. Voters can vote again.")


if __name__ == "__main__":
    init_db()

    parser = argparse.ArgumentParser(description="HGVS Voter Registration Tool")
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="Register a new voter")
    reg.add_argument("--id", required=True, help="Voter ID (e.g., VOTER001)")
    reg.add_argument("--name", required=True, help="Voter's full name")
    reg.add_argument("--photo", required=True, help="Path to ID photo (Aadhar card, etc.)")

    sub.add_parser("list", help="List all registered voters")
    sub.add_parser("results", help="Show anonymous vote counts")
    sub.add_parser("reset", help="Reset all votes (admin only)")

    args = parser.parse_args()

    if args.command == "register":
        register_voter(args.id, args.name, args.photo)
    elif args.command == "list":
        list_voters()
    elif args.command == "results":
        show_results()
    elif args.command == "reset":
        reset_votes()
    else:
        parser.print_help()
