import csv
import difflib
import os
import unicodedata
from flask import Flask, render_template, request, jsonify, send_file, session
from gtts import gTTS
import tempfile
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'votre-cle-secrete-par-defaut')

chemin_fichier = os.path.join(os.path.dirname(__file__), 'traductions.csv')

# Chargement du dictionnaire
def sans_accents(texte):
    return ''.join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

def charger_dictionnaires(fichier_csv):
    patois_to_fr = {}
    fr_to_patois = {}
    definitions = {}
    historiques = {}
    phonetique = {}
    
    # Dictionnaire pour la recherche directe (sans accents)
    recherche_fr_to_patois = {}
    recherche_patois_to_fr = {}

    try:
        # Utiliser spécifiquement l'encodage Windows-1252
        with open(fichier_csv, mode='r', encoding='cp1252') as fichier:
            lecteur = csv.DictReader(fichier)
            print("\n=== Chargement du dictionnaire ===")
            
            for ligne in lecteur:
                patois = ligne['mot_patois'].strip().lower()
                francais = ligne['traduction_francaise'].strip().lower()
                
                # Ne prendre que la première traduction française si plusieurs sont présentes
                if ',' in francais:
                    francais = francais.split(',')[0].strip()
                
                sens = ligne.get('SENS', '').strip()
                histo = ligne.get('Historique_alternative', '').strip()
                phono = ligne.get('Phonetique', '').strip()

                # Ne traiter que les lignes qui ont à la fois un mot patois et une traduction française
                if patois and francais:
                    # Ajouter les traductions dans les deux sens
                    patois_to_fr[patois] = francais
                    fr_to_patois[francais] = patois
                    
                    # Ajouter les mots sans accents pour la recherche
                    recherche_patois_to_fr[sans_accents(patois)] = patois
                    recherche_fr_to_patois[sans_accents(francais)] = patois
                    
                    # Ajouter chaque mot de la traduction française séparément
                    if ',' in ligne['traduction_francaise']:
                        for mot in ligne['traduction_francaise'].split(','):
                            mot_clean = mot.strip().lower()
                            if mot_clean:
                                fr_to_patois[mot_clean] = patois
                                recherche_fr_to_patois[sans_accents(mot_clean)] = patois
                    
                    # Stocker les informations supplémentaires
                    if francais:
                        definitions[francais] = sens
                        historiques[francais] = histo
                    if patois:
                        definitions[patois] = sens
                        historiques[patois] = histo
                        phonetique[patois] = phono

            print(f"Nombre total de mots chargés: {len(patois_to_fr)}")
            print(f"Nombre de mots avec phonétique: {sum(1 for v in phonetique.values() if v)}")
            print("\nExemples de traductions chargées:")
            print("fr_to_patois:", dict(list(fr_to_patois.items())[:5]))
            print("recherche_fr_to_patois:", dict(list(recherche_fr_to_patois.items())[:5]))
            print("=== Chargement terminé ===\n")
    except Exception as e:
        print(f"Erreur lors du chargement du fichier CSV: {e}")

    return patois_to_fr, fr_to_patois, definitions, historiques, phonetique, recherche_fr_to_patois, recherche_patois_to_fr

patois_to_fr, fr_to_patois, definitions, historiques, phonétiques, recherche_fr_to_patois, recherche_patois_to_fr = charger_dictionnaires(chemin_fichier)

