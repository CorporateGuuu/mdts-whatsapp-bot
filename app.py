import os
import re
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from sqlalchemy import (create_engine, Column, Integer, String, DateTime, Float,
                        ForeignKey, Boolean, Text)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

import boto3

# --- ENV ---
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_NUMBER")  # 'whatsapp:+1...'
DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g. postgres://user:pass@host/db
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Asia/Dubai")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Labor cost (USD) per screen
LABOR_PER_SCREEN = float(os.getenv("LABOR_PER_SCREEN", "50"))

# --- Twilio & Flask ---
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = Flask(__name__)

# --- DB setup ---
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Technician(Base):
    __tablename__ = "technicians"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    whatsapp = Column(String(40), nullable=False)  # 'whatsapp:+1...'
    active = Column(Boolean, default=True)

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True)
    model = Column(String(80), unique=True, nullable=False)  # e.g. '14pro', '14promax'
    unit_price = Column(Float, nullable=False)
    cable_adder = Column(Float, default=0.0)  # add-on if cable included

class UserPref(Base):
    __tablename__ = "user_prefs"
    id = Column(Integer, primary_key=True)
    phone = Column(String(40), unique=True, nullable=False)  # sender line
    tz = Column(String(80), default=DEFAULT_TZ)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    customer_phone = Column(String(40))   # who submitted intake
    model = Column(String(80))
    qty = Column(Integer, default=1)
    include_cable = Column(Boolean, default=False)
    notes = Column(Text)
    photo_url = Column(Text)     # original (twilio) or S3 url
    s3_key = Column(String(255)) # if uploaded
    status = Column(String(40), default="draft")  # draft|open|assigned|in_progress|done|issue|canceled
    intake_step = Column(Integer, default=0)      # 0 none, 1 ask model, 2 ask qty, 3 cable?, 4 notes
    assigned_to_id = Column(Integer, ForeignKey("technicians.id"), nullable=True)
    assigned_to = relationship("Technician")

# Create tables if missing
Base.metadata.create_all(engine)

# --- S3 ---
s3 = boto3.client("s3", region_name=AWS_REGION) if AWS_S3_BUCKET else None

# --- Helpers ---
MODEL_ALIASES = {
    # normalize user text -> price.model keys
    "14pro": "14pro",
    "14 pro": "14pro",
    "14promax": "14promax",
    "14 pro max": "14promax",
    "13 pro max": "13promax",
    "13promax": "13promax",
    "15 pro max": "15promax",
    "15promax": "15promax",
    "12 pro max": "12promax",
    "12promax": "12promax",
    "15 pro": "15pro",
    "15pro": "15pro",
    "16 pro": "16pro",
    "16 pro max": "16promax",
}

CMD_PATTERNS = {
    "assign": re.compile(r"^/assign\s+(\d+)\s+(.+)$", re.I),
    "total":  re.compile(r"^/total\s+(\d+)$", re.I),
    "tz":     re.compile(r"^/tz\s+([A-Za-z_]+/[A-Za-z_]+)$"),
    "price":  re.compile(r"^/price\s+(.+)$", re.I),
    "setprice": re.compile(r"^/setprice\s+(.+?)\s+(\d+(\.\d+)?)\s*(\+(\d+(\.\d+)?))?$", re.I),
    "dispatch": re.compile(r"^/dispatch\s+(\d+)\s*(.*)$", re.I),
    "accept": re.compile(r"^/accept\s+(\d+)$", re.I),
    "done": re.compile(r"^/done\s+(\d+)$", re.I),
    "issue": re.compile(r"^/issue\s+(\d+)\s*(.*)$", re.I),
    "status": re.compile(r"^/status\s+(\d+)$", re.I),
    "cancel": re.compile(r"^/cancel$", re.I),
}

def normalize_model(m: str) -> str | None:
    if not m:
        return None
    key = re.sub(r"\s+", " ", m.strip().lower())
    return MODEL_ALIASES.get(key)

