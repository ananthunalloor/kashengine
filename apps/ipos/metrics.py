"""Refresh the numbers of the IPOs: GMP, subscription, listing result, status, and score."""

import logging

from apps.siteconfig import conf

from .collect import refresh_statuses
from .gmp import GmpSourceError, update_gmp
from .listing import fill_listing_results
from .scoring import score_ipos

logger = logging.getLogger(__name__)


def refresh_metrics(force: bool = False) -> dict:
    """Run all the steps. A step that fails does not stop the others.

    force: run the GMP step and the listing step also when their settings are off.
    """
    result: dict = {}

    if conf.IPO_GMP_ENABLED or force:
        try:
            result["gmp"] = update_gmp().as_dict()
        except GmpSourceError as exc:
            logger.warning("GMP source failed: %s", exc)
            result["gmp"] = {"error": str(exc)}
    else:
        result["gmp"] = "disabled"

    if conf.IPO_LISTING_ENABLED or force:
        try:
            result["listing"] = fill_listing_results()
        except Exception:  # A broken data library must not stop the scores.
            logger.exception("The listing step failed.")
            result["listing"] = {"error": "see the log"}
    else:
        result["listing"] = "disabled"

    result["status_changed"] = refresh_statuses()
    result["scores"] = score_ipos()
    return result
