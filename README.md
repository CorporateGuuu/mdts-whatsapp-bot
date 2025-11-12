# Midas Tech WhatsApp Bot

A sophisticated WhatsApp business bot for managing LCD screen repair jobs with technician assignment and comprehensive job tracking.

## Features

- **Media-First Intake**: Send photos to start job intake process
- **Command Interface**: `/help`, `/new`, `/assign`, `/total`, `/status`, `/tz`
- **Job Lifecycle Management**: intake → open → assigned → done/canceled
- **Technician Assignment**: Assign jobs to technicians (TechA, TechB)
- **Time Zone Support**: Localized timestamps for global operations
- **PostgreSQL Database**: Full job and technician tracking

## Quick Start

```bash
# Set up virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up database (requires PostgreSQL)
psql "$DATABASE_URL" -f schema.sql

# Run the bot (development)
export FLASK_APP=app.py
flask run --host 0.0.0.0 --port 5000
```

## Environment Variables

Create a `.env` file with:

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+1415XXXXXXX  # your Twilio WhatsApp-enabled number

# Flask
FLASK_ENV=production
SECRET_KEY=change-me

# Postgres
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/whatsappbot

# Business
DEFAULT_TZ=America/New_York         # your "home" timezone label for formatting
TECH_LABOR_USD=50                   # per-screen labor

# AWS S3 (for media)
AWS_ACCESS_KEY_ID=AKIAXXXXX
AWS_SECRET_ACCESS_KEY=XXXXXXXXXXXXXXXXXXXX
AWS_REGION=us-east-1
S3_BUCKET=your-media-bucket
S3_PREFIX=whatsapp-intake/
```

## Commands

- `/help` - Show all available commands
- `/setcity <city>` - Set timezone for timestamps (e.g., `/setcity Dubai`)
- `/assign <job_id> <techname>` - Assign job to technician (auto-notifies tech)
- `/total <job_id>` - Show detailed job totals with breakdown

## Workflow

1. **Send Photo** → Bot creates job and prompts for items
2. **Add Items** → Reply with `model, qty, unit_price` (e.g., `14 Pro, 4, 170`)
3. **Get Totals** → Use `/total <job_id>` for detailed breakdown
4. **Assign Work** → Use `/assign <job_id> Tech-A` (technician gets notified automatically)

## Database Schema

- `technicians` table: id, name, wa_number
- `jobs` table: id, customer_wa, photo_url, city, status, assigned_to, created_at
- `job_items` table: id, job_id, model, qty, unit_price

## API Endpoints

- `GET /` - Health check
- `POST /whatsapp` - WhatsApp webhook handler

## Development Setup

For local development and testing with Twilio:

```bash
# 1. Environment setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql

# 2. Run Flask app
export FLASK_APP=app.py
flask run --host 0.0.0.0 --port 5000

# 3. Expose with ngrok (separate terminal)
# Install ngrok: https://ngrok.com/download
ngrok http 5000

# 4. Configure Twilio webhook to ngrok URL
# Set your Twilio WhatsApp webhook to:
# https://<your-ngrok-id>.ngrok.io/whatsapp  (HTTP POST)
```

## Deployment

The bot is designed to run on any platform that supports Python and PostgreSQL. For production deployment:

1. Set up PostgreSQL database
2. Configure environment variables
3. Run schema.sql to initialize database
4. Deploy the Flask app behind a WSGI server (gunicorn, uwsgi)
5. Configure Twilio WhatsApp webhook to point to your `/whatsapp` endpoint
