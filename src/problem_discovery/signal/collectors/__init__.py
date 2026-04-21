from __future__ import annotations

from .arxiv import ArxivCollector
from .cms import CMSNewsCollector
from .fda import FDANewsCollector
from .federal_register import FederalRegisterCollector
from .github import GitHubIssuesCollector
from .google_ads_transparency import GoogleAdsTransparencyCollector
from .google_trends import GoogleTrendsCollector
from .hackernews import HackerNewsCollector
from .meta_ad_library import MetaAdLibraryCollector
from .nih_reporter import NIHReporterCollector
from .polymarket import PolymarketCollector
from .protocol import Collector, HealthStatus, RawRecord
from .reddit import RedditCollector
from .sec_edgar import SECEdgarNewsCollector
from .sec_filings import SECFilingsCollector
from .stackoverflow import StackOverflowCollector
from .tier2 import (
    AhrefsKeywordCollector,
    ListenNotesCollector,
    ProfoundCollector,
    SemrushDomainCollector,
    SimilarwebCollector,
    SparkToroCollector,
)
from .tier3 import (
    AppFollowCollector,
    ApifyActorCollector,
    CapterraCollector,
    G2Collector,
    IndeedCollector,
    ProductHuntCollector,
    UpworkCollector,
)
from .youtube import YouTubeDataCollector
from .youtube_comments import YouTubeCommentsCollector

__all__ = [
    "Collector",
    "HealthStatus",
    "RawRecord",
    "RedditCollector",
    "HackerNewsCollector",
    "FederalRegisterCollector",
    "GitHubIssuesCollector",
    "SECEdgarNewsCollector",
    "CMSNewsCollector",
    "ArxivCollector",
    "FDANewsCollector",
    "StackOverflowCollector",
    "YouTubeDataCollector",
    "YouTubeCommentsCollector",
    "SECFilingsCollector",
    "MetaAdLibraryCollector",
    "GoogleAdsTransparencyCollector",
    "NIHReporterCollector",
    "PolymarketCollector",
    "GoogleTrendsCollector",
    "AhrefsKeywordCollector",
    "SemrushDomainCollector",
    "SimilarwebCollector",
    "SparkToroCollector",
    "ListenNotesCollector",
    "ProfoundCollector",
    "ApifyActorCollector",
    "G2Collector",
    "CapterraCollector",
    "UpworkCollector",
    "IndeedCollector",
    "AppFollowCollector",
    "ProductHuntCollector",
]
