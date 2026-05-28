"""MCP server exposing public CER evidence search tools.

The server intentionally uses only the Python standard library so it can run as
a local stdio MCP without extra deployment dependencies. Network-backed tools
return raw query metadata (URL/date/count) and degrade to structured errors
instead of fabricating "no risk" conclusions.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 20
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMBASE_DEFAULT_URL = "https://www.embase.com/search/results"
COCHRANE_DEFAULT_URL = "https://www.cochranelibrary.com/search"


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "DeerFlow-CER-Authoring/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DeerFlow-CER-Authoring/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _safe_call(url: str, parser: str = "json") -> tuple[dict[str, Any] | str | None, dict[str, Any] | None]:
    try:
        if parser == "json":
            return _fetch_json(url), None
        return _fetch_text(url), None
    except Exception as exc:
        return None, {"type": exc.__class__.__name__, "message": str(exc), "url": url}


def _ncbi_url(endpoint: str, params: dict[str, Any]) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return f"{NCBI_BASE}/{endpoint}?{urllib.parse.urlencode(clean, doseq=True)}"


def pubmed_search(query: str, retmax: int = 20, date_from: str = "", date_to: str = "") -> dict[str, Any]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max(0, min(int(retmax), 200)),
        "sort": "relevance",
    }
    if date_from or date_to:
        params["datetype"] = "pdat"
        params["mindate"] = date_from
        params["maxdate"] = date_to or _today()
    url = _ncbi_url("esearch.fcgi", params)
    data, error = _safe_call(url)
    if error:
        return _search_error("PubMed", query, url, error)
    assert isinstance(data, dict)
    result = data.get("esearchresult", {})
    ids = result.get("idlist", [])
    return {
        "status": "ok",
        "database": "PubMed",
        "query": query,
        "search_date": _today(),
        "url": url,
        "count": int(result.get("count", 0)),
        "returned_count": len(ids),
        "pmids": ids,
        "raw": result,
    }


def pubmed_fetch(pmids: list[str] | str) -> dict[str, Any]:
    id_list = _split_ids(pmids)
    url = _ncbi_url("esummary.fcgi", {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"})
    data, error = _safe_call(url)
    if error:
        return _search_error("PubMed", ",".join(id_list), url, error)
    assert isinstance(data, dict)
    result = data.get("result", {})
    articles = []
    for pmid in result.get("uids", []):
        entry = result.get(pmid, {})
        articles.append(
            {
                "pmid": pmid,
                "title": entry.get("title", ""),
                "authors": [author.get("name", "") for author in entry.get("authors", [])],
                "journal": entry.get("fulljournalname") or entry.get("source", ""),
                "pubdate": entry.get("pubdate", ""),
                "doi": _extract_article_id(entry, "doi"),
                "raw": entry,
            }
        )
    return {
        "status": "ok",
        "database": "PubMed",
        "search_date": _today(),
        "url": url,
        "count": len(articles),
        "articles": articles,
    }


def pubmed_fetch_abstracts(pmids: list[str] | str) -> dict[str, Any]:
    id_list = _split_ids(pmids)
    url = _ncbi_url("efetch.fcgi", {"db": "pubmed", "id": ",".join(id_list), "retmode": "xml"})
    data, error = _safe_call(url, parser="text")
    if error:
        return _search_error("PubMed abstracts", ",".join(id_list), url, error)
    assert isinstance(data, str)
    articles: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return _search_error("PubMed abstracts", ",".join(id_list), url, {"type": "ParseError", "message": str(exc), "url": url})
    for article in root.findall(".//PubmedArticle"):
        pmid = "".join(article.findtext(".//PMID") or "").strip()
        title = _xml_text(article.find(".//ArticleTitle"))
        abstract_parts = []
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            label = abstract_text.attrib.get("Label")
            part = _xml_text(abstract_text)
            if part:
                abstract_parts.append(f"{label}: {part}" if label else part)
        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "abstract": "\n".join(abstract_parts),
                "endpoint_candidates": _extract_endpoint_candidates("\n".join(abstract_parts)),
            }
        )
    return {
        "status": "ok",
        "database": "PubMed",
        "search_date": _today(),
        "url": url,
        "count": len(articles),
        "articles": articles,
    }


def pubmed_verify_citation(
    pmid: str = "",
    doi: str = "",
    title: str = "",
    first_author: str = "",
    year: str = "",
) -> dict[str, Any]:
    query = pmid or doi or title
    if not query:
        return {"status": "error", "verified": False, "reason": "pmid, doi, or title is required"}
    if pmid:
        fetched = pubmed_fetch(pmid)
    else:
        term = doi if doi else f'"{title}"'
        search = pubmed_search(term, retmax=5)
        ids = search.get("pmids", []) if search.get("status") == "ok" else []
        fetched = pubmed_fetch(ids[:5]) if ids else {"status": "ok", "articles": []}
    articles = fetched.get("articles", []) if fetched.get("status") == "ok" else []
    best = articles[0] if articles else {}
    checks = {
        "pmid_match": not pmid or best.get("pmid") == str(pmid),
        "doi_match": not doi or _norm(doi) == _norm(best.get("doi", "")),
        "title_match": not title or _loose_contains(title, best.get("title", "")),
        "author_match": not first_author or any(_norm(first_author) in _norm(author) for author in best.get("authors", [])),
        "year_match": not year or str(year) in str(best.get("pubdate", "")),
    }
    verified = bool(best) and all(checks.values())
    return {
        "status": "ok",
        "verified": verified,
        "query": query,
        "search_date": _today(),
        "checks": checks,
        "matched_article": best,
        "raw_fetch_status": fetched.get("status"),
    }


def europe_pmc_search(query: str, page_size: int = 25) -> dict[str, Any]:
    params = {"query": query, "format": "json", "pageSize": max(1, min(int(page_size), 100))}
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
    data, error = _safe_call(url)
    if error:
        return _search_error("Europe PMC", query, url, error)
    assert isinstance(data, dict)
    result = data.get("resultList", {}).get("result", [])
    return {
        "status": "ok",
        "database": "Europe PMC",
        "query": query,
        "search_date": _today(),
        "url": url,
        "count": int(data.get("hitCount", 0)),
        "returned_count": len(result),
        "records": result,
    }


def clinicaltrials_search(query: str, page_size: int = 25) -> dict[str, Any]:
    params = {"query.term": query, "format": "json", "pageSize": max(1, min(int(page_size), 100))}
    url = "https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(params)
    data, error = _safe_call(url)
    if error:
        return _search_error("ClinicalTrials.gov", query, url, error)
    assert isinstance(data, dict)
    studies = data.get("studies", [])
    return {
        "status": "ok",
        "database": "ClinicalTrials.gov",
        "query": query,
        "search_date": _today(),
        "url": url,
        "count": data.get("totalCount", len(studies)),
        "returned_count": len(studies),
        "records": studies,
    }


def euctr_search(query: str, page_size: int = 25) -> dict[str, Any]:
    """Create a reproducible EU Clinical Trials Register search record.

    EUCTR does not provide a stable open JSON API for all use cases. This tool
    records the official query URL and returns source-limited metadata rather
    than pretending a browser/manual search is a zero-result API search.
    """
    params = {"query": query}
    url = "https://www.clinicaltrialsregister.eu/ctr-search/search?" + urllib.parse.urlencode(params)
    return {
        "status": "source_unavailable",
        "database": "EU Clinical Trials Register",
        "query": query,
        "search_date": _today(),
        "url": url,
        "count": None,
        "returned_count": 0,
        "records": [],
        "page_size": max(1, min(int(page_size), 100)),
        "note": "Official EUCTR web search record generated. Manual/browser-assisted confirmation is required; do not interpret as no clinical trials.",
    }


def embase_availability_check() -> dict[str, Any]:
    return _subscription_availability(
        database="Embase",
        base_env="EMBASE_API_BASE",
        key_env="EMBASE_API_KEY",
        default_url=EMBASE_DEFAULT_URL,
    )


def embase_search(query: str, limit: int = 25, date_from: str = "", date_to: str = "") -> dict[str, Any]:
    return _subscription_search(
        database="Embase",
        query=query,
        limit=limit,
        base_env="EMBASE_API_BASE",
        key_env="EMBASE_API_KEY",
        default_url=EMBASE_DEFAULT_URL,
        extra_params={"date_from": date_from, "date_to": date_to},
    )


def cochrane_availability_check() -> dict[str, Any]:
    return _subscription_availability(
        database="Cochrane Library",
        base_env="COCHRANE_API_BASE",
        key_env="COCHRANE_API_KEY",
        default_url=COCHRANE_DEFAULT_URL,
    )


def cochrane_search(query: str, limit: int = 25, collection: str = "all") -> dict[str, Any]:
    return _subscription_search(
        database="Cochrane Library",
        query=query,
        limit=limit,
        base_env="COCHRANE_API_BASE",
        key_env="COCHRANE_API_KEY",
        default_url=COCHRANE_DEFAULT_URL,
        extra_params={"collection": collection},
    )


def cochrane_reviews_search(query: str, limit: int = 25) -> dict[str, Any]:
    return cochrane_search(query=query, limit=limit, collection="reviews")


def cochrane_trials_search(query: str, limit: int = 25) -> dict[str, Any]:
    return cochrane_search(query=query, limit=limit, collection="trials")


def fda_maude_search(search_terms: str, limit: int = 25) -> dict[str, Any]:
    return _openfda_search(
        "FDA MAUDE",
        "https://api.fda.gov/device/event.json",
        search_terms,
        max(1, min(int(limit), 100)),
    )


def fda_recall_search(search_terms: str, limit: int = 25) -> dict[str, Any]:
    return _openfda_search(
        "FDA Device Recall",
        "https://api.fda.gov/device/recall.json",
        search_terms,
        max(1, min(int(limit), 100)),
    )


def fda_510k_search(search_terms: str, limit: int = 25) -> dict[str, Any]:
    return _openfda_search(
        "FDA 510(k)",
        "https://api.fda.gov/device/510k.json",
        search_terms,
        max(1, min(int(limit), 100)),
    )


def accessgudid_search(search_terms: str, page_size: int = 25) -> dict[str, Any]:
    params = {"query": search_terms, "page_size": max(1, min(int(page_size), 100))}
    url = "https://accessgudid.nlm.nih.gov/api/v3/devices/search.json?" + urllib.parse.urlencode(params)
    data, error = _safe_call(url)
    if error:
        return _search_error("AccessGUDID", search_terms, url, error)
    assert isinstance(data, dict)
    records = data.get("gudid", {}).get("device", [])
    return {
        "status": "ok",
        "database": "AccessGUDID",
        "query": search_terms,
        "search_date": _today(),
        "url": url,
        "count": data.get("gudid", {}).get("total", len(records)),
        "returned_count": len(records),
        "records": records,
    }


def mhra_safety_search(search_terms: str) -> dict[str, Any]:
    return _public_web_record("MHRA Safety Alerts", "https://www.gov.uk/search/all", search_terms)


def bfarm_safety_search(search_terms: str) -> dict[str, Any]:
    return _public_web_record("BfArM Safety Information", "https://www.bfarm.de/SiteGlobals/Forms/Suche/EN/Expertensuche_Formular.html", search_terms)


def swissmedic_safety_search(search_terms: str) -> dict[str, Any]:
    return _public_web_record("Swissmedic Safety Communications", "https://www.swissmedic.ch/swissmedic/en/home/search.html", search_terms)


def eudamed_device_search(search_terms: str) -> dict[str, Any]:
    return _source_limited_web_record(
        "EUDAMED public device/module search",
        "https://ec.europa.eu/tools/eudamed/#/screen/search-device",
        search_terms,
        "EUDAMED public module access may require manual browser interaction and may not expose complete legacy CE market data.",
    )


def eudamed_vigilance_search(search_terms: str) -> dict[str, Any]:
    return _source_limited_web_record(
        "EUDAMED vigilance / safety notice search",
        "https://ec.europa.eu/tools/eudamed/#/screen/search-vigilance",
        search_terms,
        "EUDAMED vigilance/public safety information access is source-limited; manual confirmation is required before any AE conclusion.",
    )


def nz_medsafe_safety_search(search_terms: str) -> dict[str, Any]:
    return _public_web_record("New Zealand Medsafe safety communications", "https://www.medsafe.govt.nz/search/search.asp", search_terms)


def build_search_run_record(
    database: str,
    query: str,
    url: str = "",
    result_count: int = 0,
    deduped_count: int = 0,
    included_count: int = 0,
    excluded_count: int = 0,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "status": "ok",
        "search_run": {
            "database": database,
            "query": query,
            "url": url,
            "search_date": _today(),
            "result_count": result_count,
            "deduped_count": deduped_count,
            "included_count": included_count,
            "excluded_count": excluded_count,
            "notes": notes,
        },
    }


def _subscription_availability(database: str, base_env: str, key_env: str, default_url: str) -> dict[str, Any]:
    base = os.getenv(base_env, "").strip()
    key = os.getenv(key_env, "").strip()
    status = "ok" if base and key else "auth_required"
    missing = [name for name, value in ((base_env, base), (key_env, key)) if not value]
    return {
        "status": status,
        "database": database,
        "search_date": _today(),
        "url": base or default_url,
        "count": None,
        "returned_count": 0,
        "records": [],
        "missing_configuration": missing,
        "note": "Subscription/API access is available." if status == "ok" else "Subscription/API configuration is required; do not interpret as no records.",
    }


def _subscription_search(
    database: str,
    query: str,
    limit: int,
    base_env: str,
    key_env: str,
    default_url: str,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = os.getenv(base_env, "").strip()
    key = os.getenv(key_env, "").strip()
    params = {"query": query, "q": query, "limit": max(1, min(int(limit), 100))}
    params.update({key_: value for key_, value in (extra_params or {}).items() if value not in (None, "")})
    display_url = (base or default_url) + "?" + urllib.parse.urlencode(params)
    if not base or not key:
        return {
            "status": "auth_required",
            "database": database,
            "query": query,
            "search_date": _today(),
            "url": display_url,
            "count": None,
            "returned_count": 0,
            "records": [],
            "missing_configuration": [name for name, value in ((base_env, base), (key_env, key)) if not value],
            "note": "Subscription/API access is required; this is a source limitation record, not a zero-result search.",
        }
    req = urllib.request.Request(display_url, headers={"User-Agent": "DeerFlow-CER-Authoring/1.0", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return _search_error(database, query, display_url, {"type": exc.__class__.__name__, "message": str(exc), "url": display_url})
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"raw_text": payload[:5000]}
    records = _subscription_records(data)
    count = _subscription_count(data, records)
    return {
        "status": "ok",
        "database": database,
        "query": query,
        "search_date": _today(),
        "url": display_url,
        "count": count,
        "returned_count": len(records),
        "records": records,
        "raw": data,
    }


def _subscription_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("records", "results", "items", "documents", "articles"):
        value = data.get(key)
        if isinstance(value, list):
            return [item if isinstance(item, dict) else {"value": item} for item in value]
    return []


def _subscription_count(data: dict[str, Any], records: list[dict[str, Any]]) -> int:
    for key in ("count", "total", "totalResults", "hitCount", "result_count"):
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    meta = data.get("meta")
    if isinstance(meta, dict):
        for key in ("count", "total", "totalResults"):
            value = meta.get(key)
            if isinstance(value, int):
                return value
    return len(records)


def _openfda_search(database: str, endpoint: str, search_terms: str, limit: int) -> dict[str, Any]:
    params = {"search": search_terms, "limit": limit}
    url = endpoint + "?" + urllib.parse.urlencode(params)
    data, error = _safe_call(url)
    if error:
        return _search_error(database, search_terms, url, error)
    assert isinstance(data, dict)
    records = data.get("results", [])
    return {
        "status": "ok",
        "database": database,
        "query": search_terms,
        "search_date": _today(),
        "url": url,
        "count": data.get("meta", {}).get("results", {}).get("total", len(records)),
        "returned_count": len(records),
        "records": records,
    }


def _public_web_record(database: str, base_url: str, search_terms: str) -> dict[str, Any]:
    params = {"q": search_terms}
    url = base_url + "?" + urllib.parse.urlencode(params)
    return {
        "status": "ok",
        "database": database,
        "query": search_terms,
        "search_date": _today(),
        "url": url,
        "count": 0,
        "returned_count": 0,
        "records": [],
        "note": "Public web safety source registered for reproducible manual/API-assisted review; no risk conclusion may be inferred from count=0 without source access confirmation.",
    }


def _source_limited_web_record(database: str, base_url: str, search_terms: str, note: str) -> dict[str, Any]:
    url = base_url + ("&" if "?" in base_url else "?") + urllib.parse.urlencode({"q": search_terms})
    return {
        "status": "source_unavailable",
        "database": database,
        "query": search_terms,
        "search_date": _today(),
        "url": url,
        "count": None,
        "returned_count": 0,
        "records": [],
        "note": note,
    }


def _search_error(database: str, query: str, url: str, error: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "source_unavailable",
        "database": database,
        "query": query,
        "search_date": _today(),
        "url": url,
        "count": None,
        "returned_count": 0,
        "records": [],
        "error": error,
    }


def _split_ids(ids: list[str] | str) -> list[str]:
    if isinstance(ids, str):
        return [item.strip() for item in ids.split(",") if item.strip()]
    return [str(item).strip() for item in ids if str(item).strip()]


def _extract_article_id(entry: dict[str, Any], kind: str) -> str:
    for article_id in entry.get("articleids", []):
        if article_id.get("idtype", "").lower() == kind.lower():
            return article_id.get("value", "")
    return ""


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _loose_contains(expected: str, actual: str) -> bool:
    expected_norm = _norm(expected)
    actual_norm = _norm(actual)
    return bool(expected_norm) and (expected_norm in actual_norm or actual_norm in expected_norm)


def _xml_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _extract_endpoint_candidates(text: str) -> list[dict[str, str]]:
    candidates = []
    if not text:
        return candidates
    sentences = re.split(r"(?<=[.!?])\s+", text)
    endpoint_words = re.compile(
        r"\b(success|efficacy|safety|adverse|complication|mortality|recurrence|freedom|endpoint|outcome|rate|incidence|stone-free|ablation|isolation|follow-up|months?|days?)\b",
        re.IGNORECASE,
    )
    number_words = re.compile(r"(\d+(?:\.\d+)?\s*(?:%|patients?|subjects?|cases?|months?|days?|years?)|n\s*=\s*\d+)", re.IGNORECASE)
    for sentence in sentences:
        if endpoint_words.search(sentence) and number_words.search(sentence):
            candidates.append({"sentence": sentence[:600]})
        if len(candidates) >= 12:
            break
    return candidates


class MCPServer:
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, name: str, func: Any, description: str, parameters: dict[str, dict[str, Any]]) -> None:
        self.tools[name] = {
            "function": func,
            "schema": {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": parameters,
                    "required": [key for key, spec in parameters.items() if spec.get("required")],
                },
            },
        }

    def run(self) -> None:
        print(f"[{self.name}] MCP server starting...", file=sys.stderr)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle(request)
            if response is None:
                continue
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})
        is_notification = "id" not in request

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }
        if method == "notifications/initialized" or is_notification:
            return None
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [tool["schema"] for tool in self.tools.values()]}}
        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            if name not in self.tools:
                return self._tool_error(req_id, f"Tool not found: {name}")
            try:
                result = self.tools[name]["function"](**arguments)
            except Exception as exc:
                return self._tool_error(req_id, f"Tool error: {exc}")
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    @staticmethod
    def _tool_error(req_id: Any, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": message}], "isError": True}}


def main() -> None:
    server = MCPServer("cer-public-evidence", "1.0.0")
    _register_tools(server)
    print(f"[cer-public-evidence] Registered {len(server.tools)} tools", file=sys.stderr)
    server.run()


def _register_tools(server: MCPServer) -> None:
    text = {"type": "string"}
    integer = {"type": "integer"}
    array_string = {"type": "array", "items": {"type": "string"}}
    server.register_tool("pubmed_search", pubmed_search, "Search PubMed using NCBI E-utilities and return raw reproducible search metadata.", {"query": text, "retmax": integer, "date_from": text, "date_to": text})
    server.register_tool("pubmed_fetch", pubmed_fetch, "Fetch PubMed article summaries for one or more PMIDs.", {"pmids": {"oneOf": [array_string, text], "description": "PMID list or comma-separated PMID string"}})
    server.register_tool("pubmed_fetch_abstracts", pubmed_fetch_abstracts, "Fetch PubMed abstracts/full abstract XML for endpoint-level extraction where available.", {"pmids": {"oneOf": [array_string, text], "description": "PMID list or comma-separated PMID string"}})
    server.register_tool("pubmed_verify_citation", pubmed_verify_citation, "Verify PMID/DOI/title/author/year citation consistency before allowing pivotal evidence.", {"pmid": text, "doi": text, "title": text, "first_author": text, "year": text})
    server.register_tool("europe_pmc_search", europe_pmc_search, "Search Europe PMC and return raw reproducible metadata.", {"query": text, "page_size": integer})
    server.register_tool("clinicaltrials_search", clinicaltrials_search, "Search ClinicalTrials.gov v2 study records.", {"query": text, "page_size": integer})
    server.register_tool("euctr_search", euctr_search, "Create a reproducible EU Clinical Trials Register source-limited search record.", {"query": text, "page_size": integer})
    server.register_tool("embase_search", embase_search, "Search Embase through configured subscription/API access or return an auth-required source limitation record.", {"query": text, "limit": integer, "date_from": text, "date_to": text})
    server.register_tool("embase_availability_check", embase_availability_check, "Check whether Embase API/subscription configuration is available.", {})
    server.register_tool("cochrane_search", cochrane_search, "Search Cochrane Library through configured API access or return an auth-required source limitation record.", {"query": text, "limit": integer, "collection": text})
    server.register_tool("cochrane_reviews_search", cochrane_reviews_search, "Search Cochrane Reviews through configured API access or return an auth-required source limitation record.", {"query": text, "limit": integer})
    server.register_tool("cochrane_trials_search", cochrane_trials_search, "Search Cochrane Trials through configured API access or return an auth-required source limitation record.", {"query": text, "limit": integer})
    server.register_tool("cochrane_availability_check", cochrane_availability_check, "Check whether Cochrane API/subscription configuration is available.", {})
    server.register_tool("fda_maude_search", fda_maude_search, "Search openFDA device adverse event records (MAUDE).", {"search_terms": text, "limit": integer})
    server.register_tool("fda_recall_search", fda_recall_search, "Search openFDA device recall records.", {"search_terms": text, "limit": integer})
    server.register_tool("fda_510k_search", fda_510k_search, "Search openFDA 510(k) records for device/equivalence scouting.", {"search_terms": text, "limit": integer})
    server.register_tool("accessgudid_search", accessgudid_search, "Search AccessGUDID public device records.", {"search_terms": text, "page_size": integer})
    server.register_tool("mhra_safety_search", mhra_safety_search, "Create reproducible MHRA safety search record.", {"search_terms": text})
    server.register_tool("bfarm_safety_search", bfarm_safety_search, "Create reproducible BfArM safety search record.", {"search_terms": text})
    server.register_tool("swissmedic_safety_search", swissmedic_safety_search, "Create reproducible Swissmedic safety search record.", {"search_terms": text})
    server.register_tool("eudamed_device_search", eudamed_device_search, "Create reproducible EUDAMED public device/market status search record.", {"search_terms": text})
    server.register_tool("eudamed_vigilance_search", eudamed_vigilance_search, "Create reproducible EUDAMED vigilance/safety source-limited search record.", {"search_terms": text})
    server.register_tool("nz_medsafe_safety_search", nz_medsafe_safety_search, "Create reproducible New Zealand Medsafe safety search record.", {"search_terms": text})
    server.register_tool("build_search_run_record", build_search_run_record, "Build a normalized search-run registry record from executed search metadata.", {"database": text, "query": text, "url": text, "result_count": integer, "deduped_count": integer, "included_count": integer, "excluded_count": integer, "notes": text})


if __name__ == "__main__":
    main()
