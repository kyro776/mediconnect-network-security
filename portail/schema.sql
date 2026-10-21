-- Schema de la base du portail MediConnect (PostgreSQL)
CREATE DATABASE mediconnect;
\c mediconnect

CREATE TABLE medecins (
  id            serial PRIMARY KEY,
  nom           text NOT NULL,
  specialite    text NOT NULL,
  login         text NOT NULL UNIQUE,
  password_hash text NOT NULL,          -- empreinte (scrypt), jamais le mot de passe
  totp_secret   text,
  totp_actif    boolean NOT NULL DEFAULT false
);

CREATE TABLE rendez_vous (
  id            serial PRIMARY KEY,
  medecin_id    integer NOT NULL REFERENCES medecins(id),
  patient_nom   text NOT NULL,
  patient_email text NOT NULL,
  date_heure    timestamp NOT NULL,
  cree_le       timestamptz NOT NULL DEFAULT now()
);

-- Compte de l'application : droits minimaux (le mot de passe est genere
-- aleatoirement a l'installation, il ne figure jamais dans le depot).
-- CREATE ROLE portail_app LOGIN PASSWORD '<genere>';
GRANT CONNECT ON DATABASE mediconnect TO portail_app;
GRANT USAGE ON SCHEMA public TO portail_app;
GRANT SELECT ON medecins TO portail_app;
GRANT UPDATE (totp_secret, totp_actif) ON medecins TO portail_app;
GRANT SELECT, INSERT ON rendez_vous TO portail_app;
GRANT USAGE ON SEQUENCE rendez_vous_id_seq TO portail_app;
