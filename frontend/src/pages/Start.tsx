import { Link } from "react-router-dom";

const STAGES = [
  { who: "10 customers", shop: "One person takes orders, cooks and washes up.", sys: "One server and one database. It is simple, and that is the right choice.", lesson: "mvp" },
  { who: "10,000 customers", shop: "You hire a host to direct people, keep popular dishes ready on the counter, and add a second cook.", sys: "A load balancer, several servers, a cache for popular answers.", lesson: "scale" },
  { who: "10 million customers", shop: "Many kitchens in many cities, copies of the recipe book, and order tickets so nobody waits at the till.", sys: "Replicated and sharded databases, queues, CDNs in many regions.", lesson: "shard" },
];

const BLOCKS = [
  { name: "Server", does: "The cook", text: "Runs your code and answers each request.", lesson: "journey" },
  { name: "Database", does: "The pantry and the ledger", text: "Stores data safely so it is still there tomorrow.", lesson: "db" },
  { name: "Cache", does: "Ready-made dishes on the counter", text: "Remembers recent answers so the slow database is asked less often.", lesson: "cache" },
  { name: "Load balancer", does: "The host who seats guests", text: "Sends each request to a free, healthy server.", lesson: "lb" },
  { name: "Queue", does: "The ticket rail in the kitchen", text: "Holds slow jobs so the user does not wait, and cooks work through them.", lesson: "queue" },
  { name: "CDN", does: "A branch in every city", text: "Keeps copies of files near each user so they load quickly.", lesson: "cdn" },
  { name: "Replication", does: "Copies of the recipe book", text: "Keeps the same data on several machines for safety and speed.", lesson: "repl" },
  { name: "Sharding", does: "Several pantries", text: "Splits a huge dataset across machines when one cannot hold it.", lesson: "shard" },
];

const QUESTIONS = [
  { q: "How big will it get?", a: "How many users, requests per second and gigabytes of data. A design for a hundred users is very different from one for a hundred million." },
  { q: "What must never break?", a: "Losing a bank transfer is a disaster. Losing a like is not. Knowing which is which decides how careful the design must be." },
  { q: "What can be a little slow or out of date?", a: "A news feed can be a few seconds behind. A seat booking cannot. Relaxing the right things makes systems cheaper and faster." },
  { q: "What will it cost, and what happens when a part fails?", a: "Every extra machine costs money, and every machine can fail. Good designs keep working when a part breaks." },
];

const FIRST = [
  ["journey", "What happens when you open a URL", "Follow one request from your browser to a database and back. Every later idea plugs into this path."],
  ["numbers", "Latency, throughput and availability", "The few numbers every designer keeps in their head."],
  ["lb", "Load balancing", "Your first scaling tool, with a simulation where you watch requests being shared out."],
  ["cache", "Caching", "The cheapest way to make a system faster, and the source of its trickiest bugs."],
  ["queue", "Queues and asynchronous work", "Take slow work off the request path."],
  ["db", "Choosing a database", "Pick a store by how your data is used, not by fashion."],
  ["scale", "Scaling from 1 to 1 million users", "See the order in which real products add each building block."],
];

export function Start() {
  return (
    <>
      <h1>What is system design?</h1>
      <p className="sub">System design is deciding how the parts of a software product fit together, so that it keeps working when many people use it.</p>
      <p>Anyone can build an app that works for one person on one laptop. System design is the skill of making it work for a million people at once: fast, without losing their data, and without a huge bill. It is also what interviewers at technology companies ask about, and what engineers do every day when a product grows.</p>

      <h2>Think of a lemonade stand that grows into a restaurant chain</h2>
      <p className="lead">The ideas are the same as running a food business. Only the names change.</p>
      <div className="howto">
        {STAGES.map(s => (
          <div className="card" key={s.who}>
            <span className="pill blue">{s.who}</span>
            <p style={{ margin: "10px 0 4px" }}><b>In the shop:</b> {s.shop}</p>
            <p style={{ margin: "0 0 8px" }}><b>In software:</b> {s.sys}</p>
            <Link to={`/lesson/${s.lesson}`}>Read the lesson →</Link>
          </div>
        ))}
      </div>

      <h2>A small example you will see everywhere</h2>
      <p className="lead">When you open a website, your request usually travels like this:</p>
      <div className="flow">
        <span className="node">You</span><span className="arr" aria-hidden="true">→</span>
        <span className="node">CDN</span><span className="arr" aria-hidden="true">→</span>
        <span className="node">Load balancer</span><span className="arr" aria-hidden="true">→</span>
        <span className="node">App servers</span><span className="arr" aria-hidden="true">→</span>
        <span className="node">Cache</span><span className="arr" aria-hidden="true">→</span>
        <span className="node">Database</span>
      </div>
      <p>Each box exists to solve one problem. The CDN makes files load nearby. The load balancer shares the work. The cache avoids repeating slow work. The database keeps the data safe. This course teaches each one, then how they fail and how to fix them.</p>

      <h2>The building blocks, in plain words</h2>
      <div className="grid">
        {BLOCKS.map(b => (
          <Link to={`/lesson/${b.lesson}`} className="card lcard" key={b.name}>
            <div><h4>{b.name} <span className="muted">· {b.does}</span></h4><small className="muted">{b.text}</small></div>
          </Link>
        ))}
      </div>

      <h2>Four questions every design answers</h2>
      <div className="howto">
        {QUESTIONS.map((x, i) => (
          <div className="card" key={x.q}><span className="num">{i + 1}</span><b>{x.q}</b><span className="muted">{x.a}</span></div>
        ))}
      </div>
      <p>There is rarely one right answer. System design is about trade-offs: you give up something to gain something, and you explain why. That is why this course shows you what each choice costs.</p>

      <h2>How this site teaches it</h2>
      <div className="howto">
        <div className="card"><span className="num">1</span><b>Read the plain-English note</b><span className="muted">Every lesson opens with what it is, why we use it, and when to use it or not.</span></div>
        <div className="card"><span className="num">2</span><b>Play with it</b><span className="muted">Change the settings of a real mechanism, such as a load balancer or a cache, and watch what happens. You earn stars for good results.</span></div>
        <div className="card"><span className="num">3</span><b>Go deeper</b><span className="muted">Worked numbers, a real company example, common mistakes and further reading.</span></div>
        <div className="card"><span className="num">4</span><b>Check yourself</b><span className="muted">A short question at the end. Stuck on a word? The <Link to="/glossary">glossary</Link> explains every term.</span></div>
      </div>
      <p className="lead">You need no experience with distributed systems, only a little programming. There is no schedule: spend as long on each topic as you like.</p>

      <h2>Where to start</h2>
      <p className="lead">Take these seven in order, then explore the rest of the course in any order.</p>
      <ol className="startlist">
        {FIRST.map(([id, title, why]) => (
          <li key={id}><Link to={`/lesson/${id}`}><b>{title}</b></Link><span className="muted"> {why}</span></li>
        ))}
      </ol>
      <div className="row2" style={{ marginTop: 18 }}>
        <Link className="btn pri" to="/lesson/journey">Start the first lesson</Link>
        <Link className="btn" to="/glossary">Open the glossary</Link>
      </div>
    </>
  );
}
