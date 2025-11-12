-- Technicians table
CREATE TABLE IF NOT EXISTS technicians (
  id SERIAL PRIMARY KEY,
  name VARCHAR(80) UNIQUE NOT NULL,
  whatsapp VARCHAR(40) NOT NULL,  -- 'whatsapp:+1...'
  active BOOLEAN DEFAULT TRUE
);

-- User preferences for timezone
CREATE TABLE IF NOT EXISTS user_prefs (
  id SERIAL PRIMARY KEY,
  phone VARCHAR(40) UNIQUE NOT NULL,  -- sender line
  tz VARCHAR(80) DEFAULT 'Asia/Dubai'
);

-- Price list for phone models
CREATE TABLE IF NOT EXISTS prices (
  id SERIAL PRIMARY KEY,
  model VARCHAR(80) UNIQUE NOT NULL,  -- e.g. '14pro', '14promax'
  unit_price FLOAT NOT NULL,
  cable_adder FLOAT DEFAULT 0.0  -- add-on if cable included
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  customer_phone VARCHAR(40),   -- who submitted intake
  model VARCHAR(80),
  qty INTEGER DEFAULT 1,
  include_cable BOOLEAN DEFAULT FALSE,
  notes TEXT,
  photo_url TEXT,     -- original (twilio) or S3 url
  s3_key VARCHAR(255), -- if uploaded
  status VARCHAR(40) DEFAULT 'draft',  -- draft|open|assigned|done|canceled
  intake_step INTEGER DEFAULT 0,      -- 0 none, 1 ask model, 2 ask qty, 3 cable?, 4 notes
  assigned_to_id INTEGER REFERENCES technicians(id)
);

-- Seed phone LCD prices
INSERT INTO prices (model, unit_price, cable_adder) VALUES
('16promax', 270, 15),
('16pro',    260, 15),
('15promax', 230, 15),
('15pro',    200, 15),
('14promax', 190, 10),
('14pro',    170, 10),
('13promax', 180, 10),
('13pro',    160, 10)
ON CONFLICT (model) DO NOTHING;

-- Seed technicians
INSERT INTO technicians (name, whatsapp, active) VALUES
('Tech_A', 'whatsapp:+1571XXXXXXX', true),
('Tech_B', 'whatsapp:+1703XXXXXXX', true)
ON CONFLICT (name) DO NOTHING;
