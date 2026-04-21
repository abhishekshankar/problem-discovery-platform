"""Mocked smoke: one RawRecord through pre_filter per new collector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from problem_discovery.signal.collectors.google_ads_transparency import GoogleAdsTransparencyCollector
from problem_discovery.signal.collectors.meta_ad_library import MetaAdLibraryCollector
from problem_discovery.signal.collectors.sec_filings import SECFilingsCollector
from problem_discovery.signal.collectors.youtube_comments import YouTubeCommentsCollector
from problem_discovery.signal.collectors.tier2 import ListenNotesCollector, ProfoundCollector
from problem_discovery.signal.collectors.tier3 import (
    AppFollowCollector,
    CapterraCollector,
    G2Collector,
    IndeedCollector,
    ProductHuntCollector,
    UpworkCollector,
)


@patch("problem_discovery.signal.collectors.youtube_comments.requests.get")
def test_youtube_comments(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "items": [
                {
                    "id": "c1",
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "textDisplay": "This is a long enough comment for the gate.",
                                "authorDisplayName": "u1",
                                "publishedAt": "2024-01-01T00:00:00Z",
                            }
                        }
                    },
                }
            ]
        },
    )
    col = YouTubeCommentsCollector(api_key="k", video_ids=["vid1"])
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.sec_filings.requests.get")
def test_sec_filings(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "name": "TestCo",
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2024-02-01"],
                    "accessionNumber": ["0001234567-24-000001"],
                }
            },
        },
    )
    col = SECFilingsCollector(ciks=["1"], user_agent="SignalTest contact@test.example")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.meta_ad_library.requests.get")
def test_meta_ads(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "data": [
                {
                    "id": "ad1",
                    "ad_creation_time": "2024-03-01",
                    "ad_snapshot_url": "https://example.com/s",
                    "ad_creative_bodies": ["Buy our B2B solution for compliance headaches."],
                    "page_name": "Acme",
                }
            ]
        },
    )
    col = MetaAdLibraryCollector(access_token="t")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.google_ads_transparency.requests.get")
def test_google_ads_transparency(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"id": "a1", "name": "Advertiser", "extra": "x" * 30}],
    )
    col = GoogleAdsTransparencyCollector()
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier2.requests.get")
def test_listen_notes(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "results": [
                {
                    "id": "ep1",
                    "title_original": "Pod ep",
                    "description_original": "D" * 40,
                    "pub_date_ms": 1700000000000,
                    "listennotes_url": "https://ln.test/ep1",
                }
            ]
        },
    )
    col = ListenNotesCollector(api_key="k", q="x")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier2.requests.post")
def test_profound(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
    col = ProfoundCollector(api_key="k", base_url="https://api.example.com")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier3.apify_base.requests.post")
def test_apify_g2(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"url": "https://g2.com/p", "title": "t" * 25, "text": "review " * 5}],
    )
    col = G2Collector(product_url="https://g2.com/products/x", token="tok")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier3.apify_base.requests.post")
def test_apify_capterra_upwork_indeed(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: [{"url": "https://x.com", "body": "word " * 10}],
    )
    for col in (
        CapterraCollector(listing_url="https://capterra.com/x", token="t"),
        UpworkCollector(search_url="https://upwork.com/nx/search/jobs/", token="t"),
        IndeedCollector(jobs_url="https://indeed.com/q-dev-jobs.html", token="t"),
    ):
        rec = next(col.fetch(None, "r"))
        assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier3.appfollow.requests.get")
def test_appfollow(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"reviews": [{"id": "r1", "review": "Great app but billing is confusing " * 2}]},
    )
    col = AppFollowCollector(token="t")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)


@patch("problem_discovery.signal.collectors.tier3.producthunt.requests.post")
def test_producthunt(mock_post):
    ph_payload = {
        "data": {
            "posts": {
                "edges": [
                    {
                        "node": {
                            "id": "1",
                            "name": "thing",
                            "createdAt": "2024-01-01T00:00:00Z",
                            "url": "https://ph.test/1",
                            "tagline": "tag " * 10,
                            "description": "desc " * 10,
                            "votesCount": 3,
                        }
                    }
                ]
            }
        }
    }
    mock_post.return_value = MagicMock(status_code=200, json=lambda: ph_payload)
    col = ProductHuntCollector(token="t")
    rec = next(col.fetch(None, "r"))
    assert col.pre_filter(rec)
