"""Content for new lessons: search, geo. Imported by add_lessons.py"""

FLOW = lambda *n: '<div class="flow">' + '<span class="arr" aria-hidden="true">→</span>'.join('<span class="node">%s</span>' % x for x in n) + '</div>'

LESSONS = {}
EXPLAIN = {}
DEEP = {}
INTERVIEW = {}

# ---------------------------------------------------------------------------------------------- search
LESSONS["search"] = {
    "id": "search", "t": "d", "title": "Search and autocomplete",
    "sum": "Find documents by their words, rank the best ones first and suggest completions as the user types.",
    "sec": [
        {"h": "The inverted index", "b": "<p>A database that scans every row for the words 'red running shoes' gets slower with every product you add. A search engine does the work ahead of time. It builds an <b>inverted index</b>: for each word, a list of the documents that contain it. A query looks up each word, intersects the lists, and ranks what is left.</p>" + FLOW("Documents", "Analyzer: split, lowercase, stem", "Inverted index", "Query", "Ranked results")},
        {"h": "Ranking and filters", "b": "<p>Matching is not enough, the best match must come first. <b>BM25</b>, the default in Lucene, Elasticsearch and OpenSearch, scores a document higher when it contains rare query words many times, and discounts very long documents. Filters (price, brand, in stock) and facets (counts per brand) run on separate structures, so they stay fast. Business signals such as sales or freshness are added on top.</p>"},
        {"h": "Autocomplete", "b": "<p>Suggestions must appear in a few dozen milliseconds, so they use their own structure: a <b>trie</b> or an index of <b>edge n-grams</b> that maps a typed prefix straight to the most popular completions. Keep the top few completions precomputed for common prefixes, cache them, and wait a moment after the last keystroke (debounce) before sending the request.</p>"},
        {"h": "Keeping the index fresh", "b": "<p>The search index is a <b>copy</b> of your data, never the source of truth. Changes reach it through a queue or a change feed, so it lags the database by a moment. Plan for that lag, and for a full rebuild into a new index followed by an atomic switch when the analyzer or the fields change.</p>" + FLOW("Database", "Change feed / queue", "Indexer", "Search index")},
    ],
    "breaks": [
        "The index is behind the database, so a new product is missing from search for a few seconds. Show it on its own page straight away, and accept that search is eventually consistent.",
        "Deep pagination (page 5,000) makes every shard sort and discard thousands of hits. Limit the depth, or use a cursor such as search_after.",
        "The query is analyzed differently from the documents (case, stemming, accents), so obvious matches never hit. Use the same analyzer on both sides.",
        "A very common word or one popular shard becomes a hot spot. Spread documents by id, not by category, and cache the heaviest queries.",
        "Autocomplete sends a request on every keystroke. Debounce, cancel the old request, and cache the answers for common prefixes.",
        "Using the search engine as the only database. It is not built for transactions or strict consistency, so rebuild it from the real store when needed.",
    ],
    "quiz": {"q": "Why is a search query on an inverted index fast?", "o": ["It reads every document each time", "It looks up the query words in a prebuilt word-to-documents map", "It copies the whole database into memory"], "a": 1, "w": "The expensive work (splitting text into words and listing which documents contain each word) is done at index time, so a query only combines a few short lists."},
    "projects": False,
}
EXPLAIN["search"] = {
    "what": "A separate system that keeps a word-to-documents map, so it can find and rank matches in milliseconds.",
    "why": "Scanning a database for words is slow and cannot rank results or forgive typos.",
    "use": ["Product, document or message search", "Ranking by relevance, filters and facets", "Suggestions while the user types"],
    "avoid": ["As your only source of truth", "Lookups by id that a normal database answers better"],
    "example": "A shop's search box uses Elasticsearch to find products by their words, and a trie of popular queries for the suggestion drop-down.",
    "takeaways": ["The index is a copy that lags the database", "Index and query must use the same analyzer", "Autocomplete is its own faster structure"],
}
DEEP["search"] = {
    "how": [
        {"h": "The analogy: the index at the back of a book", "p": "To find every page that mentions a word, you do not read the book again. You open the index at the back, which lists each word with its page numbers. A search engine builds exactly that index for your documents, called an inverted index because it maps words back to the documents that contain them. Looking up two words and finding the pages they share is far faster than reading every page, and it stays fast as the book grows."},
        {"h": "From text to terms: the analyzer", "p": "Before a document is indexed, an analyzer turns its text into terms. It splits the text into words, lowercases them, can remove very common words such as 'the', and can reduce words to a stem, so that 'running' and 'runs' both become 'run'. The same analyzer must process the query, otherwise a word is stored in one form and searched in another and nothing matches. Synonyms, accents and different languages are handled at this stage too."},
        {"h": "Ranking with TF-IDF and BM25", "p": "Finding matches is easy, ordering them is the real work. Term frequency says that a document mentioning 'espresso' five times is probably more about espresso than one that mentions it once. Inverse document frequency says that a rare word such as 'portafilter' tells you more than a common one such as 'machine'. BM25 combines both and also discounts long documents, which would otherwise win just by containing more words. It is the default scoring function in Lucene and Elasticsearch."},
        {"h": "Spreading an index over many machines", "p": "A large index is split into shards, each a complete small index holding part of the documents, and each shard has replicas for safety and extra read capacity. A query is sent to one copy of every shard (scatter), each returns its best hits, and a coordinating node merges them into one list (gather). Adding shards adds capacity, but every query now touches every shard, so the slowest shard decides the response time."},
        {"h": "Autocomplete is a different problem", "p": "Typing 'iph' should suggest 'iphone 15' within about 50 milliseconds, long before a full search would finish. Systems use a trie, or index the first few characters of each term as edge n-grams, so a prefix leads straight to a short list of candidates. Candidates are ranked by how often people search them, which is gathered from logs and refreshed regularly. Because many people type the same prefixes, the answers for popular prefixes are cached."},
    ],
    "worked": {
        "title": "Sizing a product search",
        "steps": [
            "Illustrative numbers: 20 million products, each about 2 KB of searchable text.",
            "Raw text is about 20,000,000 x 2 KB = 40 GB. An inverted index with extra fields is often one to two times the text, so plan for about 80 GB.",
            "Split it into 8 shards of about 10 GB each, a size that keeps each shard fast to search and to move.",
            "With one replica of each shard, the cluster stores about 160 GB across 16 shard copies.",
            "Suppose 2,000 searches a second arrive at peak. Every search touches 8 shards, so the cluster serves 16,000 shard queries a second, or about 1,000 a second for each of the 16 copies.",
            "If one shard copy handles about 1,500 queries a second at the target latency, there is headroom of 50%. Autocomplete traffic goes to a separate, smaller index so it cannot slow normal search.",
        ],
        "result": "Under these assumptions, 8 shards with one replica (16 copies, about 160 GB) carry the peak, and the number that matters is shard queries a second, which is searches times shards.",
    },
    "case": {
        "who": "GitHub (code search)",
        "title": "Indexing billions of lines of code",
        "text": "GitHub rebuilt its code search to handle hundreds of millions of repositories. Ordinary word search does not fit code, where symbols, punctuation and partial names matter, so the team built a custom index that supports substring and regular expression queries and splits the work across many shards. They described choosing to index each unique piece of content only once, even when it appears in thousands of forks, which cut the amount of data a great deal. The lesson is that the general idea, a precomputed index spread over shards, is the same, while the analyzer and the storage layout are shaped by what you search.",
        "source": {"title": "The technology behind GitHub's new code search", "url": "https://github.blog/engineering/the-technology-behind-githubs-new-code-search/"},
    },
    "choose": [
        ["Option", "Strength", "Think twice when"],
        ["Elasticsearch or OpenSearch", "Rich queries, ranking, filters, facets and a large ecosystem", "You only need simple lookups, or you cannot run and tune a cluster"],
        ["Database full-text search (Postgres)", "No second system to keep in sync, good for small and medium data", "You need advanced ranking, typo tolerance or very large scale"],
        ["Hosted search (Algolia, Typesense Cloud)", "Fast to adopt with built-in typo tolerance and autocomplete", "Cost grows with volume, or data must stay in your own network"],
    ],
    "mistakes": [
        "Treating the search index as the source of truth. It is a rebuildable copy, so keep the real data in a database.",
        "Using different analyzers when indexing and when querying, so words are stored in one form and searched in another.",
        "Allowing unlimited deep pagination. Every shard must sort and skip thousands of hits, so use cursors and limit the depth.",
        "Making too many tiny shards. Each shard has fixed overhead, so a few well-sized shards beat hundreds of small ones.",
        "Sending a request on every keystroke without debouncing or cancelling the previous one.",
    ],
    "reading": [
        {"title": "Elasticsearch Guide: text analysis", "by": "Elastic", "kind": "docs", "url": "https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis.html"},
        {"title": "Elasticsearch from the bottom up", "by": "Elastic", "kind": "blog", "url": "https://www.elastic.co/blog/found-elasticsearch-from-the-bottom-up"},
        {"title": "Introduction to Information Retrieval", "by": "Manning, Raghavan and Schutze", "kind": "book"},
        {"title": "The Probabilistic Relevance Framework: BM25 and Beyond", "by": "Robertson and Zaragoza", "kind": "paper", "url": "https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf"},
        {"title": "The technology behind GitHub's new code search", "by": "GitHub Engineering", "kind": "blog", "url": "https://github.blog/engineering/the-technology-behind-githubs-new-code-search/"},
        {"title": "Apache Lucene core documentation", "by": "Apache Software Foundation", "kind": "docs", "url": "https://lucene.apache.org/core/"},
    ],
}
INTERVIEW["search"] = [{
    "title": "Design search for an online shop", "level": 1, "name": "First question",
    "prompt": "An online shop has 20 million products. Design its search box with typo-tolerant results and suggestions while the user types. Say what you store, how a query is answered quickly, how the index stays up to date and how suggestions work.",
    "tips": ["Say what the index is made of.", "Say how it stays in sync with the database."],
    "rubric": [
        {"id": "p1", "point": "Uses an inverted index (word to documents) rather than scanning the database", "keywords": ["inverted index", "elasticsearch", "lucene", "opensearch", "index"]},
        {"id": "p2", "point": "Explains analysis of text (tokenising, lowercasing, stemming) and using it for both documents and queries", "keywords": ["analy", "token", "stem", "lowercase"]},
        {"id": "p3", "point": "Explains ranking, for example BM25 or TF-IDF plus business signals", "keywords": ["bm25", "tf-idf", "rank", "relevance", "score"]},
        {"id": "p4", "point": "Keeps the index in sync from the database through a queue or change feed and accepts a small lag", "keywords": ["queue", "change", "cdc", "stream", "eventual", "lag", "sync"]},
        {"id": "p5", "point": "Designs suggestions with a trie, n-grams or precomputed popular prefixes, with caching or debouncing", "keywords": ["trie", "prefix", "n-gram", "ngram", "autocomplete", "debounce", "cache"]},
    ],
}]

