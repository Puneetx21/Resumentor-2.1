"""Test authentication setup"""
from ResumAi import create_app
from ResumAi.models import User
from ResumAi.extensions import db

app = create_app()

with app.app_context():
    # Check if user exists
    user = User.query.filter_by(email='punitchauhan2103@gmail.com').first()
    
    if user:
        print(f"✓ User found: {user.name} ({user.email})")
        print(f"  ID: {user.id}")
        print(f"  Google ID: {user.google_id}")
        print(f"  Role: {user.role}")
        print(f"  Has is_authenticated: {hasattr(user, 'is_authenticated')}")
        print(f"  is_authenticated value: {user.is_authenticated}")
        print(f"  Get ID: {user.get_id()}")
    else:
        print("✗ User not found")
        
    # List all users
    all_users = User.query.all()
    print(f"\n✓ Total users in database: {len(all_users)}")
    for u in all_users:
        print(f"  - {u.name} ({u.email})")
