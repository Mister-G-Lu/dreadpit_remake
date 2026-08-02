#!/usr/bin/env python3
"""
Archetype Coverage Map

Classifies every fighter in comparison_analysis.json into broad visual archetype
families using BLIP keywords + names, then reports which archetypes are COVERED
(>=5 wins) vs UNCOVERED.

The goal: find 3+ archetypes that (a) have NOT been proven in the arena, and
(b) FLUX can render consistently -- so we can build novel fighters.
"""
import json
import os
from collections import defaultdict

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(CACHE_DIR, "comparison_analysis.json")

# ---------------------------------------------------------------------------
# Archetype family definitions: each has a detector on (blip, kws, name)
# ---------------------------------------------------------------------------

def _has(text, *words):
    t = text.lower()
    return any(w in t for w in words)

def classify(blip, kws, name):
    """Return a list of archetype families this fighter belongs to."""
    hits = []
    n = name.lower()
    b = (blip or "").lower()

    # --- Monster / demon / dragon (the MAGIC meta) ---
    if kws.get("monster") or _has(b, "demon", "monster", "beast", "dragon", "fiend", "devil", "daemon"):
        if _has(b, "dragon", "wyrm", "drake"):
            hits.append("dragon")
        else:
            hits.append("demon/monster")
    # --- Fire / heat ---
    if kws.get("fire") or _has(b, "fire", "flame", "burn", "blaze", "molten", "lava", "ember", "magma"):
        hits.append("fire")
    # --- Wings / angel ---
    if kws.get("wings") or _has(b, "wing", "angel", "seraph", "halo"):
        hits.append("wings/angel")
    # --- Robot / mech ---
    if kws.get("robot") or _has(b, "robot", "mech", "gundam", "android", "cyborg", "machine", "droid"):
        hits.append("robot/mech")
    # --- Human + gun (SIMO archetype) ---
    if kws.get("gun") or _has(b, "gun", "rifle", "sniper", "gatling", "cannon", "pistol", "firearm", "weapon"):
        hits.append("gun/rifle")
    # --- Sword / blade ---
    if kws.get("sword") or _has(b, "sword", "blade", "katana", "saber", "scimitar"):
        hits.append("sword/blade")
    # --- Armor / knight ---
    if kws.get("armor") or kws.get("helmet") or kws.get("shield") or _has(b, "armor", "armour", "knight", "helmet", "plate"):
        hits.append("armored")
    # --- Dark / void / shadow ---
    if kws.get("dark") or _has(b, "dark", "shadow", "void", "black", "abyss", "obsidian", "umbra", "eldritch", "horror"):
        hits.append("dark/void")
    # --- Cosmic / space / universe ---
    if _has(b, "cosmos", "cosmic", "space", "galaxy", "star", "universe", "nebula", "planet", "moon", "sun", "celestial", "void"):
        hits.append("cosmic/space")
    # --- Snake / serpent ---
    if _has(b, "snake", "serpent", "viper", "cobra", "naga"):
        hits.append("snake/serpent")
    # --- Business / suit (BIG archetype) ---
    # Exclude "space suit" (space fighters are NOT businessmen)
    if (not _has(b, "space suit") and
            _has(b, "suit", "business", "briefcase", "tie", "office", "man in a suit")):
        hits.append("businessman")
    # --- Toon / cartoon / jester ---
    if _has(b, "cartoon", "toon", "jester", "clown", "anime"):
        hits.append("cartoon/toon")
    # --- Skeleton / undead / lich / ghost ---
    if _has(b, "skeleton", "skull", "undead", "lich", "zombie", "ghost", "wraith", "phantom", "specter", "bone", "necromanc"):
        hits.append("undead/skeleton")
    # --- Water / sea / ice / frost ---
    if _has(b, "water", "sea", "ocean", "tide", "wave", "ice", "frost", "snow", "glacier", "cryo", "icey", "frozen", "aquatic", "kraken", "leviathan", "abyssal"):
        hits.append("water/ice")
    # --- Nature / plant / forest / fungus ---
    if _has(b, "plant", "tree", "forest", "vine", "leaf", "flower", "mushroom", "fungus", "moss", "root", "wood", "ent", "nature", "thorn"):
        hits.append("nature/plant")
    # --- Insect / bug / spider ---
    if _has(b, "insect", "bug", "spider", "wasp", "bee", "beetle", "ant", "mantis", "scorpion", "crab", "lobster", "arthropod"):
        hits.append("insect/arachnid")
    # --- Beast / animal / wolf / lion / bear / bull ---
    if _has(b, "wolf", "lion", "tiger", "bear", "bull", "minotaur", "beast", "animal", "jackal", "anubis", "pharaoh", "egypt", "mummy", "canine", "feline"):
        hits.append("beast/animal")
    # --- Lightning / storm / thunder ---
    if _has(b, "lightning", "thunder", "storm", "electr", "zap", "thunderbolt"):
        hits.append("lightning/storm")
    # --- Smoke / gas / mist / fog ---
    if _has(b, "smoke", "gas", "mist", "fog", "haze", "vapor", "cloud", "smog"):
        hits.append("smoke/mist")
    # --- Crystal / gem / gold / treasure ---
    if _has(b, "crystal", "gem", "diamond", "emerald", "ruby", "gold", "jewel", "prism"):
        hits.append("crystal/gem")
    # --- Clock / time ---
    if _has(b, "clock", "time", "hourglass", "watch", "temporal"):
        hits.append("time/clock")
    # --- Mirror / glass / reflection ---
    if _has(b, "mirror", "glass", "reflect", "shard", "fragment", "crystal"):
        hits.append("mirror/glass")
    # --- Music / sound / instrument ---
    if _has(b, "music", "guitar", "trumpet", "horn", "drum", "instrument", "lute", "harp", "violin"):
        hits.append("music/sound")
    # --- Mummy / egypt ---
    if _has(b, "mummy", "egypt", "pharaoh", "anubis", "hieroglyph", "sarcophagus"):
        hits.append("mummy/egypt")

    # Fallback: pure "human" with nothing else special
    if not hits:
        if kws.get("human") or _has(b, "man", "woman", "person", "human", "character"):
            hits.append("plain-human")
        else:
            hits.append("unclassifiable")

    return hits


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    fighters = data.get("results", [])
    print("=" * 76)
    print("  ARCHETYPE COVERAGE MAP  (%d fighters analyzed)" % len(fighters))
    print("=" * 76)

    # Classify every fighter
    covered = defaultdict(list)      # archetype -> [fighters with >=5 wins]
    seen_low = defaultdict(int)      # archetype -> count of <5 win fighters
    all_fams = defaultdict(list)     # archetype -> all fighters

    for r in fighters:
        blip = r.get("blip", "")
        kws = r.get("kws", {})
        name = r.get("name", "?")
        wins = r.get("wins", 0)
        fams = classify(blip, kws, name)
        for fam in fams:
            all_fams[fam].append((name, wins, blip))
            if wins >= 5:
                covered[fam].append((name, wins, blip))
            else:
                seen_low[fam] += 1

    # ------------------------------------------------------------------
    print("\n[1] COVERED ARCHETYPES (>=5 wins) -- proven in the arena")
    print("-" * 76)
    order = sorted(covered.keys(), key=lambda k: -len(covered[k]))
    for fam in order:
        members = covered[fam]
        top = sorted(members, key=lambda x: -x[1])[:5]
        names = ", ".join(f"{n} ({w})" for n, w, _ in top)
        print(f"  {fam:22s} {len(members):3d} fighters  e.g. {names}")

    # ------------------------------------------------------------------
    print("\n[2] ARCHETYPES SEEN BUT NEVER PROVEN (all <5 wins)")
    print("-" * 76)
    partial = {k: v for k, v in seen_low.items() if k not in covered}
    for fam in sorted(partial.keys()):
        print(f"  {fam:22s} {partial[fam]:3d} fighters tried, none reached 5 wins")

    # ------------------------------------------------------------------
    print("\n[3] COMPLETELY UNCOVERED ARCHETYPES (never seen at all)")
    print("-" * 76)
    # Hard-coded candidate families that the classifier checks for
    all_possible = [
        "water/ice", "nature/plant", "insect/arachnid", "mummy/egypt",
        "time/clock", "mirror/glass", "music/sound", "lightning/storm",
        "undead/skeleton", "smoke/mist", "beast/animal", "crystal/gem",
        "businessman", "cartoon/toon",
    ]
    for fam in all_possible:
        in_high = len(covered.get(fam, []))
        in_low = seen_low.get(fam, 0)
        if in_high >= 3:
            status = "PROVEN"
        elif in_high >= 1:
            status = "SEEN-LOW"
        elif in_low > 0:
            status = "TRIED-LOW"
        else:
            status = "NEVER SEEN"
        print(f"  {fam:22s} high={in_high:2d} low={in_low:2d}   [{status}]")

    # ------------------------------------------------------------------
    print("\n[4] TOP 25 WINNERS -- what archetypes do the BEST actually use?")
    print("-" * 76)
    top25 = sorted(fighters, key=lambda x: -x.get("wins", 0))[:25]
    for r in top25:
        fams = classify(r.get("blip", ""), r.get("kws", {}), r.get("name", ""))
        print(f"  {r.get('wins',0):2d}w  {r.get('name','?')[:40]:40s} -> {', '.join(fams)}")


if __name__ == "__main__":
    main()