# ---------------------------------------------------------------------------------------------- geo
LESSONS["geo"] = {
    "id": "geo", "t": "y", "title": "Design a location service (nearby search)",
    "sum": "Find the closest drivers, shops or friends among millions of moving points, quickly.",
    "sec": [
        {"h": "The problem", "b": "<p>'Show restaurants within 2 km' or 'find the nearest free driver' cannot be answered by comparing your position with every row. A normal index on latitude alone does not help, because nearby places also differ in longitude. The trick is to turn two-dimensional space into something an index handles well: <b>cells</b>.</p>"},
        {"h": "Cells: geohash, quadtree and H3", "b": "<p>A <b>geohash</b> encodes a position as a short string, and places that share a long prefix are close together, so a normal prefix lookup finds a neighbourhood. A <b>quadtree</b> keeps splitting a square into four until each holds only a few points, so crowded cities get small cells and empty oceans stay large. <b>H3</b> and <b>S2</b> divide the earth into regular cells with a clean notion of neighbours. In every case the search is: find the user's cell, add the neighbouring cells, then compute exact distances for the few candidates.</p>" + FLOW("Position", "Cell id", "Candidates in this and nearby cells", "Exact distance and sort")},
        {"h": "Moving points", "b": "<p>Drivers update their position every few seconds, so locations are write-heavy and constantly outdated. Keep the current position in memory (for example Redis geo commands) keyed by cell, expire entries that have not updated, and write only occasional history to disk. Static places such as shops change rarely and can live in an ordinary database with a spatial index.</p>"},
        {"h": "Scaling it", "b": "<p>Partition by cell or by city so that one machine owns each area, and a request touches only one or a few partitions. A dense downtown cell is a hot spot, so split it into smaller cells or give it more machines. Matching a rider to a driver is a separate service that reads this one.</p>"},
    ],
    "breaks": [
        "A search at the edge of a cell misses points just across the border. Always search the neighbouring cells too.",
        "One huge downtown cell takes all the traffic. Use smaller, adaptive cells there.",
        "Writing every location update to a disk database overloads it. Keep live positions in memory and sample the history.",
        "Stale positions from drivers who went offline appear on the map. Give each entry a time to live.",
        "Ranking by straight-line distance ignores rivers and one-way streets. Re-rank the closest candidates by travel time.",
    ],
    "quiz": {"q": "Why search the neighbouring cells as well as the user's own cell?", "o": ["To make the query slower", "A close point can sit just across a cell border", "Cells do not contain any points"], "a": 1, "w": "Cells cut space into pieces with hard borders, so the nearest point can be in the next cell. Searching neighbours fixes that."},
    "projects": False,
}
EXPLAIN["geo"] = {
    "what": "A way to find the closest places or people by cutting the map into cells and only looking in the right few.",
    "why": "Comparing your position with millions of points is far too slow.",
    "use": ["Nearby restaurants, shops and friends", "Matching riders with drivers", "Tracking vehicles on a map"],
    "avoid": ["A handful of places you can scan directly", "Ranking by distance alone when roads matter"],
    "example": "A ride app keeps each driver's position in memory under a map cell, so finding the nearest ones means reading a handful of cells.",
    "takeaways": ["Turn 2D space into cell ids an index can use", "Search the neighbouring cells too", "Live positions belong in memory, not on disk"],
}
DEEP["geo"] = {
    "how": [
        {"h": "The analogy: a city divided into postcodes", "p": "To find a coffee shop near you, you would not measure the distance to every shop in the country. You would look in your own postcode and the ones next to it. Location services do the same thing with the whole planet: they divide the map into cells, give every cell an identifier, and remember which points are in which cell. A nearby search becomes a lookup of a few cells instead of a scan of every point."},
        {"h": "Geohash: a position as a string", "p": "A geohash repeatedly halves the world between west and east and between south and north, and writes the answers as characters. The longer the string, the smaller the box. Two places with the same first five characters are in the same box of roughly a few kilometres, so a plain index on the string answers 'what is in this box'. The weakness is the border: two points a metre apart on either side of a boundary can have completely different hashes, so you search the eight neighbouring boxes as well."},
        {"h": "Quadtrees adapt to density", "p": "Fixed-size cells waste effort. A city centre may contain thousands of points in one cell while a desert cell holds none. A quadtree starts with the whole map as one square and splits any square that holds more than a set number of points into four smaller ones, repeating as needed. Dense areas end up with small, precise cells and sparse areas keep large ones. To search, you descend to the leaf that contains the user and then look at its neighbours."},
        {"h": "Hexagonal cells: H3 and S2", "p": "Uber's H3 divides the earth into hexagons at several resolutions. A hexagon has the useful property that all of its neighbours are the same distance from its centre, which makes 'everything within two rings' a clean idea and avoids the awkward corner neighbours of squares. Google's S2 library does something similar on the surface of a sphere. Both give you a cell id as a number that is cheap to index and compare."},
        {"h": "Live positions and partitioning", "p": "A driver app sends a position every few seconds, so a million drivers produce hundreds of thousands of writes a second. Disk databases struggle, so live positions are kept in memory, keyed by cell, and entries expire when updates stop. The service is partitioned by cell or city so that each machine handles one region. Crowded cells need extra capacity or smaller cells. History for later analysis is written in batches through a queue, not on the request path."},
    ],
    "worked": {
        "title": "Sizing live driver positions",
        "steps": [
            "Illustrative numbers: 1,000,000 drivers online, each sending a position every 5 seconds.",
            "That is 1,000,000 / 5 = 200,000 position updates a second.",
            "Each stored position is about 50 bytes (id, latitude, longitude, time). Live data is 1,000,000 x 50 B = 50 MB, which easily fits in memory on one machine.",
            "The write rate, not the size, is the problem. One in-memory node may take around 50,000 updates a second, so use at least 4 partitions, and more for safety, split by city.",
            "A rider's request looks up the rider's cell and its 6 neighbours, reads perhaps 100 candidates and ranks them by exact distance, which takes a few milliseconds.",
        ],
        "result": "The live data is tiny (50 MB) but the 200,000 writes a second need several in-memory partitions split by area, and a nearby search stays fast because it reads only a few cells.",
    },
    "case": {
        "who": "Uber (H3)",
        "title": "A hexagonal grid for the whole planet",
        "text": "Uber needed to analyse and match supply and demand across every city it operates, with regions of many different sizes. Square grids caused problems because neighbours at the corners are further away than neighbours at the sides, which distorts anything that depends on distance. The team created H3, a hierarchical hexagonal grid where each cell has six equally spaced neighbours, and released it as open source. Pricing, forecasting and matching can then work on cell ids at the resolution that suits the question.",
        "source": {"title": "H3 documentation", "url": "https://h3geo.org/docs"},
    },
    "choose": [
        ["Approach", "Strength", "Think twice when"],
        ["Geohash on a normal index", "Simple, works in any database, prefix lookups are fast", "Borders matter a lot, or density varies widely"],
        ["Quadtree", "Adapts to dense and sparse areas", "Many frequent updates, because the tree needs rebalancing"],
        ["H3 or S2 cells", "Uniform neighbours, multiple resolutions, good for analysis", "You need a library in every service that touches it"],
        ["Spatial database (PostGIS)", "Rich queries such as polygons and distances", "Very high update rates, where in-memory storage fits better"],
    ],
    "mistakes": [
        "Searching only the user's own cell and missing points just across the border.",
        "Writing every location update to a disk database instead of holding live positions in memory.",
        "Using one fixed cell size everywhere, so the busiest cell becomes a hot spot.",
        "Never expiring old positions, so offline drivers keep appearing on the map.",
        "Sorting by straight-line distance when the real travel time is what the user cares about.",
    ],
    "reading": [
        {"title": "Quad trees: a data structure for retrieval on composite keys", "by": "Finkel and Bentley", "kind": "paper"},
        {"title": "S2 geometry library", "by": "Google", "kind": "docs", "url": "https://s2geometry.io/"},
        {"title": "H3 documentation", "by": "Uber", "kind": "docs", "url": "https://h3geo.org/docs"},
        {"title": "Redis geospatial commands: GEOSEARCH", "by": "Redis", "kind": "docs", "url": "https://redis.io/docs/latest/commands/geosearch/"},
        {"title": "Geohash", "by": "Wikipedia", "kind": "docs", "url": "https://en.wikipedia.org/wiki/Geohash"},
        {"title": "PostGIS documentation", "by": "PostGIS project", "kind": "docs", "url": "https://postgis.net/documentation/"},
        {"title": "Designing Data-Intensive Applications", "by": "Martin Kleppmann", "kind": "book"},
    ],
}
INTERVIEW["geo"] = [{
    "title": "Design 'find nearby drivers'", "level": 1, "name": "First question",
    "prompt": "A ride app has one million drivers online, each sending a position every few seconds. Design the service that returns the closest available drivers to a rider. Explain how you index locations, how you store the live positions and how you scale it.",
    "tips": ["Say how you avoid scanning every driver.", "Say what happens at the border of a cell."],
    "rubric": [
        {"id": "p1", "point": "Divides the map into cells (geohash, quadtree, H3 or S2) so a search reads only a few cells", "keywords": ["geohash", "quadtree", "h3", "s2", "cell", "grid"]},
        {"id": "p2", "point": "Searches neighbouring cells too, because the nearest driver may be across a border", "keywords": ["neighbo", "adjacent", "border", "boundary"]},
        {"id": "p3", "point": "Keeps live positions in memory (for example Redis), not in a disk database", "keywords": ["redis", "in-memory", "in memory", "memory"]},
        {"id": "p4", "point": "Expires stale positions with a time to live or heartbeat", "keywords": ["ttl", "expire", "stale", "heartbeat", "time to live"]},
        {"id": "p5", "point": "Partitions by area or city and handles hot dense cells", "keywords": ["partition", "shard", "city", "region", "hot", "dense"]},
    ],
}]
