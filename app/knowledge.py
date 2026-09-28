from io import BytesIO
import hashlib
import re
import threading
import time
import uuid
import zipfile
from decimal import Decimal
from xml.etree import ElementTree
from qdrant_client import QdrantClient, models
from pypdf import PdfReader
from .storage import now, uid

MAX_UPLOAD = 10 * 1024 * 1024
DEPARTMENTS = {"All", "HR", "IT", "Operations"}


class IndexUnavailable(RuntimeError):
    """SQL claims documents are ready but their vector index is incomplete."""


def extract_sections(filename, content):
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError("Upload a nonempty file of 10 MB or smaller.")
    extension = filename.rsplit(".", 1)[-1].lower()
    sections = []
    try:
        if extension in {"txt", "md"}:
            text = content.decode("utf-8-sig")
            sections = [(f"Paragraph {i + 1}", p.strip()) for i, p in enumerate(re.split(r"\n\s*\n", text)) if p.strip()]
        elif extension == "pdf":
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported. Upload an unlocked text-based PDF.")
            if len(reader.pages) > 100:
                raise ValueError("This demo accepts PDFs up to 100 pages.")
            sections = [(f"Page {i + 1}", page.extract_text() or "") for i, page in enumerate(reader.pages)]
        elif extension == "docx":
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if sum(info.file_size for info in archive.infolist()) > 30 * MAX_UPLOAD:
                    raise ValueError("The DOCX expands beyond the supported limit.")
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_UPLOAD or info.file_size / max(1, info.compress_size) > 200:
                    raise ValueError("The DOCX text expands beyond the supported limit.")
                xml = archive.read("word/document.xml")
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ValueError("Documents with XML entity declarations are not supported.")
                root = ElementTree.fromstring(xml)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for i, p in enumerate(root.findall(".//w:p", ns)):
                    text = "".join(t.text or "" for t in p.findall(".//w:t", ns))
                    if text.strip():
                        sections.append((f"Paragraph {i + 1}", text))
        else:
            raise ValueError("Supported files: UTF-8 TXT, MD, text-based PDF, and DOCX.")
    except UnicodeDecodeError as exc:
        raise ValueError("Text files must use UTF-8 encoding.") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The document could not be read. Use a valid, unencrypted, text-based file.") from exc
    sections = [(locator, text.replace("\x00", "").strip()) for locator, text in sections if text.strip()]
    length = sum(len(text) for _, text in sections)
    if length < 40:
        raise ValueError("No usable text found. Scanned PDFs need OCR before upload.")
    if length > 200_000:
        raise ValueError("This demo accepts up to 200,000 extracted characters per document.")
    return sections


def extract_text(filename, content):
    return "\n\n".join(text for _, text in extract_sections(filename, content))


def chunk_text(text, size=160, overlap=30):
    if size <= overlap or overlap < 0:
        raise ValueError("Chunk size must exceed overlap.")
    tokens, chunks = text.split(), []
    for start in range(0, len(tokens), size - overlap):
        chunks.append(" ".join(tokens[start:start + size]))
        if start + size >= len(tokens):
            break
    return chunks


def normalized(text):
    return " ".join(text.casefold().split())


def canonical_pdf_quote(quote, source):
    """Map whitespace-only PDF extraction differences back to original text.

    Return the canonical span, never the model's repaired typography. Letters,
    punctuation, numbers and negation must all remain in the same order.
    """
    if not source.get('filename', '').lower().endswith('.pdf'):
        return None
    text = source['text']
    chars, positions = [], []
    for index, char in enumerate(text):
        if not char.isspace():
            folded = char.casefold()
            chars.extend(folded)
            positions.extend([index] * len(folded))
    needle = ''.join(char.casefold() for char in quote if not char.isspace())
    if len(needle) < 15:
        return None
    offset = ''.join(chars).find(needle)
    if offset < 0:
        return None
    return text[positions[offset]:positions[offset + len(needle)-1]+1]


STOPWORDS = set("a an the to of for and or in is are be on with what how when where can i my do does me about please our we it this that should could would you your have has at as by from must which".split())
QUERY_ALIASES = {'mfa':'multi-factor authentication', 'sso':'single sign-on', 'vpn':'virtual private network'}


def retrieval_query(query):
    # A leading publication reference can make a cover page outrank the actual
    # rule. Keep the original question for generation; search its substantive part.
    query = re.sub(r'^according to\s+[^,\n]{1,140},\s*', '', query, flags=re.I)
    for abbreviation, expansion in QUERY_ALIASES.items():
        query = re.sub(r'\b' + abbreviation + r'\b', expansion, query, flags=re.I)
    return query


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


