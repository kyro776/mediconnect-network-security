"""Portail MediConnect.

- Partie publique : prise de rendez-vous par les patients (sans compte).
- Espace medecin : mot de passe + code a usage unique (TOTP), soit une
  authentification a deux facteurs.

L'application tourne derriere le reverse proxy Nginx (DMZ) et utilise la base
PostgreSQL de la zone SERVEURS, avec un compte aux droits minimaux.
"""
import datetime
import io
import os
import secrets

import click
import psycopg
import pyotp
import qrcode
import qrcode.image.svg
from flask import (Flask, abort, g, redirect, render_template_string, request,
                   session, url_for)
from psycopg.rows import dict_row
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SESSION_COOKIE_SECURE=True,        # cookie envoye uniquement en HTTPS
    SESSION_COOKIE_HTTPONLY=True,      # inaccessible au JavaScript
    SESSION_COOKIE_SAMESITE="Strict",  # non envoye depuis un autre site
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(minutes=30),
    MAX_CONTENT_LENGTH=64 * 1024,
)
# Le reverse proxy transmet l'adresse reelle du client et le protocole HTTPS.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

DATABASE_URL = os.environ["DATABASE_URL"]
MAX_ECHECS_MFA = 5
# Hachage factice : la verification dure le meme temps, que le compte existe ou non.
HASH_FACTICE = generate_password_hash(secrets.token_hex(16))


# --------------------------------------------------------------------------
# Base de donnees
# --------------------------------------------------------------------------
def db():
    if "db" not in g:
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
    return g.db


@app.teardown_appcontext
def fermer_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# --------------------------------------------------------------------------
# Protection CSRF : un jeton secret par session, verifie a chaque formulaire
# --------------------------------------------------------------------------
def jeton_csrf():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf"] = jeton_csrf


@app.before_request
def verifier_csrf():
    if request.method == "POST":
        recu = request.form.get("_csrf", "")
        attendu = session.get("_csrf", "")
        if not recu or not attendu or not secrets.compare_digest(recu, attendu):
            abort(400)


@app.after_request
def entetes(reponse):
    if request.path.startswith("/medecin"):
        reponse.headers["Cache-Control"] = "no-store"
    return reponse


def journal(evenement, **details):
    infos = " ".join(f"{k}={v}" for k, v in details.items())
    app.logger.warning("securite %s ip=%s %s", evenement, request.remote_addr, infos)


