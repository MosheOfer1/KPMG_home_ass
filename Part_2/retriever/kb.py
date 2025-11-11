from __future__ import annotations

import glob
import hashlib
import html
import os
import pickle
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterable, Dict

from bs4 import BeautifulSoup

from Part_2.azure_integration import IEmbeddingsClient
from Part_2.core_models import HMO, Tier
from Part_2.retriever.kb_interfaces import IKnowledgeBase


# ----------------------------- Data model -----------------------------

@dataclass
class KBChunk:
    text: str              # normalized, embed-ready text (one atomic “fact”)
    source_uri: str        # file://...#anchor
    hmo: Optional[HMO]     # Maccabi / Meuhedet / Clalit / None
    tier_tags: Tuple[str, ...]  # ("זהב","כסף",...)
    section: Optional[str] # e.g., "רפואה משלימה"
    service: Optional[str] # e.g., "דיקור סיני", "סתימות"
    kind: str = "benefit"  # "benefit" | "contact" | "blurb"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_uri": self.source_uri,
            "hmo": self.hmo.value if self.hmo else None,
            "tier_tags": list(self.tier_tags),
            "section": self.section,
            "service": self.service,
            "kind": self.kind,
        }

    @staticmethod
    def from_dict(d: dict) -> "KBChunk":
        hmo = HMO(d["hmo"]) if d.get("hmo") is not None else None
        return KBChunk(
            text=d["text"],
            source_uri=d["source_uri"],
            hmo=hmo,
            tier_tags=tuple(d.get("tier_tags", ())),
            section=d.get("section"),
            service=d.get("service"),
            kind=d.get("kind", "benefit"),
        )

# ----------------------------- KB builder -----------------------------