def focus_sources(sources, query):
    """Exclude weakly related policies only when the top hit covers the query.

    Retain competing policies with similar coverage, and all candidates for a
    multi-topic / low-overlap question. This is a retrieval heuristic, not a
    semantic confidence score or an authorization boundary.
    """
    if len(sources) < 2:
        return sources
    vocabulary = [words(s['text'] + ' ' + s.get('title', '')) for s in sources]
    represented = words(query) & set().union(*vocabulary)
    if len(represented) < 3:
        return sources
    coverage = [len(represented & terms) for terms in vocabulary]
    if coverage[0] / len(represented) < 0.85:
        return sources
    # Keep all retrieved chunks of a strongly matching document, so a nearby
    # exception does not disappear just because its paragraph repeats fewer words.
    strong = {s.get('document_id', s['source_id']) for s, count in zip(sources, coverage) if count >= coverage[0] * 0.75}
    return [s for s in sources if s.get('document_id', s['source_id']) in strong]


def has_numeric_conflict(sources, query):
    """Catch identical relevant rules with different values across active docs.

    This deliberately narrow check does not infer precedence or claim to detect
    arbitrary semantic contradictions. Other conflicts remain a model/review task.
    """
    number = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")
    seen = {}
    for source in sources:
        for sentence in re.split(r'(?<=[.!?])\s+', source['text']):
            values = tuple(str(Decimal(v.replace(',', '')).normalize()) for v in number.findall(sentence))
            if not values or len(words(sentence) & words(query)) < 2:
                continue
            signature = normalized(number.sub('<number>', sentence))
            if len(words(signature)) < 6:
                continue
            previous = seen.get(signature)
            if previous and previous[0] != source['document_id'] and previous[1] != values:
                return True
            seen[signature] = (source['document_id'], values)
    return False


def permitted(document, user):
    return user["role"] == "admin" or (
        document["department"] in {"All", user["department"]}
        and (document["classification"] == "internal" or user["role"] == "manager")
    )


