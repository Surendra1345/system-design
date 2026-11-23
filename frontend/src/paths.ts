export interface Path { id: string; title: string; goal: string; who: string; lessons: string[] }

// Curated routes through the course. Lessons can still be taken in any order.
export const PATHS: Path[] = [
  { id: "zero", title: "From zero", goal: "Understand what happens behind every app, then grow a system from one user to a million.", who: "You are new to this and want a solid base.", lessons: ["journey", "numbers", "lb", "cache", "queue", "db", "scale"] },
  { id: "interview", title: "Ace the interview", goal: "Learn the routine and practise the classic design questions with real numbers.", who: "You have an interview coming and want to answer calmly.", lessons: ["interview", "req", "estimate", "urlshort", "feed", "chat", "kvstore", "ecommerce"] },
  { id: "build", title: "Build and run my product", goal: "Go from idea to a deployed, observable, secure service.", who: "You are building something real and want it to survive users.", lessons: ["mvp", "backend", "db", "auth", "deploy", "observe", "resil", "scale"] },
  { id: "distributed", title: "Distributed systems, the hard part", goal: "Replication, transactions, consensus, clocks and the CAP trade-off, all by experiment.", who: "You know the basics and want depth on what makes distributed systems hard.", lessons: ["repl", "tx", "cap", "consensus", "clocks", "kvstore"] },
];

// One line that says what you will do, for the lessons that have a hands-on lab.
export const LAB_HOOKS: Record<string, string> = {
  lb: "Watch big requests bury one server, then fix it with the right algorithm.",
  cache: "Make a database collapse when every cached item expires at once.",
  cdn: "Place servers on a world map and watch delay fall for each region.",
  queue: "Send a poison message and see how one bad job can block everyone.",
  shard: "Add a shard and see how many of your keys have to move.",
  ratelimiter: "Stop a bot without locking out a whole office.",
  resil: "Turn a small outage into a big one with careless retries.",
  serverless: "Survive a flash sale without paying for idle servers.",
  repl: "Lose a user's change by reading from the wrong copy.",
  tx: "Make a Like counter lose likes, then stop it.",
  consensus: "Cut the network and watch two leaders fight.",
  clocks: "See a newer edit lose to an older clock.",
  cap: "Split the network and choose what breaks.",
  journey: "Shave milliseconds off a page load by removing round trips.",
  slo: "Spend an error budget and decide who gets paged at 3 a.m.",
  deploy: "Ship a bad release and count how many users it hurts.",
  streaming: "Pick the wrong key and watch one partition drown.",
  engines: "Choose B-tree or LSM-tree and watch what the disk has to do.",
  micro: "Add services to a chain and watch its reliability fall.",
};
