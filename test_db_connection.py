"""Test database connection"""
from ResumAi import create_app
from ResumAi.extensions import db

def test_connection():
    try:
        app = create_app()
        print("✓ App created successfully")
        
        with app.app_context():
            # Try to connect to the database
            db.engine.connect()
            print("✓ Database connection successful!")
            
            # Get database info
            result = db.session.execute(db.text("SELECT version()"))
            version = result.scalar()
            print(f"✓ PostgreSQL version: {version}")
            
            # List all tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"✓ Tables found: {tables if tables else 'No tables yet'}")
            
    except Exception as e:
        print(f"✗ Database connection failed!")
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_connection()