# --------------------------------------------------------------------------
# Gabarits
# --------------------------------------------------------------------------
BASE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MediConnect</title>
<style>
body{font-family:system-ui,sans-serif;max-width:680px;margin:2rem auto;padding:0 1rem;color:#1d2733}
h1{color:#0b5c8a;font-size:1.6rem}nav a{margin-right:1rem}
form{display:grid;gap:.6rem;margin:1rem 0}input,select,button{padding:.5rem;font-size:1rem}
button{background:#0b5c8a;color:#fff;border:0;border-radius:4px;cursor:pointer}
.msg{padding:.6rem;border-radius:4px;background:#e6f2ea}.err{padding:.6rem;border-radius:4px;background:#fdecea}
table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}
code{background:#f1f3f5;padding:.1rem .3rem;word-break:break-all}
</style></head><body>
<nav><a href="/">Prendre rendez-vous</a><a href="/medecin">Espace médecin</a></nav>
__CONTENU__
</body></html>"""


def page(contenu, statut=200, **ctx):
    return render_template_string(BASE.replace("__CONTENU__", contenu), **ctx), statut


ACCUEIL = """
<h1>Prendre rendez-vous</h1>
{% if ok %}<p class="msg">Votre demande de rendez-vous a bien été enregistrée.</p>{% endif %}
{% if erreur %}<p class="err">{{ erreur }}</p>{% endif %}
<form method="post" action="/rendez-vous">
  <input type="hidden" name="_csrf" value="{{ csrf() }}">
  <label>Médecin <select name="medecin" required>
    {% for m in medecins %}<option value="{{ m.id }}">{{ m.nom }} ({{ m.specialite }})</option>{% endfor %}
  </select></label>
  <label>Nom <input name="nom" maxlength="100" required></label>
  <label>E-mail <input name="email" type="email" maxlength="120" required></label>
  <label>Date et heure <input name="date" type="datetime-local" required></label>
  <button>Demander le rendez-vous</button>
</form>"""

CONNEXION = """
<h1>Espace médecin : connexion</h1>
{% if erreur %}<p class="err">{{ erreur }}</p>{% endif %}
<form method="post">
  <input type="hidden" name="_csrf" value="{{ csrf() }}">
  <label>Identifiant <input name="login" autocomplete="username" required></label>
  <label>Mot de passe <input name="motdepasse" type="password" autocomplete="current-password" required></label>
  <button>Continuer</button>
</form>"""

ENROLEMENT = """
<h1>Activer la double authentification</h1>
<p>Scannez ce code avec une application d'authentification (Google Authenticator,
Microsoft Authenticator, FreeOTP…), puis saisissez le code à 6 chiffres affiché.</p>
<div>{{ qr|safe }}</div>
<p>Clé (si le scan est impossible) : <code>{{ secret }}</code></p>
{% if erreur %}<p class="err">{{ erreur }}</p>{% endif %}
<form method="post">
  <input type="hidden" name="_csrf" value="{{ csrf() }}">
  <label>Code à 6 chiffres <input name="code" inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code" required></label>
  <button>Activer</button>
</form>"""

VERIFICATION = """
<h1>Double authentification</h1>
<p>Saisissez le code à 6 chiffres de votre application d'authentification.</p>
{% if erreur %}<p class="err">{{ erreur }}</p>{% endif %}
<form method="post">
  <input type="hidden" name="_csrf" value="{{ csrf() }}">
  <label>Code <input name="code" inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code" required></label>
  <button>Valider</button>
</form>"""

TABLEAU = """
<h1>Bonjour {{ nom }}</h1>
<h2>Vos rendez-vous</h2>
{% if rdv %}
<table><tr><th>Date</th><th>Patient</th><th>E-mail</th></tr>
{% for r in rdv %}<tr><td>{{ r.date_heure.strftime('%d/%m/%Y %H:%M') }}</td><td>{{ r.patient_nom }}</td><td>{{ r.patient_email }}</td></tr>{% endfor %}
</table>
{% else %}<p>Aucun rendez-vous.</p>{% endif %}
<form method="post" action="/medecin/deconnexion">
  <input type="hidden" name="_csrf" value="{{ csrf() }}">
  <button>Se déconnecter</button>
</form>"""


# --------------------------------------------------------------------------
# Partie publique
# --------------------------------------------------------------------------
def liste_medecins():
    return db().execute("SELECT id, nom, specialite FROM medecins ORDER BY nom").fetchall()


@app.get("/")
def accueil():
    return page(ACCUEIL, medecins=liste_medecins(), ok=request.args.get("ok"))


@app.post("/rendez-vous")
def prendre_rendez_vous():
    nom = request.form.get("nom", "").strip()[:100]
    email = request.form.get("email", "").strip()[:120]
    try:
        medecin_id = int(request.form.get("medecin", ""))
        date_heure = datetime.datetime.strptime(request.form.get("date", ""), "%Y-%m-%dT%H:%M")
    except ValueError:
        date_heure, medecin_id = None, None
    maintenant = datetime.datetime.now()
    valide = (
        nom and "@" in email and date_heure is not None
        and maintenant < date_heure < maintenant + datetime.timedelta(days=365)
        and db().execute("SELECT 1 FROM medecins WHERE id = %s", (medecin_id,)).fetchone()
    )
    if not valide:
        return page(ACCUEIL, 400, medecins=liste_medecins(),
                    erreur="Demande invalide : vérifiez les champs et choisissez une date future.")
    # Requete parametree : aucune donnee saisie n'est inseree dans le texte SQL.
    db().execute(
        "INSERT INTO rendez_vous (medecin_id, patient_nom, patient_email, date_heure) "
        "VALUES (%s, %s, %s, %s)",
        (medecin_id, nom, email, date_heure),
    )
    return redirect(url_for("accueil", ok=1))


# --------------------------------------------------------------------------
# Espace medecin : mot de passe, puis code TOTP
# --------------------------------------------------------------------------
@app.route("/medecin/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "GET":
        return page(CONNEXION)
    login = request.form.get("login", "").strip()
    medecin = db().execute(
        "SELECT id, password_hash, totp_actif FROM medecins WHERE login = %s", (login,)
    ).fetchone()
    hash_attendu = medecin["password_hash"] if medecin else HASH_FACTICE
    if not check_password_hash(hash_attendu, request.form.get("motdepasse", "")) or not medecin:
        journal("echec_mot_de_passe", login=login)
        return page(CONNEXION, 401, erreur="Identifiant ou mot de passe incorrect.")
    session.clear()  # nouvelle session : empeche la fixation de session
    session["mfa_en_attente"] = medecin["id"]
    session["echecs_mfa"] = 0
    cible = "verification" if medecin["totp_actif"] else "enrolement"
    return redirect(url_for(cible))


def medecin_en_attente():
    medecin_id = session.get("mfa_en_attente")
    if not medecin_id:
        return None
    return db().execute(
        "SELECT id, login, totp_secret, totp_actif FROM medecins WHERE id = %s", (medecin_id,)
    ).fetchone()


def ouvrir_session(medecin_id):
    session.clear()
    session["medecin_id"] = medecin_id
    session.permanent = True
    return redirect(url_for("tableau"))


def echec_mfa(gabarit, **ctx):
    session["echecs_mfa"] = session.get("echecs_mfa", 0) + 1
    journal("echec_totp", medecin=session.get("mfa_en_attente"), essai=session["echecs_mfa"])
    if session["echecs_mfa"] >= MAX_ECHECS_MFA:
        session.clear()
        return redirect(url_for("connexion"))
    return page(gabarit, 401, erreur="Code incorrect.", **ctx)


@app.route("/medecin/enrolement", methods=["GET", "POST"])
def enrolement():
    medecin = medecin_en_attente()
    if not medecin:
        return redirect(url_for("connexion"))
    if medecin["totp_actif"]:
        return redirect(url_for("verification"))
    secret = medecin["totp_secret"]
    if not secret:
        secret = pyotp.random_base32()
        db().execute("UPDATE medecins SET totp_secret = %s WHERE id = %s", (secret, medecin["id"]))
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=medecin["login"], issuer_name="MediConnect")
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    tampon = io.BytesIO()
    image.save(tampon)
    ctx = {"qr": tampon.getvalue().decode(), "secret": secret}
    if request.method == "GET":
        return page(ENROLEMENT, **ctx)
    if not totp.verify(request.form.get("code", ""), valid_window=1):
        return echec_mfa(ENROLEMENT, **ctx)
    db().execute("UPDATE medecins SET totp_actif = TRUE WHERE id = %s", (medecin["id"],))
    journal("totp_active", medecin=medecin["id"])
    return ouvrir_session(medecin["id"])


@app.route("/medecin/verification", methods=["GET", "POST"])
def verification():
    medecin = medecin_en_attente()
    if not medecin or not medecin["totp_actif"]:
        return redirect(url_for("connexion"))
    if request.method == "GET":
        return page(VERIFICATION)
    if not pyotp.TOTP(medecin["totp_secret"]).verify(request.form.get("code", ""), valid_window=1):
        return echec_mfa(VERIFICATION)
    journal("connexion_reussie", medecin=medecin["id"])
    return ouvrir_session(medecin["id"])


@app.get("/medecin")
def tableau():
    medecin_id = session.get("medecin_id")
    if not medecin_id:
        return redirect(url_for("connexion"))
    medecin = db().execute("SELECT nom FROM medecins WHERE id = %s", (medecin_id,)).fetchone()
    rdv = db().execute(
        "SELECT patient_nom, patient_email, date_heure FROM rendez_vous "
        "WHERE medecin_id = %s ORDER BY date_heure",
        (medecin_id,),
    ).fetchall()
    return page(TABLEAU, nom=medecin["nom"], rdv=rdv)


@app.post("/medecin/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


# --------------------------------------------------------------------------
# Outil d'administration : calcule le hachage d'un mot de passe de medecin.
# Le compte est ensuite cree dans la base par l'administrateur (psql), car
# l'application n'a pas le droit d'ajouter des medecins.
# --------------------------------------------------------------------------
@app.cli.command("hacher-mot-de-passe")
def hacher_mot_de_passe():
    mot_de_passe = click.prompt("Mot de passe du medecin", hide_input=True,
                                confirmation_prompt=True)
    click.echo(generate_password_hash(mot_de_passe))
