"""Content for new lessons: notify, dr."""
from tools.new_lessons_a import FLOW

LESSONS, EXPLAIN, DEEP, INTERVIEW = {}, {}, {}, {}

# ---------------------------------------------------------------------------------------------- notify
LESSONS["notify"] = {
    "id": "notify", "t": "y", "title": "Design a notification system",
    "sum": "Send push, SMS and email reliably, once, at the right time, without overwhelming users or providers.",
    "sec": [
        {"h": "Channels and providers", "b": "<p>You rarely send messages yourself. Push goes through Apple (APNs) and Google (FCM), SMS and email go through providers such as Twilio or Amazon SES. Your system decides <b>who</b> gets <b>what</b> and <b>when</b>, and hands the delivery to the provider. Each provider has its own limits, formats and failure modes, so put each channel behind its own queue and worker.</p>" + FLOW("Event", "Notification service", "Queue per channel", "Worker", "Provider", "Device")},
        {"h": "Preferences, templates and priority", "b": "<p>Before sending, check the user's preferences (opt-outs, quiet hours, channel choice) and fill a template with their language and data. Give messages a priority: a password reset or payment code must not wait behind a marketing campaign of ten million emails, so use separate queues or priority lanes.</p>"},
        {"h": "Reliability: retries and no duplicates", "b": "<p>Providers fail and time out, so workers retry with <b>exponential backoff</b>. Retrying can send the same message twice, so give every notification an <b>idempotency key</b> and have the worker check it before sending. Messages that keep failing go to a dead-letter queue. Record each state (queued, sent, delivered, opened) so you can answer 'did it go out?'.</p>"},
        {"h": "Fan-out and protecting people", "b": "<p>A broadcast to ten million users is a fan-out job: split it into batches, spread them over time, and respect provider rate limits. Add per-user limits too, so that one busy day does not send someone fifty pushes. Webhooks from providers report bounces and unsubscribes, which you must honour.</p>"},
    ],
    "breaks": [
        "A retry sends the same message twice. Use an idempotency key checked before every send.",
        "A marketing blast delays urgent one-time codes. Separate queues by priority.",
        "The provider rate-limits you and the queue explodes. Throttle workers to the provider's limit and spread large batches over time.",
        "Messages go to users who opted out or in the middle of the night. Check preferences and quiet hours at send time, not at queue time.",
        "Bounces and invalid device tokens are ignored, so you keep paying to send to dead addresses. Process provider feedback and remove them.",
    ],
    "quiz": {"q": "Why give each notification an idempotency key?", "o": ["So it is encrypted", "So a retry cannot send the same message twice", "So it is sent faster"], "a": 1, "w": "Retries are needed because providers fail, but a retry after a timeout may repeat a message that actually went through. The key lets the worker detect that and skip it."},
    "projects": False,
}
EXPLAIN["notify"] = {
    "what": "A service that decides who should be told what, then sends push, SMS or email through outside providers.",
    "why": "Sending directly from your app is slow, unreliable and easy to overdo.",
    "use": ["Order updates and receipts", "One-time codes and security alerts", "Campaigns sent to millions of users"],
    "avoid": ["Urgent codes in the same queue as campaigns", "Sending without checking preferences"],
    "example": "A shop publishes an 'order shipped' event, and the notification service sends a push, with email as a fallback.",
    "takeaways": ["One queue and worker per channel", "Idempotency key plus retries with backoff", "Separate urgent from bulk traffic"],
}
DEEP["notify"] = {
    "how": [
        {"h": "The analogy: a post office", "p": "A post office does not deliver every letter by itself. It sorts mail by priority, hands each batch to the right carrier, tracks what was delivered, and returns what could not be. A notification system is the same: your services drop messages at the counter, the system sorts them by channel and urgency, hands them to push, SMS or email providers, and keeps a record so you can tell what reached the person."},
        {"h": "The pipeline", "p": "A service publishes an event, such as 'order shipped'. The notification service looks up the user, reads their preferences, picks the channel, renders a template in the right language, and puts a message on the queue for that channel. A pool of workers takes messages from the queue and calls the provider. Because the queue sits between the steps, a slow provider or a traffic spike never blocks the services that raised the events."},
        {"h": "Retries without duplicates", "p": "Provider calls fail often enough that retries are essential, and a naive retry can send a message twice, for example when the provider delivered it but the response was lost. Each notification therefore carries a unique idempotency key. Before sending, the worker records the key atomically, and a second attempt with the same key is skipped. Retries wait longer each time, with randomness added, and a message that exhausts its retries moves to a dead-letter queue for investigation."},
        {"h": "Priorities and rate limits", "p": "A one-time login code has to arrive in seconds, while a campaign can take an hour. Put them in separate queues with separate workers so a large campaign cannot starve urgent messages. Providers also limit how fast you may send, so workers are throttled to that limit and large batches are spread over time. Per-user limits stop a single user receiving a flood, and quiet hours delay non-urgent messages."},
        {"h": "Feedback and tracking", "p": "A send request being accepted is not the same as delivery. Providers report back through webhooks: delivered, bounced, complained, unsubscribed, or an invalid device token. Process these events, update the message status, and remove dead addresses and tokens so you stop paying to contact them and protect your sender reputation. Unsubscribes must be honoured immediately, because email and SMS are regulated in many countries."},
    ],
    "worked": {
        "title": "Sizing a campaign and the urgent lane",
        "steps": [
            "Illustrative numbers: a campaign to 10,000,000 users by push, and 200 one-time codes a second at peak.",
            "If the email provider accepts 1,000 messages a second per connection and you run 20 workers, you send 20,000 a second, so 10,000,000 / 20,000 = 500 seconds, a little over 8 minutes.",
            "Spreading the campaign over an hour (about 2,800 messages a second) is gentler on providers and on your own systems.",
            "One-time codes use their own queue and workers, sized for 200 a second with a margin, so a 500-second campaign cannot delay them.",
            "Each message is about 1 KB of queued data, so 10,000,000 messages is 10 GB, comfortably held by a managed queue.",
        ],
        "result": "A 10 million message campaign takes minutes at full speed or an hour when throttled, and a separate small urgent lane sized for 200 messages a second keeps login codes fast regardless.",
    },
    "case": {
        "who": "Stripe",
        "title": "Webhooks that survive failure",
        "text": "Stripe sends webhook events to its customers' servers when something happens, such as a payment succeeding. Customers' servers go down, so Stripe retries failed deliveries with increasing delays for days, and gives each event a unique identifier so a receiver can detect and ignore duplicates. Stripe's documentation tells receivers to respond quickly and to handle repeated events safely. It is the same pattern a notification system needs: at-least-once delivery, retries with backoff, and idempotency on the receiving side.",
        "source": {"title": "Stripe webhooks", "url": "https://docs.stripe.com/webhooks"},
    },
    "choose": [
        ["Option", "Strength", "Think twice when"],
        ["Managed service (SNS, Firebase, Twilio, SES)", "Scales without effort and handles provider details", "Cost at very high volume, or you need custom routing"],
        ["Your own queue and workers", "Full control over priorities, templates and limits", "A small team that must also run the queue and the workers"],
        ["Notification platform (Braze, OneSignal)", "Campaign tools and analytics for marketing teams", "You need tight control over security-critical messages"],
    ],
    "mistakes": [
        "Sending in the request path, so a slow provider makes your own page slow.",
        "No idempotency key, so a timeout and retry delivers the message twice.",
        "Putting urgent codes and bulk campaigns in the same queue.",
        "Ignoring bounces, unsubscribes and invalid tokens, which hurts deliverability and breaks the rules.",
        "Checking preferences once when queuing instead of when sending.",
    ],
    "reading": [
        {"title": "Stripe webhooks", "by": "Stripe", "kind": "docs", "url": "https://docs.stripe.com/webhooks"},
        {"title": "Implementing Stripe-like idempotency keys in Postgres", "by": "Brandur Leach", "kind": "blog", "url": "https://brandur.org/idempotency-keys"},
        {"title": "Amazon SNS developer guide", "by": "Amazon Web Services", "kind": "docs", "url": "https://docs.aws.amazon.com/sns/latest/dg/welcome.html"},
        {"title": "Firebase Cloud Messaging", "by": "Google", "kind": "docs", "url": "https://firebase.google.com/docs/cloud-messaging"},
        {"title": "Designing Data-Intensive Applications", "by": "Martin Kleppmann", "kind": "book"},
    ],
}
INTERVIEW["notify"] = [{
    "title": "Design a notification system", "level": 1, "name": "First question",
    "prompt": "Design a system that sends push, SMS and email notifications for an app with 50 million users. It must send urgent one-time codes within seconds, run a campaign to all users, and never send the same message twice. Explain the components, the queues, retries and how you prevent duplicates.",
    "tips": ["Separate urgent from bulk.", "Say what a retry does to duplicates."],
    "rubric": [
        {"id": "p1", "point": "Uses a queue between the event and the senders, with workers per channel", "keywords": ["queue", "worker", "kafka", "sqs", "channel"]},
        {"id": "p2", "point": "Hands delivery to providers such as APNs, FCM, Twilio or SES", "keywords": ["apns", "fcm", "twilio", "ses", "provider", "firebase"]},
        {"id": "p3", "point": "Separates urgent messages from bulk campaigns using separate queues or priorities", "keywords": ["priority", "separate queue", "urgent", "otp", "one-time"]},
        {"id": "p4", "point": "Retries with backoff, and prevents duplicates with an idempotency key", "keywords": ["idempoten", "dedup", "retry", "backoff", "duplicate"]},
        {"id": "p5", "point": "Checks user preferences and rate limits, and processes bounces or unsubscribes", "keywords": ["preference", "opt", "unsubscribe", "bounce", "rate limit", "quiet"]},
    ],
}]