class HtmlKB(IKnowledgeBase):
    """
    HTML-aware KB:
      - Extracts records from headings, tables, lists
      - Emits one chunk per (service × HMO × tier) benefit, plus contacts/blurbs
      - Embeds once with persistent cache
    """
    CACHE_VERSION = "2"  # bumped for new serialization

    def __init__(
        self,
        kb_dir: str,
        embedder: IEmbeddingsClient,
        *,
        cache_dir: str = ".kb_cache",
        embeddings_deployment: Optional[str] = None,
    ):
        self.kb_dir = kb_dir
        self.embedder = embedder
        self.cache_dir = cache_dir
        self.embeddings_deployment = embeddings_deployment or getattr(embedder, "default_deployment", "unknown")

        self._chunks: List[KBChunk] = []
        self._vectors: List[List[float]] = []

        os.makedirs(self.cache_dir, exist_ok=True)
        manifest = self._manifest()
        self._fingerprint = self._fingerprint_from_manifest(manifest)
        cache_path = os.path.join(self.cache_dir, f"kb_{self._fingerprint}.pkl")

        if os.path.exists(cache_path):
            self._load_cache(cache_path)
        else:
            self._build_and_cache(cache_path, manifest)

    # --------------------------- Public API ---------------------------

    def search(self, query: str, *, hmo: Optional[HMO], tier: Optional[Tier], top_k: int = 6) -> List[KBChunk]:
        if not self._chunks:
            return []
        qv = self.embedder.embed_texts([query])[0]
        scored: List[tuple[float, KBChunk]] = []
        for vec, ch in zip(self._vectors, self._chunks):
            score = self._cos(qv, vec)
            if hmo and ch.hmo and ch.hmo != hmo: score *= 0.75
            if tier and (tier in ch.tier_tags):   score *= 1.08
            scored.append((score, ch))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    # ------------------------ Build & cache --------------------------

    def _build_and_cache(self, cache_path: str, manifest: list[dict]) -> None:
        for p in [m["path"] for m in manifest]:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                html_str = f.read()
            self._chunks.extend(self._extract_chunks_from_html(p, html_str))

        if self._chunks:
            # Embed a normalized view for better retrieval quality
            payloads = [self._normalize_for_embedding(c) for c in self._chunks]
            self._vectors = self.embedder.embed_texts(payloads)

        payload = {
            "version": self.CACHE_VERSION,
            "embeddings_deployment": self.embeddings_deployment,
            "manifest": manifest,
            "chunks": [c.to_dict() for c in self._chunks],
            "vectors": self._vectors,
        }
        with open(cache_path, "wb") as f:
            pickle.dump(payload, f)

    def _load_cache(self, cache_path: str) -> None:
        with open(cache_path, "rb") as f:
            payload = pickle.load(f)
        if payload.get("version") != self.CACHE_VERSION \
           or payload.get("embeddings_deployment") != self.embeddings_deployment:
            os.remove(cache_path); raise FileNotFoundError("cache mismatch")
        self._chunks  = [KBChunk.from_dict(d) for d in payload.get("chunks", [])]
        self._vectors = payload.get("vectors", [])

    # ------------------------- Extractors ----------------------------

    def _extract_chunks_from_html(self, path: str, html_str: str) -> List[KBChunk]:
        soup = BeautifulSoup(html_str, "html.parser")
        chunks: List[KBChunk] = []
        section = None

        # Track the current section by nearest preceding h1/h2/h3
        for node in soup.find_all(["h1","h2","h3","table","ul","p"]):
            if node.name in ("h1","h2","h3"):
                section = self._clean(node.get_text(" "))
                continue

            if node.name == "table":
                chunks.extend(self._extract_table_records(path, node, section))
            elif node.name == "ul":
                chunks.extend(self._extract_list_contacts(path, node, section))
            elif node.name == "p":
                txt = self._clean(node.get_text(" "))
                if txt:
                    chunks.append(KBChunk(
                        text=txt, source_uri=f"file://{path}#p{hash(txt)%10_000}",
                        hmo=None, tier_tags=(), section=section, service=None, kind="blurb"
                    ))
        return chunks

    def _extract_table_records(self, path: str, table, section: Optional[str]) -> List[KBChunk]:
        """Build atomic records: (service × hmo × tier) with benefit text."""
        rows = table.find_all("tr")
        if not rows: return []
        headers = [self._clean(th.get_text(" ")) for th in rows[0].find_all(["th","td"])]
        # Try to identify HMO columns
        hmo_cols: Dict[int, HMO] = {}
        for idx, h in enumerate(headers):
            low = (h or "").lower()
            if "מכבי" in low or "maccabi" in low:   hmo_cols[idx] = HMO.MACCABI
            if "מאוחדת" in low or "meuhedet" in low:hmo_cols[idx] = HMO.MEUHEDET
            if "כללית" in low or "clalit" in low:   hmo_cols[idx] = HMO.CLALIT

        out: List[KBChunk] = []
        for r_i, tr in enumerate(rows[1:], start=1):
            cells = tr.find_all(["td","th"])
            if not cells: continue
            service = self._clean(cells[0].get_text(" ")) if cells else None

            for c_i, td in enumerate(cells[1:], start=1):
                hmo = hmo_cols.get(c_i)
                if not hmo: continue
                cell_text = self._clean(td.get_text(" ", strip=True))
                # Split tiers inside cell (bold labels or keywords)
                for tier_label, benefit in self._split_tiers(cell_text):
                    out.append(KBChunk(
                        text=f"{benefit}",
                        source_uri=f"file://{path}#t{r_i}_{c_i}",
                        hmo=hmo,
                        tier_tags=(tier_label,) if tier_label else (),
                        section=section,
                        service=service,
                        kind="benefit",
                    ))
        return out

    def _extract_list_contacts(self, path: str, ul, section: Optional[str]) -> List[KBChunk]:
        """
        Handles three common <ul> patterns:
          1) Services bullets (no phones/urls)           -> kind="service",   hmo=None
          2) HMO contact bullets with phones (and ext)   -> kind="contact",   hmo=parsed
          3) 'More info' bullets with phone + URL        -> kind="contact",   hmo=parsed, text includes url
        """
        out: List[KBChunk] = []

        PHONE_RE = re.compile(
            r"(?:\d{2,3}-\d{6,7}|"
            r"\d{1}-\d{3}-\d{2}-\d{2}-\d{2}|"  # 1-700-50-53-53 style
            r"\*?\d{3,4})"
        )
        EXT_RE = re.compile(r"שלוחה\s*(\d+)")

        def li_urls(li) -> List[str]:
            return [a.get("href") for a in li.find_all("a") if a.get("href")]

        for li in ul.find_all("li", recursive=False):
            raw_txt = li.get_text(" ", strip=True)
            txt = self._clean(raw_txt)
            if not txt:
                continue

            urls = li_urls(li)
            phones = PHONE_RE.findall(txt)
            hmo = self._guess_hmo_from_text(txt)
            ext = EXT_RE.search(txt)
            has_phone = bool(phones)
            has_url = bool(urls)

            # Case 2/3: contacts (with optional URL)
            if has_phone or ("טלפון" in txt) or has_url:
                bits = []
                if phones: bits.append("; ".join(phones))
                if ext:    bits.append(f"שלוחה {ext.group(1)}")
                if urls:   bits.append("; ".join(urls))
                payload = " | ".join(bits) if bits else txt
                out.append(KBChunk(
                    text=payload,
                    source_uri=f"file://{path}#c{abs(hash(txt)) % 10_000}",
                    hmo=hmo,
                    tier_tags=(),
                    section=section,
                    service=None,
                    kind="contact",
                ))
                continue

            # Case 1: plain services bullet (no phones/urls)
            out.append(KBChunk(
                text=txt,
                source_uri=f"file://{path}#s{abs(hash(txt)) % 10_000}",
                hmo=None,
                tier_tags=(),
                section=section,
                service=txt,  # treat bullet as a service name
                kind="service",
            ))

        return out

    # ------------------------- Utilities -----------------------------

    @staticmethod
    def _split_tiers(cell_text: str) -> Iterable[tuple[Optional[str], str]]:
        """
        Extract inner 'זהב/כסף/ארד' blocks if present; else yield the whole cell once.
        Works even if markup is lost (uses keywords).
        """
        # Try explicit tier blocks like: "זהב: 70% ...\nכסף: 50% ..."
        parts = re.split(r"(?=(?:זהב|כסף|ארד)\s*[:：])", cell_text)
        if len(parts) > 1:
            for p in parts:
                m = re.match(r"(זהב|כסף|ארד)\s*[:：]\s*(.+)", p, re.S)
                if m:
                    yield m.group(1), m.group(2).strip()
            return
        yield None, cell_text

    @staticmethod
    def _clean(s: str | None) -> str:
        if not s: return ""
        s = html.unescape(s)
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n+", " ", s)
        return s.strip()

    @staticmethod
    def _guess_hmo_from_text(s: str) -> Optional[HMO]:
        low = s.lower()
        if "מכבי" in low or "maccabi" in low:   return HMO.MACCABI
        if "מאוחדת" in low or "meuhedet" in low:return HMO.MEUHEDET
        if "כללית" in low or "clalit" in low:   return HMO.CLALIT
        return None

    @staticmethod
    def _cos(a: List[float], b: List[float]) -> float:
        import math
        dot = sum(x*y for x, y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a)) or 1.0
        nb = math.sqrt(sum(y*y for y in b)) or 1.0
        return dot/(na*nb)

    def _normalize_for_embedding(self, c: KBChunk) -> str:
        """Compact, fielded string improves retrieval quality."""
        bits = []
        if c.section: bits.append(f"section:{c.section}")
        if c.service: bits.append(f"service:{c.service}")
        if c.hmo:     bits.append(f"hmo:{c.hmo.value}")
        if c.tier_tags: bits.append(f"tier:{'|'.join(c.tier_tags)}")
        bits.append(f"kind:{c.kind}")
        bits.append(f"text:{c.text}")
        return " | ".join(bits)

    # ---------------------- Manifest & fingerprint -------------------

    def _manifest(self) -> list[dict]:
        files = sorted(glob.glob(os.path.join(self.kb_dir, "**/*.html"), recursive=True))
        out: list[dict] = []
        for p in files:
            try:
                st = os.stat(p)
                out.append({"path": os.path.abspath(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns})
            except OSError:
                continue
        return out

    def _fingerprint_from_manifest(self, manifest: list[dict]) -> str:
        h = hashlib.sha256()
        h.update(f"ver:{self.CACHE_VERSION}\n".encode())
        h.update(f"deploy:{self.embeddings_deployment}\n".encode())
        for m in manifest:
            h.update(f"{m['path']}|{m['size']}|{m['mtime_ns']}\n".encode())
        return h.hexdigest()[:16]
