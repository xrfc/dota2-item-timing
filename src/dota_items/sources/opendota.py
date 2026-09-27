"""Read-only OpenDota access with raw caching and bounded retries."""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def fetch_match(
    match_id: int,
    cache_dir: Path,
    *,
    refresh: bool = False,
    client: httpx.Client | None = None,
) -> Path:
    if match_id <= 0:
        raise ValueError("match_id must be positive")
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{match_id}.json"
    if destination.exists() and not refresh:
        return destination
    own_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    key = os.environ.get("OPENDOTA_API_KEY")
    params = {"api_key": key} if key else {}
    try:
        for attempt in range(3):
            response = client.get(f"https://api.opendota.com/api/matches/{match_id}", params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise ValueError(
                        f"OpenDota temporarily unavailable (HTTP {response.status_code})"
                    )
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = max(float(retry_after), 0)
                except ValueError:
                    delay = float(2 ** (attempt + 1))
                if delay > 30:
                    raise ValueError("OpenDota requested a longer wait; retry this command later")
                time.sleep(delay)
                continue
            if response.status_code != 200:
                raise ValueError(f"OpenDota request failed (HTTP {response.status_code})")
            raw = response.json()
            if not isinstance(raw, dict) or raw.get("match_id") != match_id:
                raise ValueError("OpenDota returned an unexpected match payload")
            contents = response.content
            temporary = destination.with_suffix(".json.tmp")
            temporary.write_bytes(contents)
            temporary.replace(destination)
            manifest = {
                "match_id": match_id,
                "source": "opendota",
                "fetched_at": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(contents).hexdigest(),
            }
            destination.with_suffix(".manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            return destination
    except httpx.HTTPError as error:
        # Do not include a URL/query string: it may contain an API key.
        raise ValueError("OpenDota network request failed; check connectivity and retry") from error
    finally:
        if own_client:
            client.close()
    raise ValueError("No match response received")