# ---------------------------------------------------------------------------------------------- dr
LESSONS["dr"] = {
    "id": "dr", "t": "r", "title": "Multi-region and disaster recovery",
    "sum": "Plan for losing a whole data centre or region: how much data you can lose, how fast you recover, and what it costs.",
    "sec": [
        {"h": "RPO and RTO", "b": "<p>Two numbers define a recovery plan. <b>RPO</b> (recovery point objective) is how much recent data you can afford to lose, measured in time: 'at most 5 minutes of orders'. <b>RTO</b> (recovery time objective) is how long you can be down: 'back within 30 minutes'. The smaller the numbers, the more the design costs, so agree them with the business first.</p>"},
        {"h": "The four strategies", "b": "<p><b>Backup and restore</b> is cheapest and slowest, since you rebuild from backups in another region. <b>Pilot light</b> keeps data replicated and the core switched off, ready to scale up. <b>Warm standby</b> runs a smaller full copy that you scale up on failover. <b>Active-active</b> serves traffic from several regions at once, with the shortest recovery and the highest cost and complexity.</p>" + FLOW("Backup and restore", "Pilot light", "Warm standby", "Active-active")},
        {"h": "Data is the hard part", "b": "<p>Servers are easy to recreate, data is not. Replicating across regions is slower than inside one, so <b>asynchronous</b> replication has a lag (your RPO) and synchronous replication adds latency to every write. Active-active needs a plan for conflicting writes, such as routing each user to a home region. Test restores, because an untested backup is only a hope.</p>"},
        {"h": "Failover and practice", "b": "<p>Failover means detecting the problem, deciding to switch, and moving traffic, usually with health checks and DNS or a global load balancer. Automatic failover is fast but can trigger by mistake, so many teams keep a human decision for whole-region failover. Rehearse regularly in game days: only a failover you have done before will work under pressure.</p>"},
    ],
    "breaks": [
        "The backups exist but nobody has ever restored one, and the restore fails or takes a day. Run restore tests on a schedule.",
        "The standby region lacks capacity or quota when everyone fails over at once. Pre-provision, or reserve capacity.",
        "Failover works for the app but the database is hours behind. Monitor replication lag against the RPO.",
        "Automatic failover flips on a brief network glitch and causes the outage it was meant to prevent. Add damping, or a human decision.",
        "Configuration, secrets and DNS records exist only in the primary region. Replicate or define them as code.",
    ],
    "quiz": {"q": "What does an RPO of 5 minutes mean?", "o": ["Recovery must finish within 5 minutes", "At most the last 5 minutes of data may be lost", "Backups must be 5 minutes long"], "a": 1, "w": "RPO measures data loss in time. RTO is the one that measures how long recovery may take."},
    "projects": False,
}
EXPLAIN["dr"] = {
    "what": "A plan and a set of copies that let your system keep working, or come back quickly, after losing a whole data centre or region.",
    "why": "Entire regions do fail, and without a plan you lose data and hours of revenue.",
    "use": ["Systems where downtime costs real money", "Services with legal or contractual uptime promises", "Data that cannot be recreated"],
    "avoid": ["Paying for active-active when a short outage is acceptable", "Backups you have never tested"],
    "example": "A bank replicates its database to a second region and rehearses a switch-over every quarter.",
    "takeaways": ["Agree RPO and RTO with the business first", "Replication lag is your data loss", "Test restores and failovers regularly"],
}
DEEP["dr"] = {
    "how": [
        {"h": "The analogy: a fire drill and a spare office", "p": "A company that depends on one office plans for the day the building is unavailable. It decides how much work it could stand to lose and how quickly people must be working again, then arranges a spare office and rehearses the move. Disaster recovery for software is the same: you agree what loss and downtime are acceptable, you keep a copy of your system and data somewhere else, and you practise using it, because a plan that has never been rehearsed fails under pressure."},
        {"h": "RPO and RTO set the price", "p": "The recovery point objective says how much data you can lose, and it is set by how often data reaches the other site. The recovery time objective says how long you can be down, and it is set by how ready the other site is. Zero loss and zero downtime are possible but very expensive, so the right numbers come from the cost of an hour of downtime and a lost transaction. A shop might accept a one-hour RTO and five minutes of lost orders, while a payment system accepts almost none."},
        {"h": "From backup to active-active", "p": "Backup and restore stores copies in another region and rebuilds everything after a disaster, taking hours, for little cost. Pilot light replicates the data continuously and keeps only the essentials running. Warm standby runs a scaled-down full system that you grow when needed, recovering in minutes. Active-active serves users from two or more regions at the same time, so losing one is barely noticed, but every part of the system must handle multiple regions and conflicting writes. Each step reduces RTO and RPO and increases cost and complexity."},
        {"h": "Replicating data across regions", "p": "Regions are thousands of kilometres apart, so a round trip takes tens or hundreds of milliseconds. Synchronous replication waits for the other region on every write, which makes writes slow but loses nothing. Asynchronous replication confirms writes locally and copies them afterwards, so writes stay fast, but the copy trails behind, and that trailing time is the data you lose in a disaster. Databases such as Spanner use consensus across regions to avoid the choice, at the price of higher write latency."},
        {"h": "Failover is a procedure, not a switch", "p": "Failing over means noticing that the primary is truly gone, promoting the standby database, starting or scaling the application, and moving traffic through DNS or a global load balancer. Doing it automatically is fast but can be triggered by a short network problem, and a wrongly triggered failover with unfinished replication can lose data or split the system. Teams write runbooks, keep a human decision for whole-region moves, and run game days where they fail over on purpose. They also fail back afterwards, which is often harder."},
    ],
    "worked": {
        "title": "Choosing a strategy from RPO and RTO",
        "steps": [
            "Illustrative numbers: an online shop earns about 20,000 per hour at peak and 5,000 per hour on average.",
            "The business says it can tolerate losing up to 5 minutes of orders (RPO) and being down for up to 1 hour (RTO).",
            "Backup and restore cannot meet it: backups taken hourly lose up to an hour of data, and a rebuild takes several hours.",
            "Pilot light with continuous asynchronous replication can hold lag under a minute, meeting the RPO, and scaling up the standby can plausibly finish inside an hour.",
            "Warm standby would recover faster, for roughly twice the cost of pilot light, and active-active would cost the most for a recovery time the business did not ask for.",
            "A one-hour outage at peak costs about 20,000, so spending far more each month than a rare outage would cost is hard to justify.",
        ],
        "result": "Pilot light with asynchronous replication fits these numbers. The design is driven by RPO and RTO and by what an outage truly costs, not by what is technically possible.",
    },
    "case": {
        "who": "Google (Spanner)",
        "title": "Surviving the loss of a region by replicating with consensus",
        "text": "Google built Spanner so that a database can keep its data in several regions and still give strongly consistent answers. Each piece of data is copied to several places and a majority must agree on every write, using the Paxos consensus protocol, so losing one location does not lose acknowledged data or stop the service. The price is write latency, because a write must reach a majority of replicas that may be far apart, and the engineers say plainly that this is the trade they chose. It shows the two ends of the choice described above: asynchronous replication is fast and can lose recent writes, while consensus across regions loses nothing and costs time on every write.",
        "source": {"title": "Spanner: Google's Globally-Distributed Database", "url": "https://research.google/pubs/spanner-googles-globally-distributed-database-2/"},
    },
    "choose": [
        ["Strategy", "Strength", "Think twice when"],
        ["Backup and restore", "Cheapest, simple", "Hours of downtime or data loss are not acceptable"],
        ["Pilot light", "Low cost with good data protection", "You need recovery in minutes"],
        ["Warm standby", "Fast recovery, can serve some traffic", "The extra running cost is hard to justify"],
        ["Active-active", "Shortest recovery, lower latency for users everywhere", "Your data model cannot handle writes in several regions"],
    ],
    "mistakes": [
        "Having backups but never testing a restore, then finding out during the disaster that it fails.",
        "Letting the standby region run without the capacity or quotas it needs after a failover.",
        "Ignoring replication lag, so the real data loss is far above the agreed RPO.",
        "Keeping configuration, secrets and DNS only in the primary region.",
        "Failing over automatically on a brief glitch with no damping or human check.",
        "Never practising failing back, which is often harder than failing over.",
    ],
    "reading": [
        {"title": "Disaster recovery options in the cloud", "by": "Amazon Web Services", "kind": "docs", "url": "https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html"},
        {"title": "Disaster recovery planning guide", "by": "Google Cloud", "kind": "docs", "url": "https://cloud.google.com/architecture/dr-scenarios-planning-guide"},
        {"title": "Spanner: Google's Globally-Distributed Database", "by": "Corbett et al.", "kind": "paper", "url": "https://research.google/pubs/spanner-googles-globally-distributed-database-2/"},
        {"title": "Site Reliability Engineering", "by": "Google", "kind": "book", "url": "https://sre.google/sre-book/table-of-contents/"},
    ],
}
INTERVIEW["dr"] = [{
    "title": "Plan disaster recovery for a payment service", "level": 1, "name": "First question",
    "prompt": "A payment service runs in one cloud region. Leadership wants it to survive the loss of that whole region. Explain how you would choose the recovery objectives, what architecture you would pick, how data reaches the second region and how you would prove it works.",
    "tips": ["Name RPO and RTO.", "Say how you will test it."],
    "rubric": [
        {"id": "p1", "point": "Defines RPO and RTO and links them to business cost", "keywords": ["rpo", "rto", "recovery point", "recovery time"]},
        {"id": "p2", "point": "Chooses a strategy (pilot light, warm standby or active-active) and justifies it", "keywords": ["pilot light", "warm standby", "active-active", "active active", "standby"]},
        {"id": "p3", "point": "Replicates data to the second region and discusses sync versus async and the resulting lag", "keywords": ["replicat", "async", "synchronous", "lag"]},
        {"id": "p4", "point": "Covers failover steps such as health checks, promoting the database and moving traffic with DNS or a global load balancer", "keywords": ["failover", "dns", "load balancer", "promote", "health check"]},
        {"id": "p5", "point": "Tests the plan with restore tests or game days and keeps a runbook", "keywords": ["test", "game day", "drill", "runbook", "rehears"]},
    ],
}]
