from django.utils.text import slugify


WHITELIST_WORDS = ["os", "dos", "pus"]

BLACKLIST_WORDS = [
    "alors", "aucun", "aussi", "autre", "avant", "avec", "avoir", "bas", "haut", "bon", "car", "cela", "ces", "ceux", "chaque", "comme", "comment", "dans", "des", "dedans", "dehors", "depuis", "devrait", "doit", "donc", "debut", "elle", "elles", "encore", "essai", "est", "fait", "faites", "fois", "font", "hors", "ici", "ils", "juste", "les", "leur", "maintenant", "mais", "mes", "mien", "moins", "mon", "mot", "meme", "ni", "notre", "nous", "par", "parce", "pas", "peut", "peu", "plupart", "pour", "pourquoi", "quand", "que", "quel", "qui", "sans", "ses", "seulement", "sien", "son", "sont", "sous", "soyez", "sujet", "sur", "tandis", "tellement", "tels", "tes", "ton", "tous", "tout", "trop", "tres", "voient", "vont", "votre", "vous", "etaient", "etat", "etions", "ete", "les", "des", "aux", "dans", "pour", "lie", "liee", "accident", "baisse", "bobo", "brulure", "chronique", "chute", "crise", "diminution", "douleur", "douloureuse", "douloureux", "dysfonctionnement", "etat", "fievre", "hypersensibilite", "infection", "lesion", "mal", "maladie", "malaise", "manque", "organe", "perte", "probleme", "reaction", "rouge", "rythme", "sensation", "syndrome", "trouble", "trou", "dessus", "dessous", "fais",
]


def normalize_text(text):
    normalized = []
    words = slugify(text.replace("'", " ")).split("-")
    for w in words:
        if not w in WHITELIST_WORDS and (len(w) < 3 or w in BLACKLIST_WORDS):
            continue
        if len(w) > 3 and w.endswith("s"): w = w[:-1]
        if w.endswith("aux"): w = w[:-3] + "al"
        if w.endswith("ale"): w = w[:-3] + "al"
        if w.endswith("elle"): w = w[:-3] + "el"
        if w.endswith("ee"): w = w[:1]
        if w.endswith("ation"): w = w[:-5] + "er"
        if w.endswith("euse"): w = w[:-4] + "eu"
        if w.endswith("eux"): w = w[:-3] + "eu"
        if w.endswith("ement"): w = w[:-5] + "er"
        if w.endswith("age"): w = w[:-3] + "er"
        if w in BLACKLIST_WORDS:
            continue
        normalized.append(w)
    return " ".join(normalized)
