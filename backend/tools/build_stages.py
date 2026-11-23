"""Writes app/content/stages.json: the 10-stage guided path, piloted on three lessons (lb, cache, queue).
Edit the data below and re-run:  python -m tools.build_stages

Stages, in order: analogy, why it exists, how it works, visualise (the lab), the maths, variations, failures,
alternatives, independent design, proof. Proof questions are practice only: they never award XP, so the
answers may ship to the browser."""
import json
from pathlib import Path

STAGE_IDS = ["analogy", "why", "how", "visualise", "math", "variations", "failures", "alternatives", "design", "proof"]
STAGE_TITLES = {
    "analogy": "1. An everyday picture", "why": "2. Why it exists", "how": "3. How it works", "visualise": "4. See it move",
    "math": "5. Work the numbers", "variations": "6. Change the problem", "failures": "7. How it breaks",
    "alternatives": "8. Other options", "design": "9. Design it yourself", "proof": "10. Prove it",
}


def Q(q, options, answer, why):
    return {"q": q, "options": options, "answer": answer, "why": why}


LESSONS = {
 # ------------------------------------------------------------------ load balancing
 "lb": {
  "analogy": "<p>A supermarket opens one till or six. A person at the entrance points each arriving shopper to a till with a short line, and never to a closed one. That person is the <b>load balancer</b>. The shoppers are requests and the tills are servers.</p>",
  "why": "<p>One server has a hard ceiling and is a single point of failure: if it stops, the whole site stops. Several identical servers behind a load balancer give you more total capacity, and when one dies the others keep serving.</p><p>It also lets you deploy without downtime: take one server out, update it, put it back, repeat.</p>",
  "how": "<ol><li>Clients send every request to one address, the load balancer.</li><li>It picks a server using an <b>algorithm</b>: round robin (take turns), least connections (pick the least busy), or hashing (the same client goes to the same server).</li><li>It runs <b>health checks</b> and stops sending traffic to a server that fails them.</li><li>When you remove a server on purpose it <b>drains</b>: no new requests, but current ones finish.</li></ol><p>This only works well if servers are <b>stateless</b>: any server can answer any request because shared data lives in a database or cache, not in one server's memory.</p>",
  "visualise": "<p>Open the lab below and watch requests flow. Before you press play, <b>predict</b>: with one slow server and round robin, will that server's line grow or stay level? Then run it and check.</p>",
  "math": {"intro": "<p>You expect <b>800 requests per second</b>. One server handles <b>250 per second</b>.</p>",
           "steps": ["Servers needed for load alone: 800 / 250 = 3.2, so at least <b>4</b> servers.", "With 4 servers each takes 800 / 4 = <b>200 per second</b>, which is 80% of its capacity.", "Now one server crashes. The 3 left must take 800 / 3 = <b>267 per second</b>, which is 107% of capacity. They overload and may crash too.", "Fix: plan <b>N+1</b>. With 5 servers, losing one leaves 4 x 250 = 1000 per second, which covers 800."],
           "takeaway": "Capacity planning means surviving a failure, not just handling the average."},
  "variations": ["<b>Bigger requests.</b> If a few requests take 1000 times longer than the rest, round robin still hands them out evenly, so one unlucky server gets stuck. Least connections spreads the real work better.", "<b>A server dies.</b> The load balancer must notice (health check) and stop sending to it. The interval matters: a 30 second check means 30 seconds of errors.", "<b>Sticky sessions.</b> Pinning a user to one server breaks the even spread and loses their session when that server dies. Move session data to a shared store instead."],
  "failures": ["<b>Cascading overload:</b> one server fails, the rest take its share, they overload and fail in turn.", "<b>The balancer itself fails:</b> it needs a backup, or the single point of failure has only moved.", "<b>Slow health checks:</b> traffic keeps flowing to a dead server until the check notices.", "<b>Uneven long requests</b> pile up on one server under round robin."],
  "alternatives": [["Round robin", "Simple, fair when requests are alike", "Ignores how busy each server is"], ["Least connections", "Adapts to uneven request length", "Needs the balancer to track connections"], ["Hash of client or key", "Same user reaches the same server, useful for local caches", "Uneven spread, and a server change moves many users"], ["DNS round robin", "No extra hardware", "Cannot see health, clients cache answers"]],
  "design": {"prompt": "A photo site expects 1,200 requests per second at peak. Each server handles 300 per second. It must survive any single server failing. How many servers do you run, and what else do you set up?",
             "checks": ["Load alone needs 1200 / 300 = 4 servers", "Add one more for failure: 5 servers, so 4 x 300 = 1200 still covers peak", "Health checks with a short interval so a dead server is removed quickly", "Stateless servers, with sessions in a shared store", "A second load balancer so the balancer is not a single point of failure"]},
  "proof": [
   Q("Peak traffic is 900 requests per second, one server handles 300, and you must survive one server failing. How many servers?", ["2", "3", "4", "5"], 2, "900 / 300 = 3 servers carry the load. One more so that losing a server still leaves 3, so 4 in total."),
   Q("A few requests are very slow and others are instant. Which algorithm copes best?", ["Round robin, because it is fair in turns", "Always the first server", "Choose a server at random every time", "Least connections, because it sees who is busy"], 3, "Least connections notices the server stuck on slow requests and sends new work elsewhere. Round robin only counts turns."),
   Q("You add sticky sessions to keep users logged in. What is the main cost?", ["Load spreads less evenly, and a server failure logs users out", "Requests become slower on every server", "The load balancer needs more memory", "Health checks stop working"], 0, "Pinning users unbalances the load and ties their session to one server. A shared session store avoids both."),
  ],
  "tutor": ["Explain why round robin fails when some requests are much slower than others.", "Quiz me: how many servers do I need for 2,000 requests per second if each handles 400 and I must survive one failure?", "Give me a case where sticky sessions are the right choice."],
 },
 # ------------------------------------------------------------------ caching
 "cache": {
  "analogy": "<p>You keep your most-used spices on the counter and the rest in the cupboard down the hall. Grabbing from the counter takes a second, fetching from the cupboard takes a minute. The counter is the <b>cache</b>, the cupboard is the <b>database</b>.</p>",
  "why": "<p>A database read can cost tens of milliseconds and the database can only serve so many at once. Many requests ask for the same few things. Keeping recent answers in fast memory makes those reads quick and takes load off the database, which often is what limits the whole system.</p>",
  "how": "<ol><li>The app asks the cache first.</li><li><b>Hit:</b> the answer is there, return it.</li><li><b>Miss:</b> read the database, store the answer in the cache, return it.</li><li>When data changes, <b>invalidate</b> (delete) or update the cached copy, or let it expire after a <b>TTL</b>.</li><li>When memory is full, an <b>eviction</b> policy such as LRU removes the least recently used entry.</li></ol>",
  "visualise": "<p>Open the lab below and watch hits and misses as you change the cache size. <b>Predict first</b>: if you double the cache size, will the hit rate double? Run it and see.</p>",
  "math": {"intro": "<p>A cache read takes <b>1 ms</b>, a database read takes <b>50 ms</b>, and the site gets <b>10,000 reads per second</b>.</p>",
           "steps": ["At a 90% hit ratio, average latency is 0.9 x 1 + 0.1 x 50 = 0.9 + 5 = <b>5.9 ms</b>.", "The database sees the misses: 10,000 x 0.1 = <b>1,000 reads per second</b>.", "At 95%: latency is 0.95 x 1 + 0.05 x 50 = <b>3.45 ms</b>, and the database sees 10,000 x 0.05 = <b>500 per second</b>.", "Going from 90% to 95% looks small, but it <b>halves the database load</b>."],
           "takeaway": "The miss rate, not the hit rate, decides how hard the database works."},
  "variations": ["<b>Different data.</b> A product page can be seconds stale. A bank balance cannot: caching it risks showing wrong money, so read it from the source of truth.", "<b>Different traffic.</b> If every request asks for a different key, the hit ratio collapses and the cache only adds cost.", "<b>Different TTL.</b> A short TTL keeps data fresh but lowers the hit ratio. A long TTL does the opposite. Choose by how wrong the data may be, and for how long."],
  "failures": ["<b>Stampede:</b> a hot key expires and hundreds of requests miss at once and hit the database together. Fix with a lock so one request refills it, or refresh early.", "<b>Stale data:</b> the database changed but the cache still holds the old value. Fix by invalidating on write, or accept a short TTL.", "<b>Cold start:</b> an empty cache after a restart sends everything to the database. Warm it, or ramp traffic up slowly.", "<b>Cache outage:</b> if the cache dies the database may not survive the full load. Plan for it."],
  "alternatives": [["Cache-aside", "Simple: app reads cache, fills it on a miss", "First read is slow, data can be stale"], ["Write-through", "Cache and database always agree", "Every write is slower"], ["Write-back", "Very fast writes", "Data is lost if the cache dies before it is flushed"], ["A CDN or browser cache", "Closer to the user, no server work at all", "Harder to invalidate quickly"]],
  "design": {"prompt": "A news site gets 20,000 reads per second for articles that change a few times a day. Reads from the database take 40 ms. Design the caching: what do you cache, what TTL, and how do you stop a stampede when a front page expires?",
             "checks": ["Cache-aside for article reads, since reads far outnumber writes", "A TTL of minutes, or invalidate when an editor publishes", "A lock or early refresh on the front page so one request refills it", "Check the hit ratio: at 95% the database sees 1,000 reads per second, not 20,000", "A plan for the cache being down or empty"]},
  "proof": [
   Q("Cache reads take 2 ms, database reads take 100 ms, the hit ratio is 80%. What is the average read time?", ["16 ms", "20 ms", "21.6 ms", "40 ms"], 2, "0.8 x 2 + 0.2 x 100 = 1.6 + 20 = 21.6 ms."),
   Q("Traffic is 5,000 reads per second and the hit ratio rises from 90% to 98%. What happens to database reads?", ["From 500 to 100 per second", "From 500 to 450 per second", "From 4,500 to 4,900 per second", "They stay the same"], 0, "Misses fall from 10% to 2%: 5,000 x 0.10 = 500, then 5,000 x 0.02 = 100. A fivefold drop."),
   Q("A hot item expires and the site slows badly for a moment. What is this, and the best fix?", ["Cold start, fixed by a larger cache", "Stale data, fixed by a longer TTL", "Eviction, fixed by using LFU", "Stampede, fixed by letting one request refill it"], 3, "Many requests miss together and hit the database. A lock or early refresh lets one request rebuild the entry."),
  ],
  "tutor": ["Explain why raising the hit ratio from 90% to 95% matters so much for the database.", "Quiz me on choosing a TTL for product prices versus a user's bank balance.", "Walk me through a cache stampede step by step."],
 },
 # ------------------------------------------------------------------ queues
 "queue": {
  "analogy": "<p>At a bakery counter you give your order to the cashier, who hands you a ticket and moves on. Bakers fill orders from the pile of tickets when they can. You are not stuck waiting at the counter. The ticket pile is the <b>queue</b>.</p>",
  "why": "<p>Some work is slow: sending email, resizing video, building a report. Making the user wait for it feels broken, and a sudden spike of requests can overwhelm the workers. A queue lets the app answer at once, absorbs spikes, and lets failed jobs be retried later.</p>",
  "how": "<ol><li>A <b>producer</b> puts a job on the queue and returns immediately.</li><li>A <b>worker</b> takes the job. The queue hides it for a <b>visibility timeout</b> while the worker runs.</li><li>If the worker finishes, it <b>acknowledges</b> and the job is deleted.</li><li>If it crashes, the timeout ends and the job reappears for another worker. This is <b>at-least-once</b> delivery, so a job may run twice.</li><li>A job that keeps failing moves to a <b>dead-letter queue</b> so it cannot block the rest.</li></ol><p>Because of repeats, workers should be <b>idempotent</b>: running a job twice has the same result as once.</p>",
  "visualise": "<p>Open the lab below and watch jobs arrive and workers drain them. <b>Predict first</b>: if jobs arrive faster than workers finish them, does the line stay steady or keep growing? Add workers and see.</p>",
  "math": {"intro": "<p>Jobs arrive at <b>100 per second</b>. One worker finishes <b>10 per second</b>. You have <b>4 workers</b>.</p>",
           "steps": ["Capacity is 4 x 10 = <b>40 per second</b>, less than the 100 arriving.", "The backlog grows by 100 - 40 = <b>60 jobs every second</b>.", "To keep up you need 100 / 10 = <b>10 workers</b>. Add headroom, say 12.", "A spike case: 100 per second for 30 seconds, then 20 per second, with 4 workers. Backlog after the spike is 30 x (100 - 40) = <b>1,800 jobs</b>. It drains at 40 - 20 = 20 per second, so it takes 1,800 / 20 = <b>90 seconds</b>."],
           "takeaway": "A queue turns a spike into a delay, but only if workers can eventually catch up."},
  "variations": ["<b>Faster arrivals.</b> More jobs per second means a longer line unless you add workers. Autoscaling on queue length does this automatically.", "<b>A poison message.</b> One job crashes every worker that tries it. Without a dead-letter queue it loops forever and wastes capacity.", "<b>Ordering needed.</b> If steps for one customer must run in order, use an ordering key so one customer's jobs go to one worker, and give up some parallelism."],
  "failures": ["<b>Duplicate processing:</b> a worker finishes but crashes before acknowledging, so the job runs again. Make workers idempotent.", "<b>Poison message:</b> a bad job fails repeatedly. Cap retries, then dead-letter it.", "<b>Backlog that never drains:</b> arrivals stay above capacity, so waiting time grows forever.", "<b>Visibility timeout too short:</b> a slow job reappears while still running, so two workers do it."],
  "alternatives": [["Direct call (synchronous)", "Simple, the user gets the result at once", "Slow work blocks the user, spikes hit the service directly"], ["Queue (one worker per job)", "Absorbs spikes, retries, decouples services", "Delay, duplicates possible, more to operate"], ["Pub/sub or a log (Kafka)", "Many consumers can read the same events and replay them", "Heavier to run, ordering only within a partition"], ["Scheduled batch job", "Simple for work that can wait hours", "Not suitable when results are needed soon"]],
  "design": {"prompt": "A photo app resizes each upload into 4 sizes. Uploads arrive at 50 per second at peak, and each resize job takes 0.5 seconds of one worker. Users should see their photo within a few seconds. How do you design it?",
             "checks": ["Return to the user at once and queue a resize job", "Each worker does 2 jobs per second, so 50 per second needs 25 workers, plus headroom", "Make resizing idempotent so a repeat overwrites the same files", "A dead-letter queue and a retry limit for corrupt images", "Scale workers on queue length so a spike drains quickly"]},
  "proof": [
   Q("Jobs arrive at 60 per second and each worker handles 15 per second. How many workers just keep up?", ["4", "5", "6", "8"], 0, "60 / 15 = 4 workers handle the load exactly. In practice add headroom."),
   Q("A worker finishes a job but crashes before acknowledging. What happens next?", ["The job is lost forever", "The job reappears and may run again", "The queue deletes it anyway", "All workers stop"], 1, "At-least-once delivery means the unacknowledged job returns after the visibility timeout, so the work may repeat. That is why idempotency matters."),
   Q("One malformed job keeps crashing workers and blocks progress. What is the right fix?", ["Add many more workers", "Raise the visibility timeout", "Retry a few times, then move it to a dead-letter queue", "Delete the queue and start again"], 2, "Capping retries and dead-lettering the job keeps healthy work flowing and saves the bad one for a person to inspect."),
  ],
  "tutor": ["Explain at-least-once delivery and why my worker must be idempotent.", "Quiz me: 200 jobs per second arrive and each worker does 25 per second. How many workers, and what if a 60 second spike doubles it?", "When should I use a queue and when a direct call?"],
 },
}


def stage_list(lesson):
    d = LESSONS[lesson]
    out = []
    for sid in STAGE_IDS:
        st = {"id": sid, "title": STAGE_TITLES[sid]}
        v = d.get(sid)
        if sid == "math":
            st.update(intro=v["intro"], steps=v["steps"], takeaway=v["takeaway"])
        elif sid == "variations":
            st["items"] = v
        elif sid == "failures":
            st["items"] = v
        elif sid == "alternatives":
            st["rows"] = v
        elif sid == "design":
            st.update(prompt=v["prompt"], checks=v["checks"])
        elif sid == "proof":
            st["questions"] = v
        else:
            st["body"] = v
        out.append(st)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "content"
    out = {k: {"stages": stage_list(k), "tutor": LESSONS[k]["tutor"]} for k in LESSONS}
    (root / "stages.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote", len(out))


if __name__ == "__main__":
    main()
