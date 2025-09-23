#!/usr/bin/env python3
"""
Run script for Edu-Sync AI
"""

import os
import sys
from app import app, create_tables

def main():
    """Main function to run the application"""
    print("🚀 Starting Edu-Sync AI...")
    print("📊 Initializing database...")
    
    with app.app_context():
        create_tables()
        print("✅ Database initialized successfully!")
    
    print("🌐 Starting web server...")
    print("📱 Application will be available at: http://localhost:5000")
    print("👤 Default admin credentials: admin / admin123")
    print("🔧 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        app.run(
            debug=True,
            host='0.0.0.0',
            port=5000,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()