class Knowledge:
    def __init__(self, settings, store, llm):
        self.settings, self.store, self.llm = settings, store, llm
        self.client = QdrantClient(path=str(settings.data_dir / "vectors"))
        self.collection = "knowledge_" + hashlib.sha256(settings.embed_model.encode()).hexdigest()[:12]
        self.lock = threading.RLock()

    def visible_documents(self, user, active_only=True):
        sql = "SELECT * FROM documents" + (" WHERE status='ready' AND embed_model=?" if active_only else "")
        rows = self.store.all(sql, (self.settings.embed_model,) if active_only else ())
        return [d for d in rows if permitted(d, user)]

    def verify_index(self, documents):
        if not self.client.collection_exists(self.collection):
            raise IndexUnavailable("The vector index is missing. Restore a verified backup or re-upload affected documents before querying.")
        # Check canonical point IDs; vector payloads are never visibility authority.
        expected = [row['id'] for doc in documents for row in self.store.all("SELECT id FROM chunks WHERE document_id=?", (doc['id'],))]
        if len(expected) != sum(doc['chunk_count'] for doc in documents):
            raise IndexUnavailable("The document index is inconsistent. Restore a verified backup or re-upload affected documents before querying.")
        for offset in range(0, len(expected), 256):
            batch = expected[offset:offset + 256]
            present = self.client.retrieve(self.collection, ids=batch, with_payload=False, with_vectors=False)
            if {str(point.id) for point in present} != set(batch):
                raise IndexUnavailable("The vector index is incomplete. Restore a verified backup or re-upload affected documents before querying.")

    def ingest(self, filename, content, classification, user_id, title=None, department="All", replaces_id=None):
        actor = self.store.one("SELECT * FROM users WHERE id=?", (user_id,))
        if not actor or actor["role"] != "admin":
            raise PermissionError("Only an administrator can manage documents.")
        if classification not in {"internal", "leadership"} or department not in DEPARTMENTS:
            raise ValueError("Unknown document classification or department.")
        filename = filename.replace("\\", "/").split("/")[-1][:180]
        title = (title or filename.rsplit(".", 1)[0].replace("_", " ")).strip()[:150]
        if not filename or not title:
            raise ValueError("A document filename and title are required.")
        sections = extract_sections(filename, content)
        digest = hashlib.sha256(content).hexdigest()
        with self.lock:
            old = None
            if replaces_id:
                old = self.store.one("SELECT * FROM documents WHERE id=? AND status='ready'", (replaces_id,))
                if not old:
                    raise ValueError("Select an active document to replace.")
                # Access scope stays attached to a document through version changes.
                if classification != old["classification"] or department != old["department"]:
                    raise ValueError("A replacement must keep the existing access scope.")
            existing = self.store.one("SELECT * FROM documents WHERE digest=? AND classification=? AND department=? AND embed_model=? AND status='ready'", (digest, classification, department, self.settings.embed_model))
            if existing:
                if old and existing["id"] != old["id"]:
                    raise ValueError("This content is already another active document.")
                try:
                    self.verify_index([existing])
                except IndexUnavailable:
                    # Re-uploading identical bytes repairs damage through the same
                    # atomic publication path; keep the old version until success.
                    old, replaces_id = existing, existing['id']
                else:
                    return {**existing, "duplicate": True}
            document_id = uid()
            version = old["version"] + 1 if old else 1
            self.store.run("INSERT INTO documents(id,title,filename,digest,classification,status,chunk_count,embed_model,created_by,created_at,department,version,supersedes_id) VALUES (?,?,?,?,?,'indexing',0,?,?,?,?,?,?)", (document_id, title, filename, digest, classification, self.settings.embed_model, user_id, now(), department, version, replaces_id))
            try:
                pieces = [(locator, chunk) for locator, text in sections for chunk in chunk_text(text)]
                if len(pieces) > 600:
                    raise ValueError("The document produces too many chunks. Split it into smaller files.")
                points = []
                for offset in range(0, len(pieces), 16):
                    batch = pieces[offset:offset + 16]
                    vectors = self.llm.embed([text for _, text in batch])
                    if len(vectors) != len(batch):
                        raise ValueError("The embedding service returned an incomplete batch.")
                    for position, ((locator, chunk), vector) in enumerate(zip(batch, vectors), start=offset):
                        point_id = str(uuid.uuid5(uuid.UUID(document_id), str(position)))
                        payload = {"document_id": document_id, "title": title, "filename": filename, "classification": classification, "department": department, "version": version, "text": chunk, "position": position, "locator": locator}
                        points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
                if not self.client.collection_exists(self.collection):
                    self.client.create_collection(self.collection, vectors_config=models.VectorParams(size=len(points[0].vector), distance=models.Distance.COSINE))
                self.client.upsert(self.collection, points)
                # SQL is the visibility authority. Nothing becomes searchable until all vectors exist.
                with self.store.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    actor = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
                    if not actor or actor['role'] != 'admin':
                        raise PermissionError("Upload permission changed during indexing. The document was not published.")
                    if old and not conn.execute("SELECT id FROM documents WHERE id=? AND status='ready'", (old['id'],)).fetchone():
                        raise ValueError("The replaced document changed during indexing. Refresh the library before retrying.")
                    conn.executemany("INSERT INTO chunks(id,document_id,position,text,locator) VALUES (?,?,?,?,?)", [(p.id, document_id, p.payload["position"], p.payload["text"], p.payload["locator"]) for p in points])
                    conn.execute("UPDATE documents SET status='ready',chunk_count=?,error=NULL WHERE id=?", (len(pieces), document_id))
                    if old:
                        conn.execute("UPDATE documents SET status='superseded' WHERE id=?", (old["id"],))
                    self.store.audit(user_id, "document.ingested", document_id, {"chunks": len(pieces), "classification": classification, "department": department, "version": version}, conn=conn)
            except Exception as exc:
                self.store.run("UPDATE documents SET status='failed',error=? WHERE id=?", ("Ingestion failed: " + type(exc).__name__ + ". Re-upload to retry.", document_id))
                if self.client.collection_exists(self.collection):
                    self.client.delete(self.collection, models.FilterSelector(filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))])))
                self.store.audit(user_id, "document.ingestion_failed", document_id)
                raise
            # A failure reading the response must never undo a committed publication.
            return self.store.one("SELECT * FROM documents WHERE id=?", (document_id,))

    def search(self, query, user, limit=4, workflow_id=None, document_ids=None):
        started = time.perf_counter()
        with self.lock:
            documents = self.visible_documents(user)
            if document_ids is not None:
                documents = [doc for doc in documents if doc['id'] in document_ids]
            if not documents:
                return []
            allowed_ids = {doc['id'] for doc in documents}
            # A missing point must not turn a known policy into a convincing
            # knowledge gap or an answer drawn only from an unrelated document.
            self.verify_index(documents)
            search_text = retrieval_query(query)
            vector = self.llm.embed([search_text], query=True)[0]
            found = self.client.query_points(self.collection, query=vector, limit=20, query_filter=models.Filter(must=[
                models.FieldCondition(key="document_id", match=models.MatchAny(any=[d["id"] for d in documents])),
            ])).points
            # Re-read canonical SQL text and permissions instead of trusting vector payloads.
            ranked = []
            terms = words(search_text)
            for point in found:
                row = self.store.one("SELECT c.id AS chunk_id,c.text,c.position,c.locator,d.* FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=? AND d.status='ready'", (str(point.id),))
                if not row or row['id'] not in allowed_ids or not permitted(row, user):
                    continue
                lexical = len(terms & words(row["text"])) / max(1, len(terms))
                score = 0.78 * point.score + 0.22 * lexical
                ranked.append({"document_id": row["id"], "chunk_id": row["chunk_id"], "title": row["title"], "filename": row["filename"], "version": row["version"], "locator": row["locator"], "text": row["text"], "position": row["position"], "score": round(point.score, 4), "rank_score": round(score, 4)})
            ranked.sort(key=lambda p: p["rank_score"], reverse=True)
            results = [p for p in ranked[:limit] if p['score'] >= 0.35]
            # A relevant paragraph may straddle chunk boundaries. Add at most
            # two neighbors from the same canonical page/paragraph as the top
            # hits. Keep all original hits, including potentially conflicting docs.
            seen = {p['chunk_id'] for p in results}
            neighbors = []
            for anchor in results[:2]:
                rows = self.store.all("SELECT id,text,position,locator FROM chunks WHERE document_id=? AND locator=? AND position IN (?,?) ORDER BY position", (anchor['document_id'], anchor['locator'], anchor['position']-1, anchor['position']+1))
                for row in rows:
                    if row['id'] in seen or len(neighbors) >= 2:
                        continue
                    seen.add(row['id'])
                    neighbors.append({**anchor, 'chunk_id':row['id'], 'text':row['text'], 'position':row['position'], 'locator':row['locator'], 'retrieval_kind':'adjacent_context', 'score':None, 'rank_score':None})
            results = [{**p, 'source_id':f'S{i+1}'} for i,p in enumerate(results+neighbors)]
        latency = (time.perf_counter() - started) * 1000
        self.store.run("INSERT INTO metrics(workflow_id,user_id,operation,latency_ms,model,prompt_version,status,created_at) VALUES (?,?,?,?,?,?,?,?)", (workflow_id, user["id"], "retrieval", latency, self.settings.embed_model, self.settings.prompt_version, "ok", now()))
        return results

    def close(self):
        self.client.close()