def get_tz_for(phone: str) -> ZoneInfo:
    db = SessionLocal()
    try:
        pref = db.query(UserPref).filter_by(phone=phone).first()
        return ZoneInfo(pref.tz if pref and pref.tz else DEFAULT_TZ)
    finally:
        db.close()

def fmt_now_for(phone: str) -> str:
    tz = get_tz_for(phone)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")

def upload_to_s3_from_twilio(media_url: str, job_id: int) -> str:
    """Downloads Twilio media with auth and uploads to S3. Returns s3 url."""
    if not s3:
        return media_url  # fallback
    # Twilio media URLs require basic auth
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, media_url, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    opener = urllib.request.build_opener(handler)
    r = opener.open(media_url, timeout=30)
    if r.status != 200:
        raise Exception(f"HTTP {r.status}")
    key = f"jobs/{job_id}/{os.path.basename(media_url.split('?')[0])}"
    s3.upload_fileobj(r, AWS_S3_BUCKET, key, ExtraArgs={"ACL": "private", "ContentType": r.headers.get("Content-Type", "application/octet-stream")})
    return f"s3://{AWS_S3_BUCKET}/{key}"

def calc_total(db, job: Job) -> tuple[float, float, float]:
    """Returns (unit_price_with_adder, labor_total, grand_total)"""
    norm = normalize_model(job.model or "")
    pr = db.query(Price).filter_by(model=norm).first() if norm else None
    unit = pr.unit_price if pr else 0.0
    adder = pr.cable_adder if (pr and job.include_cable) else 0.0
    unit_with_adder = unit + adder
    labor = (job.qty or 0) * LABOR_PER_SCREEN
    grand = (job.qty or 0) * unit_with_adder + labor
    return (unit_with_adder, labor, grand)

def sms(to_whatsapp: str, body: str, media_url: str | None = None):
    kwargs = {"from_": TWILIO_WHATSAPP_FROM, "to": to_whatsapp, "body": body}
    if media_url:
        kwargs["media_url"] = [media_url]
    client.messages.create(**kwargs)

