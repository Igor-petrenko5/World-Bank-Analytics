import json
import hashlib

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class WorldBankAPI:

    BASE_URL = "https://api.worldbank.org/v2"

    def __init__(self):
        self.session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True
        )

        adapter = HTTPAdapter(max_retries=retry)

        self.session.mount("https://", adapter)

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "WorldBankAnalytics/1.0"
        })

    def get_page(self, endpoint, params=None):

        query = dict(params or {})
        query["format"] = "json"

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        logger.info("Request: %s | %s", url, query)

        response = self.session.get(
            url,
            params=query,
            timeout=(10, 90)
        )

        response.raise_for_status()

        payload = response.json()
        raw_dir = Path("data/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)

        request_hash = hashlib.sha256(
            response.url.encode("utf-8")
        ).hexdigest()[:16]

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S")

        raw_file = raw_dir / (
            f"{timestamp}_{request_hash}_{uuid4().hex}.json"
        )

        with raw_file.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "url": response.url,
                    "collected_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "payload": payload
                },
                file,
                ensure_ascii=False,
                indent=2
            )
        if (
            not isinstance(payload, list)
            or len(payload) != 2
            or not isinstance(payload[0], dict)
            or not isinstance(payload[1], list)
        ):
            raise ValueError(
                f"Unexpected API response: {str(payload)[:300]}"
            )

        metadata, records = payload

        required = {"page", "pages", "total"}

        if not required.issubset(metadata):
            raise ValueError("Missing pagination metadata")

        return metadata, records

    def get_all(self, endpoint, params=None):

        query = dict(params or {})
        query["per_page"] = 1000

        records = []
        page = 1
        first_metadata = None

        while True:

            query["page"] = page

            metadata, page_records = self.get_page(
                endpoint, query
            )

            if int(metadata["page"]) != page:
                raise ValueError("Unexpected page number")

            if first_metadata is None:
                first_metadata = metadata.copy()

            for key in ["pages", "total", "lastupdated"]:
                if metadata.get(key) != first_metadata.get(key):
                    raise ValueError(
                        f"Metadata changed during collection: {key}"
                    )

            records.extend(page_records)

            logger.info(
                "Page %s/%s | Records: %s",
                page,
                metadata["pages"],
                len(page_records)
            )

            if page >= int(metadata["pages"]):
                break

            page += 1

        if len(records) != int(first_metadata["total"]):
            raise ValueError(
                "Collected record count does not match API total"
            )

        return first_metadata, records
