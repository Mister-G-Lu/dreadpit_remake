const base = () => import.meta.env.BASE_URL || "/";
const img = (file) => `${base()}demo/${file}`;

const fighters = [
  { id: "forge", name: "Forge Colossus", prompt: "Giant walking furnace of black iron. White-hot molten core. Anvil hammers. Orange eye slits.", filename: "forge.jpg", wins: 6, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: "hook", name: "The Hook", prompt: "Gaunt hunter in monster pelts. Hooked chain. One glowing eye. Trophies, no armor.", filename: "hook.jpg", wins: 5, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: "wrath", name: "Wrath Infernal", prompt: "Winged entity wreathed in black orange flame. Obsidian skull. Molten claws.", filename: "wrath.jpg", wins: 4, status: "living", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z" },
  { id: "forge2", name: "Cinder Choir", prompt: "Furnace giant, cracked iron hymn plates, choir of vents screaming heat.", filename: "forge2.jpg", wins: 2, status: "living", owner: "kiln", createdAt: "2026-08-02T00:00:00.000Z" },
  { id: "vatican2", name: "Holy Rotary", prompt: "Executioner duster, spinning blessed barrels, red-lens mask.", filename: "vatican2.jpg", wins: 1, status: "living", owner: "kiln", createdAt: "2026-08-03T00:00:00.000Z" },
  { id: "hook2", name: "Pelthook", prompt: "Lean trophy-hunter, chain between both hands, iron hook for a palm.", filename: "hook2.jpg", wins: 1, status: "living", owner: "kiln", createdAt: "2026-08-03T00:00:00.000Z" },
  { id: "wrath2", name: "Ash Seraph", prompt: "Burnt-wing seraph of cinder and horn, standing in its own weather.", filename: "wrath2.jpg", wins: 0, status: "living", owner: "kiln", createdAt: "2026-08-04T00:00:00.000Z" },
  { id: "vatican", name: "Vatican Gun", prompt: "Hooded executioner. Six-barrel gatling. Holy water drums. Crucifix on the stock.", filename: "vatican.jpg", wins: 2, status: "dead", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z", diedAt: "2026-08-20T01:00:00.000Z", killerId: "hook", killerName: "The Hook" },
  { id: "reclaimer", name: "The Reclaimer", prompt: "Salvage giant of rusted plate and cable, one furnace eye, wrecking hook.", filename: "reclaimer.jpg", wins: 1, status: "dead", owner: "kiln", createdAt: "2026-08-01T00:00:00.000Z", diedAt: "2026-08-20T01:00:00.000Z", killerId: "wrath", killerName: "Wrath Infernal" },
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
    judge: "lesser-eye",
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
    judge: "lesser-eye",
    judgedAt: "2026-08-20T01:00:08.000Z",
    winnerId: "wrath",
    narration:
      "Reclaimer drags a wrecking hook through slag weather. Wrath Infernal does not step back. Wings become a kiln door slamming. Rust remembers it was once ore; ore remembers fire. The salvage giant folds, a cathedral of scrap going quiet.",
    left: { id: "wrath", name: "Wrath Infernal", image: img("wrath.jpg"), wins: 4 },
    right: { id: "reclaimer", name: "The Reclaimer", image: img("reclaimer.jpg"), wins: 1 },
  },
];

const nextBatch = new Date(Date.now() + 24 * 3600 * 1000).toISOString();

export const demoState = {
  maxRoster: 256,
  sparksMax: 10,
  batchSize: 10,
  batchIntervalMs: 3600000,
  gemini: false,
  static: true,
  living,
  gate: [],
  deadCount: dead.length,
  admittedToday: 0,
  me: null,
  round: {
    id: "demo-round",
    number: 12,
    status: "complete",
    startedAt: "2026-08-20T01:00:00.000Z",
    completedAt: "2026-08-20T01:00:10.000Z",
    batchIndex: 1,
    nextBatchAt: nextBatch,
    notes: "bye:Forge Colossus",
    matchesTotal: 2,
    matchesDone: 2,
  },
  matches,
};

export const demoAsh = { dead };
export const demoFighters = Object.fromEntries(fighters.map((f) => [f.id, { fighter: pub(f), fights: matches.filter((m) => m.left.id === f.id || m.right.id === f.id).map((m) => ({ id: m.id, round: 12, status: m.status, winnerId: m.winnerId, vs: m.left.id === f.id ? m.right.id : m.left.id })) }]));
export const demoMatches = Object.fromEntries(matches.map((m) => [m.id, { match: m }]));