# --- WhatsApp webhook ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    # Validate Twilio request signature for security
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    twilio_signature = request.headers.get('X-Twilio-Signature', '')
    request_url = request.url
    request_data = request.form.to_dict()

    if not validator.validate(request_url, request_data, twilio_signature):
        print("Invalid Twilio signature - rejecting request")
        return Response(status=403)  # Reject invalid requests

    sender = request.values.get("From")          # 'whatsapp:+1...'
    body = (request.values.get("Body") or "").strip()
    num_media = int(request.values.get("NumMedia") or 0)

    db = SessionLocal()
    resp = MessagingResponse()
    msg = resp.message()

    try:
        # Update technician WhatsApp number if they have a placeholder
        placeholder_techs = db.query(Technician).filter(Technician.whatsapp.like("pending_%@temp.com")).all()
        for tech in placeholder_techs:
            if tech.whatsapp.startswith("pending_"):
                tech.whatsapp = sender
                db.commit()
                print(f"Updated technician {tech.name} WhatsApp to {sender}")
                break  # Only update one technician per message

        # 1) Commands
        # /tz <Area/City>
        m = CMD_PATTERNS["tz"].match(body)
        if m:
            tz_str = m.group(1)
            try:
                _ = ZoneInfo(tz_str)
            except Exception:
                msg.body("❌ Invalid timezone. Example: /tz Asia/Dubai or /tz America/New_York")
                return str(resp)
            pref = db.query(UserPref).filter_by(phone=sender).first()
            if not pref:
                pref = UserPref(phone=sender, tz=tz_str)
                db.add(pref)
            else:
                pref.tz = tz_str
            db.commit()
            msg.body(f"✅ Timezone set to *{tz_str}*. Current local time: {fmt_now_for(sender)}")
            return str(resp)

        # /assign <job_id> <techname>
        m = CMD_PATTERNS["assign"].match(body)
        if m:
            job_id = int(m.group(1))
            techname = m.group(2).strip()
            job = db.query(Job).get(job_id)
            if not job:
                msg.body("❌ Job not found.")
                return str(resp)
            tech = db.query(Technician).filter(Technician.name.ilike(techname)).first()
            if not tech:
                # Auto-register new technician with placeholder WhatsApp number
                # This will be updated when they first respond to a notification
                tech = Technician(name=techname, whatsapp=f"pending_{techname.lower().replace(' ', '_')}@temp.com")
                db.add(tech)
                db.commit()
                msg.body(f"⚠️ New technician *{tech.name}* auto-registered. They will be notified when they respond to messages.\n\n✅ Assigned job #{job.id} to *{tech.name}*.")
                return str(resp)
            job.assigned_to = tech
            job.status = "assigned"
            db.commit()

            # Notify technician automatically
            try:
                sms(tech.whatsapp, f"🔔 New assignment #{job.id}\nModel: {job.model}\nQty: {job.qty}\nNotes: {job.notes or '-'}\n\nCommands: /accept {job.id}, /done {job.id}, /issue {job.id} <note>")
            except Exception as e:
                print("Tech notify error:", e)

            msg.body(f"✅ Assigned job #{job.id} to *{tech.name}* and notified them.")
            return str(resp)

        # /total <job_id>
        m = CMD_PATTERNS["total"].match(body)
        if m:
            job_id = int(m.group(1))
            job = db.query(Job).get(job_id)
            if not job:
                msg.body("❌ Job not found.")
                return str(resp)
            unit_with_adder, labor, grand = calc_total(db, job)
            msg.body(
                f"🧮 Total for job #{job.id}\n"
                f"Model: {job.model} | Qty: {job.qty}\n"
                f"Unit (incl. cable if any): ${unit_with_adder:.2f}\n"
                f"Labor (${LABOR_PER_SCREEN:.0f} × {job.qty}): ${labor:.2f}\n"
                f"—\nGrand Total: *${grand:.2f}*"
            )
            return str(resp)

        # /price <model>
        m = CMD_PATTERNS["price"].match(body)
        if m:
            model_in = m.group(1).strip()
            norm = normalize_model(model_in)
            if not norm:
                msg.body("❌ Unknown model. Try: 14pro, 14promax, 13promax, 15promax, 12promax, 15pro, 16pro, 16promax.")
                return str(resp)
            pr = db.query(Price).filter_by(model=norm).first()
            if not pr:
                msg.body("No price set yet for that model.")
                return str(resp)
            msg.body(f"📘 Price for *{norm}*: ${pr.unit_price:.2f} (+${pr.cable_adder:.2f} with cable)")
            return str(resp)

        # /setprice <model> <price> +<cable_adder>
        m = CMD_PATTERNS["setprice"].match(body)
        if m:
            model_in = m.group(1).strip()
            price = float(m.group(2))
            cable_adder = float(m.group(5)) if m.group(5) else 0.0
            norm = normalize_model(model_in)
            if not norm:
                msg.body("❌ Unknown model alias.")
                return str(resp)
            pr = db.query(Price).filter_by(model=norm).first()
            if not pr:
                pr = Price(model=norm, unit_price=price, cable_adder=cable_adder)
                db.add(pr)
            else:
                pr.unit_price = price
                pr.cable_adder = cable_adder
            db.commit()
            msg.body(f"✅ Set *{norm}* = ${price:.2f} (+${cable_adder:.2f} with cable).")
            return str(resp)

        # /dispatch <job_id> [pickup note]
        m = CMD_PATTERNS["dispatch"].match(body)
        if m:
            job_id = int(m.group(1))
            note = m.group(2).strip() if m.group(2) else ""
            job = db.query(Job).get(job_id)
            if not job:
                msg.body("❌ Job not found.")
                return str(resp)

            # Stub: call your courier APIs here (Uber Direct / Lalamove)
            # Example:
            # courier_id = create_courier_job(api_key, pickup_addr, dropoff_addr, note=note)
            # For now, we just acknowledge:
            msg.body(f"🚚 Dispatch requested for job #{job.id}. Note: {note or '-'}\n(Integrate Uber/Lalamove API in this endpoint.)")
            return str(resp)

        # /accept <job_id>
        m = CMD_PATTERNS["accept"].match(body)
        if m:
            job_id = int(m.group(1))
            job = db.query(Job).get(job_id)
            if not job or job.assigned_to.whatsapp != sender:
                msg.body("❌ Job not found or not assigned to you.")
                return str(resp)
            job.status = "in_progress"  # Add new status to Job model if needed
            db.commit()
            # Notify original customer/assigner
            sms(job.customer_phone, f"✅ Tech accepted job #{job.id}.")
            msg.body(f"✅ Accepted job #{job.id}. Start working!")
            return str(resp)

        # /done <job_id>
        m = CMD_PATTERNS["done"].match(body)
        if m:
            job_id = int(m.group(1))
            job = db.query(Job).get(job_id)
            if not job or job.assigned_to.whatsapp != sender:
                msg.body("❌ Job not found or not assigned to you.")
                return str(resp)
            job.status = "done"
            db.commit()
            sms(job.customer_phone, f"🎉 Job #{job.id} completed by tech.")
            msg.body(f"✅ Marked job #{job.id} as done.")
            return str(resp)

        # /issue <job_id> <note>
        m = CMD_PATTERNS["issue"].match(body)
        if m:
            job_id = int(m.group(1))
            note = m.group(2).strip() or "No details provided."
            job = db.query(Job).get(job_id)
            if not job or job.assigned_to.whatsapp != sender:
                msg.body("❌ Job not found or not assigned to you.")
                return str(resp)
            job.notes = (job.notes or "") + f"\nTech issue: {note}"
            job.status = "issue"  # New status
            db.commit()
            sms(job.customer_phone, f"⚠️ Issue reported on job #{job.id}: {note}")
            msg.body(f"✅ Reported issue for job #{job.id}.")
            return str(resp)

        # /status <job_id> - Tech can query job status
        m = CMD_PATTERNS["status"].match(body)
        if m:
            job_id = int(m.group(1))
            job = db.query(Job).get(job_id)
            if not job or job.assigned_to.whatsapp != sender:
                msg.body("❌ Job not found or not assigned to you.")
                return str(resp)
            status_info = (
                f"📋 Job #{job.id} Status\n"
                f"Model: {job.model}\n"
                f"Qty: {job.qty}\n"
                f"Status: {job.status.upper()}\n"
                f"Customer: {job.customer_phone}\n"
                f"Notes: {job.notes or 'None'}"
            )
            msg.body(status_info)
            return str(resp)

        # /cancel - Exit intake flow
        m = CMD_PATTERNS["cancel"].match(body)
        if m:
            draft = db.query(Job).filter_by(customer_phone=sender, status="draft").order_by(Job.id.desc()).first()
            if draft and draft.intake_step > 0:
                draft.status = "canceled"
                draft.intake_step = 0
                db.commit()
                msg.body("❌ Intake canceled. Send a photo to start a new job intake.")
                return str(resp)
            else:
                msg.body("No active intake to cancel.")
                return str(resp)

        # 2) Media-first intake flow
        # If user sends a photo: create a 'draft' job and ask questions step-by-step.
        if num_media > 0:
            media_url = request.values.get("MediaUrl0")
            # 2.1 Create draft job
            job = Job(customer_phone=sender, intake_step=1, status="draft", photo_url=media_url)
            db.add(job); db.commit()

            # Upload to S3 (optional) and update
            try:
                s3_url = upload_to_s3_from_twilio(media_url, job.id)
                if s3_url != media_url:
                    job.photo_url = s3_url
                    job.s3_key = s3_url.replace(f"s3://{AWS_S3_BUCKET}/", "")
                    db.commit()
            except Exception as e:
                print("S3 upload error:", e)

            msg.body(
                f"📸 Got your photo. Created draft job #{job.id}.\n"
                f"Step 1/4: What model? (e.g., 14pro, 14 pro max, 13 pro max)"
            )
            return str(resp)

        # If in intake steps, advance the flow
        draft = db.query(Job).filter_by(customer_phone=sender, status="draft").order_by(Job.id.desc()).first()
        if draft and draft.intake_step > 0:
            if draft.intake_step == 1:
                norm = normalize_model(body)
                if not norm:
                    msg.body("❌ Unknown model. Try: 14pro, 14 pro max, 13 pro max, 15 pro max, 12 pro max.")
                    return str(resp)
                draft.model = norm
                draft.intake_step = 2
                db.commit()
                msg.body("Step 2/4: How many screens (qty)?")
                return str(resp)

            elif draft.intake_step == 2:
                if not body.isdigit():
                    msg.body("❌ Please enter a number for qty.")
                    return str(resp)
                draft.qty = int(body)
                draft.intake_step = 3
                db.commit()
                msg.body("Step 3/4: Include cable? (yes/no)")
                return str(resp)

            elif draft.intake_step == 3:
                yn = body.strip().lower()
                draft.include_cable = yn in ("y","yes")
                draft.intake_step = 4
                db.commit()
                msg.body("Step 4/4: Any notes? (or reply 'none')")
                return str(resp)

            elif draft.intake_step == 4:
                draft.notes = None if body.strip().lower() == "none" else body.strip()
                draft.status = "open"
                draft.intake_step = 0
                db.commit()

                unit_with_adder, labor, grand = calc_total(db, draft)
                msg.body(
                    f"✅ Job #{draft.id} opened.\n"
                    f"Model: {draft.model} | Qty: {draft.qty} | Cable: {'yes' if draft.include_cable else 'no'}\n"
                    f"Unit price (w/ cable if any): ${unit_with_adder:.2f}\n"
                    f"Labor (${LABOR_PER_SCREEN:.0f} × {draft.qty}): ${labor:.2f}\n"
                    f"Grand Total: *${grand:.2f}*\n\n"
                    f"Assign with: /assign {draft.id} <techname>\n"
                    f"Get total anytime: /total {draft.id}"
                )
                return str(resp)

        # 3) Check if sender is a technician for tech-specific help
        is_tech = db.query(Technician).filter_by(whatsapp=sender).first() is not None
        if is_tech:
            tech_help = (
                "🔧 *Technician Commands*\n"
                "• /accept <job_id> – accept assigned job\n"
                "• /done <job_id> – mark job as completed\n"
                "• /issue <job_id> [description] – report issue with job\n"
                "• /status <job_id> – check job status\n"
                "• /tz <Area/City> – set your timezone\n"
                "\n💡 Reply with any message for this help menu."
            )
            msg.body(tech_help)
            return str(resp)

        # 4) General help / default
        help_txt = (
            " *MTS Service Bot*\n"
            "Commands:\n"
            "• /tz <Area/City> – set your timezone (default Asia/Dubai)\n"
            "• /price <model> – show price (e.g., /price 14pro)\n"
            "• /setprice <model> <price> +<cable> – set price (e.g., /setprice 14pro 170 +10)\n"
            "• /assign <job_id> <techname> – assign job & auto-notify tech\n"
            "• /accept <job_id> – accept assigned job\n"
            "• /done <job_id> – mark job as completed\n"
            "• /issue <job_id> [description] – report issue with job\n"
            "• /total <job_id> – calculate total (unit×qty + labor)\n"
            "• /dispatch <job_id> [note] – request courier (stub)\n"
            "\nTip: Send a *photo first* to start intake."
        )
        msg.body(help_txt)
        return str(resp)

    except Exception as e:
        print("Handler error:", e)
        msg.body("⚠️ Unexpected error. Try again.")
        return str(resp)
    finally:
        db.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
