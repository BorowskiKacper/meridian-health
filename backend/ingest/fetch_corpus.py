"""Build the evidence corpora as JSONL, one citation-shaped passage per line.

    python backend/ingest/fetch_corpus.py

Writes backend/ingest/corpus/{uspstf,pubmed,payer_docs}.jsonl. Each line is
{"source_id", "title", "passage", "locator"}, the contract's citation shape.
USPSTF and PubMed are downloaded. Payer docs are the fictional markdown files in
backend/ingest/payer_docs/. Loading into Snowflake is a separate step.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "corpus"
UA = {"User-Agent": "Mozilla/5.0 (hackathon EMR corpus builder)"}
PASSAGE_CHARS = 1000

USPSTF = "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/"
# slug -> PubMed query for the same topic
TOPICS = {
    "colorectal-cancer-screening": "colorectal cancer screening",
    "breast-cancer-screening": "breast cancer screening mammography",
    "cervical-cancer-screening": "cervical cancer screening",
    "lung-cancer-screening": "lung cancer screening low-dose CT",
    "prostate-cancer-screening": "prostate cancer screening PSA",
    "statin-use-in-adults-preventive-medication": "statin primary prevention cardiovascular",
    "hypertension-in-adults-screening": "hypertension screening adults",
    "screening-for-prediabetes-and-type-2-diabetes": "prediabetes type 2 diabetes screening",
    "osteoporosis-screening": "osteoporosis screening",
    "abdominal-aortic-aneurysm-screening": "abdominal aortic aneurysm screening",
    "hepatitis-c-screening": "hepatitis C screening adults",
    "screening-depression-suicide-risk-adults": "depression screening adults primary care",
}
PUBMED_PER_TOPIC = 25
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

SKIP = re.compile(
    r"nominate a recommendation|recommendations app|independent of the u\.s\. government"
    r"|jama podcast|patient page|^share$|^print$|^email|^recommendation: ",
    re.I,
)
# Sections about the review process or link lists, not clinical guidance.
SKIP_SECTION = re.compile(r"public comment|additional information|research taxonomy|recommendation information", re.I)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def chunk(blocks, title_prefix, source_prefix, locator):
    """blocks: [(heading, text)] -> passages capped near PASSAGE_CHARS, split on heading change."""
    out, buf, heading = [], [], None

    def flush():
        if buf:
            out.append({
                "source_id": f"{source_prefix}#{len(out) + 1}",
                "title": f"{title_prefix}: {heading}" if heading else title_prefix,
                "passage": " ".join(buf),
                "locator": locator,
            })
            buf.clear()

    for h, block in blocks:
        for text in split_long(block):
            if h != heading or sum(map(len, buf)) + len(text) > PASSAGE_CHARS:
                flush()
                heading = h
            buf.append(text)
    flush()
    return out


def split_long(text):
    """Split a block longer than PASSAGE_CHARS on sentence ends."""
    if len(text) <= PASSAGE_CHARS:
        return [text]
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(s) > PASSAGE_CHARS:
            parts.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    return parts + [cur] if cur else parts


class Blocks(HTMLParser):
    """Collect (current heading, text) for p/li/td blocks and h2-h4 headings."""

    BLOCK = {"p", "li", "td", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.blocks, self.heading, self.tag, self.text, self.skip = [], None, None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip += 1
        elif tag in self.BLOCK and not self.skip:
            self.tag, self.text = tag, []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip = max(0, self.skip - 1)
        elif tag == self.tag:
            text = re.sub(r"\s+", " ", html.unescape("".join(self.text))).strip()
            if tag.startswith("h"):
                self.heading = text or self.heading
            elif (len(text) > 25 and not SKIP.search(text)
                  and not SKIP_SECTION.search(self.heading or "")):
                self.blocks.append((self.heading, text))
            self.tag = None

    def handle_data(self, data):
        if self.tag and not self.skip:
            self.text.append(data)


def uspstf():
    rows = []
    for slug in TOPICS:
        url = USPSTF + slug
        try:
            page = get(url)
        except Exception as e:  # a moved page should not sink the other topics
            print(f"uspstf {slug}: {e}", file=sys.stderr)
            continue
        p = Blocks()
        p.feed(page)
        seen, blocks = set(), []
        for b in p.blocks:  # pages repeat the summary; keep the first copy
            if b[1] not in seen:
                seen.add(b[1])
                blocks.append(b)
        m = re.search(r"<title>\s*Recommendation:\s*(.*?)\s*\|", page)
        topic = html.unescape(m.group(1)) if m else slug
        got = chunk(blocks, f"USPSTF {topic}", f"uspstf:{slug}", url)
        print(f"uspstf {slug}: {len(got)} passages", file=sys.stderr)
        rows += got
    return rows


def pubmed():
    rows, seen = [], set()
    for query in TOPICS.values():
        term = f"({query}) AND (guideline[pt] OR systematic review[pt] OR meta-analysis[pt]) AND hasabstract AND english[la]"
        q = urllib.parse.urlencode({"db": "pubmed", "term": term, "retmax": PUBMED_PER_TOPIC,
                                    "sort": "relevance", "retmode": "json", "tool": "hackknight-emr"})
        ids = [i for i in json.loads(get(EUTILS + "esearch.fcgi?" + q))["esearchresult"]["idlist"] if i not in seen]
        seen.update(ids)
        time.sleep(0.4)  # NCBI allows 3 requests/second without a key
        if not ids:
            continue
        q = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "hackknight-emr"})
        root = ET.fromstring(get(EUTILS + "efetch.fcgi?" + q))
        time.sleep(0.4)
        for art in root.iter("PubmedArticle"):
            pmid = art.findtext(".//PMID")
            title = "".join(art.find(".//ArticleTitle").itertext()).strip()
            parts = []
            for a in art.iter("AbstractText"):
                label = a.get("Label")
                text = "".join(a.itertext()).strip()
                parts.append(f"{label.title()}: {text}" if label else text)
            abstract = re.sub(r"\s+", " ", " ".join(parts)).strip()
            if abstract:
                journal = art.findtext(".//Journal/Title") or ""
                year = art.findtext(".//PubDate/Year") or art.findtext(".//PubDate/MedlineDate") or ""
                rows += chunk([(None, abstract)], f"{title} ({journal}, {year})".strip(),
                              f"pubmed:{pmid}", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        print(f"pubmed '{query}': {len(ids)} articles", file=sys.stderr)
    return rows


def payer_docs():
    rows = []
    for md in sorted((HERE / "payer_docs").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        blocks, heading = [], None
        for para in re.split(r"\n\s*\n", text)[1:]:
            para = para.strip()
            if para.startswith("#"):
                heading = para.lstrip("# ").strip()
            elif para:
                blocks.append((heading, re.sub(r"\s+", " ", para)))
        rows += chunk(blocks, title, f"payer:{md.stem}", f"Northwind Health, {title}")
    return rows


def write(name, rows):
    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} passages", file=sys.stderr)


if __name__ == "__main__":
    write("payer_docs", payer_docs())
    write("uspstf", uspstf())
    write("pubmed", pubmed())