@app.route('/', methods=['GET', 'POST'])
def index():
    traduction = ""
    mots_infos = []
    
    # Récupérer le sens de traduction de la session ou utiliser la valeur par défaut
    sens_actuel = session.get('sens_traduction', 'patois-fr')
    
    if request.method == 'POST':
        phrase_originale = request.form['phrase'].strip()
        phrase = phrase_originale.lower()
        sens = request.form['sens']
        
        print(f"\n=== Nouvelle traduction ===")
        print(f"Phrase originale: {phrase_originale}")
        print(f"Sens de traduction: {sens}")
        
        # Sauvegarder le sens de traduction dans la session
        session['sens_traduction'] = sens
        
        # Déterminer le dictionnaire à utiliser
        if sens == "patois-fr":
            # Mode patois vers français
            dictionnaire = patois_to_fr
            dictionnaire_recherche = recherche_patois_to_fr
            retourner_patois = False
            print("Mode: patois vers français")
        else:
            # Mode français vers patois
            dictionnaire = fr_to_patois
            dictionnaire_recherche = recherche_fr_to_patois
            retourner_patois = True
            print("Mode: français vers patois")
            print("Contenu du dictionnaire fr_to_patois:", dict(list(fr_to_patois.items())[:5]))
            print("Contenu du dictionnaire recherche_fr_to_patois:", dict(list(recherche_fr_to_patois.items())[:5]))

        dictionnaire_sans_accents = {sans_accents(k): v for k, v in dictionnaire.items()}
        correspondance_inverse = {sans_accents(k): k for k in dictionnaire}

        mots = phrase.split()
        print(f"Mots à traduire: {mots}")
        
        for mot in mots:
            mot_clean = sans_accents(mot)
            print(f"\n--- Traduction du mot: {mot} (sans accents: {mot_clean}) ---")
            print(f"Recherche dans dictionnaire_sans_accents: {mot_clean in dictionnaire_sans_accents}")
            print(f"Recherche dans dictionnaire_recherche: {mot_clean in dictionnaire_recherche}")
            
            # Recherche directe
            if mot_clean in dictionnaire_sans_accents:
                print(f"Mot trouvé dans le dictionnaire principal")
                traduit = dictionnaire_sans_accents[mot_clean]
                original = correspondance_inverse[mot_clean]
                phon = phonétiques.get(original, "")
                print(f"Traduction trouvée: {traduit}")
                print(f"Mot original: {original}")
                
                # En mode français vers patois, on retourne le mot patois
                if retourner_patois:
                    print("Mode français vers patois: affichage du mot patois")
                    # Le premier élément est ce qui sera affiché, le deuxième est pour l'attribut data-mot
                    mots_infos.append((traduit, mot, phon))
                    traduction += traduit + " "
                else:
                    print("Mode patois vers français: affichage de la traduction française")
                    mots_infos.append((traduit, original, phon))
                    traduction += traduit + " "
            else:
                print(f"Mot non trouvé dans le dictionnaire principal")
                # Recherche dans le dictionnaire de recherche (sans accents)
                trouve = False
                
                # Recherche directe dans le dictionnaire de recherche
                if mot_clean in dictionnaire_recherche:
                    print(f"Mot trouvé dans le dictionnaire de recherche")
                    # En mode français vers patois, dictionnaire_recherche contient déjà le mot patois
                    if retourner_patois:
                        mot_patois = dictionnaire_recherche[mot_clean]
                        phon = phonétiques.get(mot_patois, "")
                        print(f"Mot patois trouvé: {mot_patois}")
                        # Le premier élément est ce qui sera affiché, le deuxième est pour l'attribut data-mot
                        mots_infos.append((mot_patois, mot, phon))
                        traduction += mot_patois + " "
                    else:
                        # Mode patois vers français
                        mot_patois = dictionnaire_recherche[mot_clean]
                        traduit = dictionnaire[mot_patois]
                        phon = phonétiques.get(mot_patois, "")
                        print(f"Traduction française trouvée: {traduit}")
                        mots_infos.append((traduit, mot_patois, phon))
                        traduction += traduit + " "
                    
                    trouve = True
                
                # Si toujours pas trouvé, utiliser la suggestion
                if not trouve:
                    print("Recherche de suggestions")
                    suggestion = difflib.get_close_matches(mot_clean, dictionnaire_sans_accents.keys(), n=1)
                    if suggestion:
                        suggere = suggestion[0]
                        traduit = dictionnaire_sans_accents[suggere]
                        original = correspondance_inverse[suggere]
                        phon = phonétiques.get(original, "")
                        print(f"Suggestion trouvée: {suggere}")
                        print(f"Traduction de la suggestion: {traduit}")
                        
                        # En mode français vers patois, on retourne le mot patois
                        if retourner_patois:
                            print("Mode français vers patois: affichage du mot patois suggéré")
                            mots_infos.append((traduit + "?", mot, phon))
                            traduction += traduit + "? "
                        else:
                            print("Mode patois vers français: affichage de la traduction française suggérée")
                            mots_infos.append((traduit + "?", original, phon))
                            traduction += traduit + "? "
                    else:
                        print("Aucune suggestion trouvée")
                        mots_infos.append((mot, mot, ""))
                        traduction += f"[{mot}] "

        print(f"\nRésultat final de la traduction: {traduction}")
        print("Mots infos:", mots_infos)
        print("=== Fin de la traduction ===\n")

        return render_template('index.html', traduction=True, phrase=phrase_originale, mots=mots_infos, sens=sens)

    # Pour les requêtes GET, utiliser le sens stocké dans la session
    return render_template('index.html', sens=sens_actuel)

