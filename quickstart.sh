#!/bin/bash
# Quick Start Script for macOS/Linux
# Run: bash quickstart.sh

echo "============================================================"
echo "Fraud Analytics Platform - Quick Start"
echo "============================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv venv

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Installing dependencies..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo ""
echo "Configuration..."
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please update .env with your configuration before running the app"
else
    echo ".env file already exists"
fi

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "1. Update .env with your configuration (database, API keys, etc.)"
echo "2. Run the application:"
echo "   python -m uvicorn app.main:app --reload"
echo "3. Open http://localhost:8000 in your browser"
echo "4. API documentation: http://localhost:8000/docs"
echo ""
echo "For more information, see README.md"
echo "============================================================"
