from __future__ import annotations

from .apify_base import ApifyActorCollector
from .appfollow import AppFollowCollector
from .capterra import CapterraCollector
from .g2 import G2Collector
from .indeed import IndeedCollector
from .producthunt import ProductHuntCollector
from .upwork import UpworkCollector

__all__ = [
    "ApifyActorCollector",
    "G2Collector",
    "CapterraCollector",
    "UpworkCollector",
    "IndeedCollector",
    "AppFollowCollector",
    "ProductHuntCollector",
]
