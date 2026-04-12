"""
MiroFish Backend entrypoint
"""

import os
import sys

# Fix for Windows console encoding: set UTF-8 before any other imports
if sys.platform == 'win32':
    # Environment variable ensures Python uses UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # Reconfigure stdout/stderr streams to UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path so `from app import ...` works
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """Entry point"""
    # Validate configuration before starting Flask
    errors = Config.validate()
    if errors:
        from app.utils.locale import t
        print(t('backend.configError'))
        for err in errors:
            print(f"  - {err}")
        print(f"\n{t('backend.checkEnvConfig')}")
        sys.exit(1)

    # Create the Flask app
    app = create_app()

    # Runtime configuration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG

    # Start the server
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()
