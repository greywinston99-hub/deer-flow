"""Tests for CER public evidence MCP helpers."""

from __future__ import annotations

import time

from deerflow.mcp import cer_public_evidence_server as server
from deerflow.mcp.stdio_compat_bridge import _is_invalid_notification_response


def test_pubmed_verify_citation_passes_known_mock(monkeypatch):
    def fake_pubmed_fetch(pmids):
        return {
            "status": "ok",
            "articles": [
                {
                    "pmid": "42014630",
                    "title": "Flexible and navigable suction ureteral access sheath trial",
                    "authors": ["Alhefnawy MA", "Other A"],
                    "journal": "Journal",
                    "pubdate": "2026",
                    "doi": "10.1000/mock",
                }
            ],
        }

    monkeypatch.setattr(server, "pubmed_fetch", fake_pubmed_fetch)

    result = server.pubmed_verify_citation(
        pmid="42014630",
        title="Flexible and navigable suction ureteral access sheath trial",
        first_author="Alhefnawy",
        year="2026",
    )

    assert result["verified"] is True
    assert result["checks"]["pmid_match"] is True
    assert result["matched_article"]["pmid"] == "42014630"


def test_pubmed_verify_citation_blocks_mismatch(monkeypatch):
    def fake_pubmed_fetch(pmids):
        return {
            "status": "ok",
            "articles": [
                {
                    "pmid": "1",
                    "title": "Different title",
                    "authors": ["Different Author"],
                    "pubdate": "1999",
                    "doi": "",
                }
            ],
        }

    monkeypatch.setattr(server, "pubmed_fetch", fake_pubmed_fetch)

    result = server.pubmed_verify_citation(
        pmid="42014630",
        title="Flexible and navigable suction ureteral access sheath trial",
        first_author="Alhefnawy",
        year="2026",
    )

    assert result["verified"] is False
    assert result["checks"]["pmid_match"] is False


def test_openfda_search_returns_query_date_count_and_url(monkeypatch):
    def fake_safe_call(url, parser="json"):
        return {"meta": {"results": {"total": 2}}, "results": [{"id": "a"}, {"id": "b"}]}, None

    monkeypatch.setattr(server, "_safe_call", fake_safe_call)

    result = server.fda_maude_search("ureteral access sheath", limit=2)

    assert result["status"] == "ok"
    assert result["database"] == "FDA MAUDE"
    assert result["query"] == "ureteral access sheath"
    assert result["count"] == 2
    assert "api.fda.gov/device/event.json" in result["url"]


def test_pubmed_search_records_retrieval_gap_when_count_without_pmids(monkeypatch):
    def fake_safe_call(url, parser="json"):
        return {"esearchresult": {"count": "5", "idlist": []}}, None

    monkeypatch.setattr(server, "_safe_call", fake_safe_call)
    monkeypatch.setattr(server, "_simplify_search_query", lambda query: query)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    result = server.pubmed_search("SPECT image processing", retmax=3)

    assert result["status"] == "ok"
    assert result["count"] == 5
    assert result["returned_count"] == 0
    assert result["pmids"] == []
    assert "retrieval_gap_note" in result


def test_embase_without_credentials_returns_auth_required(monkeypatch):
    monkeypatch.delenv("EMBASE_API_BASE", raising=False)
    monkeypatch.delenv("EMBASE_API_KEY", raising=False)
    monkeypatch.delenv("ELSEVIER_API_KEY", raising=False)

    result = server.embase_search("atrial fibrillation ablation", limit=5)

    assert result["status"] == "auth_required"
    assert result["database"] == "Embase"
    assert result["count"] is None
    assert result["returned_count"] == 0
    assert "not a zero-result search" in result["note"]