def validate_answer(answer, sources):
    lookup = {s["source_id"]: s for s in sources}
    citations, invalid, layout_recovered = [], 0, 0
    for citation in answer.citations:
        source = lookup.get(citation.source_id)
        quote = citation.quote
        if source and normalized(quote) not in normalized(source['text']):
            recovered = canonical_pdf_quote(quote, source)
            if recovered:
                quote = recovered
                layout_recovered += 1
        if source and len(normalized(quote)) >= 15 and normalized(quote) in normalized(source["text"]):
            citations.append({**source, "quote": quote})
        else:
            invalid += 1
    # Prevent invented numbers even if the model also supplies a genuine quote.
    def numeric_tokens(text):
        # Thousands separators and trailing decimal zeroes do not change a fact.
        # Currency / unit adjacency must not hide a claim (AED9999, 99days).
        # Preserve signs so a negative value cannot borrow positive evidence.
        values = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", text.replace("−", "-"))
        return {str(Decimal(value.replace(",", "")).normalize()) for value in values}
    answer_text = answer.answer
    # Publication identifiers are metadata, not policy quantities. Remove a
    # leading reference only when it matches a genuinely cited document's
    # canonical filename/title. Never whitelist that number in the actual claim.
    reference = re.match(r'^According to\s+([A-Za-z][A-Za-z ._-]{1,60}\s+\d+(?:[.-]\d+)*),\s*', answer_text, re.I)
    removed_reference = False
    if reference:
        reference_words = words(reference.group(1))
        if len(reference_words) >= 2 and any(reference_words <= words(c.get('title','') + ' ' + c.get('filename','')) for c in citations):
            answer_text = answer_text[reference.end():].strip()
            answer_text = answer_text[:1].upper() + answer_text[1:]
            removed_reference = True
    numbers = numeric_tokens(answer_text)
    evidence_numbers = numeric_tokens(" ".join(c["text"] for c in citations))
    unsupported_numbers = sorted(numbers - evidence_numbers)
    refused = not normalized(answer_text) or answer.insufficient_evidence or not citations or invalid > 0 or bool(unsupported_numbers)
    checks = {"citations_valid": invalid == 0, "invalid_citations": invalid, "unsupported_numbers": unsupported_numbers, "pdf_layout_quotes_recovered": layout_recovered, "document_reference_removed":removed_reference, "method": "Canonical source quote and numeric claim checks; publication metadata is shown in citations. PDF whitespace alignment returns original source text. Semantic correctness is evaluated separately."}
    if refused:
        return {"answer": "I couldn't find sufficient supporting evidence in the documents you can access. Please ask the policy owner or add a relevant document.", "citations": [], "insufficient_evidence": True, "checks": checks}
    return {"answer": answer_text, "citations": citations, "insufficient_evidence": False, "checks": checks}
