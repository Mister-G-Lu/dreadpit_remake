const base = () => import.meta.env.BASE_URL || "/";
const img = (file) => `${base()}demo/${file}`;

const CESAR_ID = "63a63214-d241-425d-8b7f-87bfddeebe58";
const MANTIS_ID = "785d5c98-7861-41ce-b6e6-43aaa96322ee";
const GEMINI_FIGHT_ID = "0bb566e7-d165-4686-b102-554bc272a722";

const fighters = [
  { id: "forge", name: "Forge Colossus", prompt: "Giant walking furnace of black iron. White-hot molten core. Anvil hammers. Orange eye slits.", filename: "forge.jpg", wins: 6, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: "hook", name: "The Hook", prompt: "Gaunt hunter in monster pelts. Hooked chain. One glowing eye. Trophies, no armor.", filename: "hook.jpg", wins: 5, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: "wrath", name: "Wrath Infernal", prompt: "Winged entity wreathed in black orange flame. Obsidian skull. Molten claws.", filename: "wrath.jpg", wins: 4, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: CESAR_ID, name: "Relentless Cesar Grist", prompt: null, filename: "cesar-grist.webp", wins: 8, status: "living", owner: "9spaceking", createdAt: "2026-07-24T12:13:08.058Z", archived: true },
  { id: "forge2", name: "Cinder Choir", prompt: "Furnace giant, cracked iron hymn plates, choir of vents screaming heat.", filename: "forge2.jpg", wins: 2, status: "living", owner: "kiln", createdAt: "2026-08-02T00:00:00.000Z" },
  { id: "vatican2", name: "Holy Rotary", prompt: "Executioner duster, spinning blessed barrels, red-lens mask.", filename: "vatican2.jpg", wins: 1, status: "living", owner: "kiln", createdAt: "2026-08-03T00:00:00.000Z" },
  { id: "hook2", name: "Pelthook", prompt: "Lean trophy-hunter, chain between both hands, iron hook for a palm.", filename: "hook2.jpg", wins: 1, status: "living", owner: "kiln", createdAt: "2026-08-03T00:00:00.000Z" },
  { id: "wrath2", name: "Ash Seraph", prompt: "Burnt-wing seraph of cinder and horn, standing in its own weather.", filename: "wrath2.jpg", wins: 0, status: "living", owner: "kiln", createdAt: "2026-08-04T00:00:00.000Z" },
  { id: "vatican", name: "Vatican Gun", prompt: "Hooded executioner. Six-barrel gatling. Holy water drums. Crucifix on the stock.", filename: "vatican.jpg", wins: 2, status: "dead", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z", diedAt: "2026-08-20T01:00:00.000Z", killerId: "hook", killerName: "The Hook" },
  { id: "reclaimer", name: "The Reclaimer", prompt: "Salvage giant of rusted plate and cable, one furnace eye, wrecking hook.", filename: "reclaimer.jpg", wins: 1, status: "dead", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z", diedAt: "2026-08-20T01:00:00.000Z", killerId: "wrath", killerName: "Wrath Infernal" },
  { id: MANTIS_ID, name: "Claw Mantis", prompt: null, filename: "claw-mantis.webp", wins: 1, status: "dead", owner: "Grimar", createdAt: "2026-05-15T23:51:41.155Z", diedAt: "2026-07-25T12:00:47.047Z", killerId: CESAR_ID, killerName: "Relentless Cesar Grist", archived: true },
];

function pub(f) {
  return {
    ...f,
    image: img(f.filename),
    sealed: f.status === "dead",
    prompt: f.status === "dead" ? null : f.prompt,
  };
}

const living = fighters.filter((f) => f.status === "living").map(pub);
const dead = fighters.filter((f) => f.status === "dead").map(pub);

const matches = [
  {
    id: "m1",
    seq: 1,
    batch: 1,
    status: "done",
    margin: "clear",
    judge: "demo",
    judgedAt: "2026-08-20T01:00:04.000Z",
    winnerId: "hook",
    narration:
      "The Eye does not blink. Vatican Gun opens with a blessed roar; brass casings become a halo that never quite lands. The Hook is already inside the noise, chain kissing the mask, iron replacing a throat. The rotary seizes. Clay remembers the shape of a hunter and forgets the shape of a church.",
    left: { id: "vatican", name: "Vatican Gun", image: img("vatican.jpg"), wins: 2 },
    right: { id: "hook", name: "The Hook", image: img("hook.jpg"), wins: 5 },
  },
  {
    id: "m2",
    seq: 2,
    batch: 1,
    status: "done",
    margin: "narrow",
    judge: "demo",
    judgedAt: "2026-08-20T01:00:08.000Z",
    winnerId: "wrath",
    narration:
      "Reclaimer drags a wrecking hook through slag weather. Wrath Infernal does not step back. Wings become a kiln door slamming. Rust remembers it was once ore; ore remembers fire. The salvage giant folds, a cathedral of scrap going quiet.",
    left: { id: "wrath", name: "Wrath Infernal", image: img("wrath.jpg"), wins: 4 },
    right: { id: "reclaimer", name: "The Reclaimer", image: img("reclaimer.jpg"), wins: 1 },
  },
  {
    // Verbatim Gemini verdict preserved in cesar_fight_details.json, paired
    // with the two original portraits already archived in this repository.
    id: GEMINI_FIGHT_ID,
    seq: 3,
    batch: 1,
    status: "done",
    margin: null,
    judge: "gemini",
    source: "archived-gemini",
    judgedAt: "2026-07-25T12:00:47.047Z",
    winnerId: CESAR_ID,
    reasoning:
      "Relentless Cesar Grist possesses heavy plating and a powerful energy staff that projects a coherent beam. Claw Mantis, despite its agility and multiple limbs, lacks any visible means to penetrate Cesar Grist's defenses or withstand his energy attack. The Mantis's fragility and exposed body prove its undoing.",
    narration:
      "Claw Mantis clicks and darts, its segmented legs scrabbling against the arena floor, a green blur against the dark. It seeks an opening, an unarmored seam on Relentless Cesar Grist. Cesar Grist simply steps forward, shield bright, the energy beam from his staff carving a line of light through the air. The Mantis leaps, trying to get inside, but the beam catches a foreleg, snapping it clean. It shrieks, a high-pitched sound of insect agony, losing balance. Cesar Grist does not hesitate. His shield slams down, crushing the Mantis into the floor, a sickening crunch echoing in the void. A waste of good chitin, really.",
    left: { id: MANTIS_ID, name: "Claw Mantis", image: img("claw-mantis.webp"), wins: 1 },
    right: { id: CESAR_ID, name: "Relentless Cesar Grist", image: img("cesar-grist.webp"), wins: 8 },
  },
];

const completedAt = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
const nextFiringAt = new Date(Date.now() + 22 * 3600 * 1000).toISOString();

export const demoState = {
  maxRoster: 256,
  sparksMax: 10,
  batchSize: 10,
  batchIntervalMs: 3600000,
  gemini: true,
  static: true,
  nextFiringAt,
  living,
  gate: [],
  deadCount: dead.length,
  admittedToday: 0,
  me: null,
  round: {
    id: "demo-round",
    number: 12,
    status: "complete",
    startedAt: new Date(new Date(completedAt).getTime() - 3600 * 1000).toISOString(),
    completedAt,
    batchIndex: 1,
    nextBatchAt: null,
    notes: null,
    matchesTotal: matches.length,
    matchesDone: matches.length,
  },
  matches,
};

export const demoAsh = { dead };

function fightSummary(match, fighter) {
  const opponent = match.left.id === fighter.id ? match.right : match.left;
  return {
    id: match.id,
    round: 12,
    status: match.status,
    winnerId: match.winnerId,
    foughtAt: match.judgedAt,
    source: match.source,
    opponent: {
      id: opponent.id,
      name: opponent.name,
      image: opponent.image,
    },
  };
}

export const demoFighters = Object.fromEntries(
  fighters.map((fighter) => [
    fighter.id,
    {
      fighter: pub(fighter),
      fights: matches
        .filter((match) => match.left.id === fighter.id || match.right.id === fighter.id)
        .map((match) => fightSummary(match, fighter)),
    },
  ])
);
export const demoMatches = Object.fromEntries(matches.map((match) => [match.id, { match }]));