def test_cochrane_without_credentials_returns_auth_required(monkeypatch):
    monkeypatch.delenv("COCHRANE_API_BASE", raising=False)
    monkeypatch.delenv("COCHRANE_API_KEY", raising=False)

    result = server.cochrane_reviews_search("single-use ureteroscope", limit=5)

    assert result["status"] == "auth_required"
    assert result["database"] == "Cochrane Library"
    assert result["count"] is None
    assert result["returned_count"] == 0
    assert "not a zero-result search" in result["note"]


def test_euctr_and_eudamed_are_source_limitation_records():
    euctr = server.euctr_search("mock equivalent device", page_size=10)
    eudamed = server.eudamed_device_search("mock device")
    eudamed_vig = server.eudamed_vigilance_search("mock device")
    nz = server.nz_medsafe_safety_search("mock device")

    assert euctr["status"] == "source_unavailable"
    assert euctr["count"] is None
    assert "clinicaltrialsregister.eu" in euctr["url"]
    assert eudamed["status"] == "source_unavailable"
    assert "eudamed" in eudamed["url"].lower()
    assert eudamed_vig["status"] == "source_unavailable"
    assert nz["database"] == "New Zealand Medsafe safety communications"


def test_subscription_search_with_mock_response(monkeypatch):
    monkeypatch.setenv("EMBASE_API_BASE", "https://example.test/embase")
    monkeypatch.setenv("EMBASE_API_KEY", "secret")
    monkeypatch.delenv("EMBASE_PROXY_URL", raising=False)

    def fake_fetch(url, headers, timeout=20):
        assert headers["X-ELS-APIKey"] == "secret"
        assert "query=mock+query" in url
        assert "count=5" in url
        return '{"total": 1, "results": [{"title": "Mock Embase record"}]}'

    monkeypatch.setattr(server, "_fetch_embase_payload", fake_fetch)

    result = server.embase_search("mock query", limit=5)

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["returned_count"] == 1
    assert result["records"][0]["title"] == "Mock Embase record"


def test_embase_parses_elsevier_search_results_shape(monkeypatch):
    monkeypatch.setenv("EMBASE_API_BASE", "https://example.test/embase")
    monkeypatch.setenv("EMBASE_API_KEY", "secret")
    monkeypatch.delenv("EMBASE_PROXY_URL", raising=False)

    monkeypatch.setattr(
        server,
        "_fetch_embase_payload",
        lambda url, headers, timeout=20: (
            '{"search-results": {"opensearch:totalResults": "1", '
            '"entry": [{"dc:title": "Elsevier Embase record", "dc:identifier": "EMB-1", '
            '"prism:doi": "10.1000/embase", "prism:publicationName": "Journal"}]}}'
        ),
    )

    result = server.embase_search("elsevier query", limit=5)

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["returned_count"] == 1
    assert result["records"][0]["title"] == "Elsevier Embase record"
    assert result["records"][0]["embase_id"] == "EMB-1"
    assert result["records"][0]["doi"] == "10.1000/embase"


def test_embase_uses_dedicated_proxy_when_configured(monkeypatch):
    monkeypatch.setenv("EMBASE_API_BASE", "https://example.test/embase")
    monkeypatch.setenv("EMBASE_API_KEY", "secret")
    monkeypatch.setenv("EMBASE_PROXY_URL", "http://127.0.0.1:7890")
    captured = {}

    def fake_fetch(url, headers, timeout=20):
        captured["url"] = url
        captured["proxy"] = server._embase_proxy_url()
        return '{"total": 0, "results": []}'

    monkeypatch.setattr(server, "_fetch_embase_payload", fake_fetch)

    result = server.embase_search("proxy query", limit=1)

    assert result["status"] == "ok"
    assert captured["url"].startswith("https://example.test/embase?")
    assert captured["proxy"] == "http://127.0.0.1:7890"


def test_compat_bridge_filters_id_null_notification_response():
    assert _is_invalid_notification_response('{"jsonrpc":"2.0","id":null,"result":{}}') is True
    assert _is_invalid_notification_response('{"jsonrpc":"2.0","id":1,"result":{}}') is False