@app.route('/suggestions', methods=['POST'])
def suggestions():
    data = request.json
    prefix = sans_accents(data['prefix'].lower())
    sens = data['sens']
    dictionnaire = patois_to_fr if sens == "patois-fr" else fr_to_patois

    suggestions = []
    for mot in dictionnaire.keys():
        if sans_accents(mot).startswith(prefix):
            suggestions.append(mot)
        if len(suggestions) >= 10:
            break

    return jsonify(suggestions)

@app.route('/traduire', methods=['POST'])
def traduire():
    data = request.json
    phrase = data['texte'].strip().lower()
    sens = data['sens']

    if sens == "patois-fr":
        dictionnaire = patois_to_fr
    else:
        dictionnaire = fr_to_patois

    dictionnaire_sans_accents = {sans_accents(k): v for k, v in dictionnaire.items()}
    correspondance_inverse = {sans_accents(k): k for k in dictionnaire}

    mots = phrase.split()
    traduction = []
    mots_originaux = []

    for mot in mots:
        mot_clean = sans_accents(mot)
        if mot_clean in dictionnaire_sans_accents:
            mot_traduit = dictionnaire_sans_accents[mot_clean]
            traduction.append(mot_traduit)
            mots_originaux.append(correspondance_inverse[mot_clean])
        else:
            suggestion = difflib.get_close_matches(mot_clean, dictionnaire_sans_accents.keys(), n=1)
            if suggestion:
                mot_suggere = suggestion[0]
                mot_traduit = dictionnaire_sans_accents[mot_suggere]
                traduction.append(f"{mot_traduit}?")
                mots_originaux.append(correspondance_inverse[mot_suggere])
            else:
                traduction.append(f"[{mot}]")
                mots_originaux.append(mot)

    return jsonify({
        'traduction': traduction,
        'originaux': mots_originaux
    })

@app.route('/infos', methods=['POST'])
def infos():
    mot = request.json['mot'].lower()
    return jsonify({
        'definition': definitions.get(mot, "Définition inconnue."),
        'historique': historiques.get(mot, "Aucune variante ou historique.")
    })

@app.route('/synthese-vocale', methods=['POST'])
def synthese_vocale():
    data = request.json
    texte = data.get('texte', '')
    download = data.get('download', False)
    
    print(f"\n=== Nouvelle demande de synthèse vocale ===")
    print(f"Texte: {texte}")
    print(f"Téléchargement: {download}")
    
    # Générer l'audio en mémoire (sans fichier temporaire)
    mp3_fp = BytesIO()
    tts = gTTS(text=texte, lang='fr')
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    if download:
        return send_file(
            mp3_fp,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f"{texte}.mp3"
        )
    else:
        return send_file(mp3_fp, mimetype='audio/mpeg')

@app.route('/en-savoir-plus')
def en_savoir_plus():
    return render_template('en_savoir_plus.html')

# Configuration pour la production
if __name__ == '__main__':
    # En développement
    app.run(debug=True)
else:
    # En production
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'votre-cle-secrete-par-defaut')
    app.config['PREFERRED_URL_SCHEME'] = 'https'