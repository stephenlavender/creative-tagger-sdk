"""Creative Tagger API client."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import httpx

ApiResponse = dict[str, Any] | list[Any] | str | None


class CreativeTagger:
    """Client for the Creative Tagger API.

    Usage:
        from creative_tagger import CreativeTagger

        ct = CreativeTagger(api_key="ct_...")

        # Connect a workspace to Meta before pulling performance-backed reports.
        connect = ct.start_meta_connect(brand_name="Brand")
        print(connect["authorization_url"])

        # Analyze a local file.
        result = ct.analyze("./ad_video.mp4", brand="Brand")

        # Analyze a URL.
        result = ct.analyze_url("https://example.com/landing", brand="Brand")

        # Analyze email HTML.
        result = ct.analyze_email("<html>...</html>", brand="Brand")
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.creativetagger.dev",
        timeout: float = 120.0,
        transport: Any | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-API-Key"] = api_key

    def analyze(
        self,
        file_path: str,
        brand: str = "Brand",
        version: int = 1,
        format: str | None = None,
    ) -> "AnalyzeResult":
        """Analyze a local file (image, video, or multiple for carousel).

        Args:
            file_path: Path to the file to analyze.
            brand: Brand name for naming conventions.
            version: Creative version number.
            format: Force format (video, image, carousel, etc.). Auto-detected if omitted.
        """
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = {"brand_name": brand, "version": str(version)}
        if format:
            data["format"] = format

        with open(path, "rb") as f:
            resp = self._request(
                "POST",
                "/analyze",
                files={"file": (path.name, f)},
                data=data,
            )
        return AnalyzeResult(resp.json())

    def analyze_url(
        self,
        url: str,
        brand: str = "Brand",
        version: int = 1,
    ) -> "AnalyzeResult":
        """Analyze a URL (landing page, or direct file URL).

        Landing pages are rendered via headless browser.
        File URLs (ending in .mp4, .jpg, etc.) are downloaded and analyzed.
        """
        is_page = not any(
            url.lower().endswith(ext)
            for ext in (".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp", ".gif")
        )
        data = {"brand_name": brand, "version": str(version)}
        if is_page:
            data["page_url"] = url
        else:
            data["file_url"] = url

        resp = self._request("POST", "/analyze", data=data)
        return AnalyzeResult(resp.json())

    def analyze_email(
        self,
        html: str,
        brand: str = "Brand",
        version: int = 1,
    ) -> "AnalyzeResult":
        """Analyze email HTML content."""
        data = {
            "brand_name": brand,
            "version": str(version),
            "html_content": html,
        }
        resp = self._request("POST", "/analyze", data=data)
        return AnalyzeResult(resp.json())

    def analyze_batch(
        self,
        file_paths: list[str],
        brand: str = "Brand",
    ) -> list["AnalyzeResult"]:
        """Analyze multiple files sequentially."""
        return [self.analyze(fp, brand=brand) for fp in file_paths]

    async def analyze_async(
        self,
        file_path: str,
        brand: str = "Brand",
        version: int = 1,
        format: str | None = None,
    ) -> "AnalyzeResult":
        """Async version of analyze()."""
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = {"brand_name": brand, "version": str(version)}
        if format:
            data["format"] = format

        with open(path, "rb") as f:
            resp = await self._async_request(
                "POST",
                "/analyze",
                files={"file": (path.name, f)},
                data=data,
            )
        return AnalyzeResult(resp.json())

    def health(self) -> bool:
        """Check if the API is reachable."""
        try:
            resp = self._request("GET", "/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_brand_contexts(self) -> ApiResponse:
        """List all saved brand contexts/workspaces for the API key."""
        return self._api_data("GET", "/auth/brand-contexts")

    def get_brand_context(self, brand_name: str) -> ApiResponse:
        """Get the saved brand context for a workspace."""
        return self._api_data(
            "GET",
            "/auth/brand-context",
            params={"brand_name": brand_name},
        )

    def save_brand_context(
        self,
        brand_name: str,
        *,
        voice: str | None = None,
        target_audience: str | None = None,
        top_performers: Sequence[str] | None = None,
        anti_patterns: Sequence[str] | None = None,
        assets: Sequence[Mapping[str, Any]] | None = None,
        notes: str | None = None,
    ) -> ApiResponse:
        """Create or update a brand context/workspace."""
        payload: dict[str, Any] = {"brand_name": brand_name}
        if voice is not None:
            payload["voice"] = voice
        if target_audience is not None:
            payload["target_audience"] = target_audience
        if top_performers is not None:
            payload["top_performers"] = list(top_performers)
        if anti_patterns is not None:
            payload["anti_patterns"] = list(anti_patterns)
        if assets is not None:
            payload["assets"] = [dict(asset) for asset in assets]
        if notes is not None:
            payload["notes"] = notes
        return self._api_data("POST", "/auth/brand-context", json=payload)

    def delete_brand_context(self, brand_name: str) -> ApiResponse:
        """Delete a brand context/workspace."""
        return self._api_data(
            "DELETE",
            "/auth/brand-context",
            params={"brand_name": brand_name},
        )

    def rename_workspace(self, old_name: str, new_name: str) -> ApiResponse:
        """Rename a workspace and move all scoped workspace data."""
        return self._api_data(
            "POST",
            "/auth/workspace/rename",
            json={"old_name": old_name, "new_name": new_name},
        )

    def start_website_ingest(self, url: str, *, brand_name: str = "") -> ApiResponse:
        """Start website ingestion into a brand workspace."""
        return self._api_data(
            "POST",
            "/auth/brand-context/ingest-website",
            json={"url": url, "brand_name": brand_name},
        )

    def get_website_ingest_status(self, job_id: int) -> ApiResponse:
        """Get progress and result summary for a website ingestion job."""
        return self._api_data(
            "GET",
            f"/auth/brand-context/ingest-website/{job_id}",
        )

    def start_meta_connect(
        self,
        *,
        brand_name: str = "",
        scopes: Sequence[str] | None = None,
        bind_session: bool = False,
    ) -> ApiResponse:
        """Start read-only Meta OAuth for a workspace."""
        payload: dict[str, Any] = {
            "brand_name": brand_name,
            "bind_session": bind_session,
        }
        if scopes is not None:
            payload["scopes"] = list(scopes)
        return self._api_data("POST", "/auth/meta/connect/start", json=payload)

    def meta_status(self, *, brand_name: str = "") -> ApiResponse:
        """Get a workspace's Meta connection status."""
        return self._api_data(
            "GET",
            "/auth/meta/status",
            params={"brand_name": brand_name},
        )

    def list_meta_adaccounts(self, *, brand_name: str = "") -> ApiResponse:
        """List ad accounts available through the workspace's Meta connection."""
        return self._api_data(
            "GET",
            "/auth/meta/adaccounts",
            params={"brand_name": brand_name},
        )

    def select_meta_adaccount(
        self,
        account_id: str,
        *,
        brand_name: str = "",
    ) -> ApiResponse:
        """Set the active Meta ad account for a workspace."""
        return self._api_data(
            "POST",
            "/auth/meta/adaccount",
            json={"account_id": account_id, "brand_name": brand_name},
        )

    def sync_meta(
        self,
        *,
        brand_name: str = "",
        account_id: str = "",
        date_preset: str = "last_30d",
        attribution_windows: Sequence[str] | None = None,
    ) -> ApiResponse:
        """Sync read-only Meta performance and demographics into a workspace."""
        payload: dict[str, Any] = {
            "brand_name": brand_name,
            "account_id": account_id,
            "date_preset": date_preset,
        }
        if attribution_windows is not None:
            payload["attribution_windows"] = list(attribution_windows)
        return self._api_data("POST", "/meta/sync", json=payload)

    def disconnect_meta(
        self,
        *,
        brand_name: str = "",
        purge_data: bool = False,
    ) -> ApiResponse:
        """Disconnect a workspace's Meta connection, optionally purging synced data."""
        return self._api_data(
            "DELETE",
            "/auth/meta/connection",
            params={"brand_name": brand_name, "purge_data": purge_data},
        )

    def quote_meta_backfill(
        self,
        *,
        months: int = 12,
        account_id: str = "",
        brand_name: str = "",
    ) -> ApiResponse:
        """Quote the one-time cost to analyze connected Meta ad history."""
        return self._api_data(
            "GET",
            "/meta/backfill/quote",
            params={
                "months": months,
                "account_id": account_id,
                "brand_name": brand_name,
            },
        )

    def checkout_meta_backfill(self, quote_id: int) -> ApiResponse:
        """Create a checkout URL for a paid Meta history backfill quote."""
        return self._api_data(
            "POST",
            "/billing/checkout/backfill",
            data={"quote_id": str(quote_id)},
        )

    def start_meta_backfill(
        self,
        quote_id: int,
        *,
        brand_name: str = "",
    ) -> ApiResponse:
        """Start ingesting a paid Meta history backfill."""
        return self._api_data(
            "POST",
            "/meta/backfill/start",
            json={"quote_id": quote_id, "brand_name": brand_name},
        )

    def get_meta_backfill_status(self, job_id: int) -> ApiResponse:
        """Get progress for a Meta backfill ingestion job."""
        return self._api_data("GET", f"/meta/backfill/jobs/{job_id}")

    def wait_for_meta_backfill(
        self,
        job_id: int,
        *,
        interval_seconds: float = 5.0,
        timeout_seconds: float = 300.0,
    ) -> ApiResponse:
        """Poll a Meta backfill job until it reaches a terminal status."""
        terminal_statuses = {"complete", "completed", "failed", "error", "canceled", "cancelled"}
        deadline = time.monotonic() + timeout_seconds

        while True:
            result = self.get_meta_backfill_status(job_id)
            status = ""
            if isinstance(result, dict):
                status = str(result.get("status", "")).lower()
            if status in terminal_statuses:
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Meta backfill job {job_id} did not finish within {timeout_seconds} seconds")
            time.sleep(interval_seconds)

    def list_library(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str = "",
        format: str = "",
        hook: str = "",
        angle: str = "",
        emotion: str = "",
        cta: str = "",
        talent: str = "",
        offer: str = "",
        audio: str = "",
        season: str = "",
        sort: str = "recent",
        brand_name: str = "",
    ) -> ApiResponse:
        """Browse the analysis library, optionally scoped to a workspace."""
        return self._api_data(
            "GET",
            "/auth/library",
            params={
                "limit": limit,
                "offset": offset,
                "search": search,
                "format": format,
                "hook": hook,
                "angle": angle,
                "emotion": emotion,
                "cta": cta,
                "talent": talent,
                "offer": offer,
                "audio": audio,
                "season": season,
                "sort": sort,
                "brand_name": brand_name,
            },
        )

    def bulk_update_library(self, items: Sequence[Mapping[str, Any]]) -> ApiResponse:
        """Bulk update multiple analyses in the library."""
        return self._api_data(
            "PATCH",
            "/auth/library",
            json=[dict(item) for item in items],
        )

    def library_patterns(self, *, brand_name: str = "") -> ApiResponse:
        """Get pattern insights across a workspace's creative library."""
        return self._api_data(
            "GET",
            "/auth/library/patterns",
            params={"brand_name": brand_name},
        )

    def get_library_item(
        self,
        analysis_id: int,
        *,
        brand_name: str | None = None,
    ) -> ApiResponse:
        """Get the full result for one library analysis."""
        return self._api_data(
            "GET",
            f"/auth/library/{analysis_id}",
            params={"brand_name": brand_name},
        )

    def update_library_item(
        self,
        analysis_id: int,
        updates: Mapping[str, Any],
    ) -> ApiResponse:
        """Update editable fields on a library analysis."""
        return self._api_data(
            "PATCH",
            f"/auth/library/{analysis_id}",
            json=dict(updates),
        )

    def delete_library_item(self, analysis_id: int) -> ApiResponse:
        """Delete one analysis from the library."""
        return self._api_data("DELETE", f"/auth/library/{analysis_id}")

    def get_library_media(
        self,
        analysis_id: int,
        *,
        brand_name: str | None = None,
    ) -> bytes:
        """Download the original analyzed media bytes, when available."""
        resp = self._request(
            "GET",
            f"/auth/library/{analysis_id}/media",
            params={"brand_name": brand_name},
        )
        return resp.content

    def share_library_item(self, analysis_id: int) -> ApiResponse:
        """Generate a public share link for one analysis."""
        return self._api_data("POST", f"/auth/library/{analysis_id}/share")

    def creative_strategy_report(
        self,
        *,
        brand_name: str = "",
        date_preset: str = "",
        rows: str = "",
        columns: str = "",
        metrics: str = "",
        metric_preset: str = "",
        status_focus: str = "",
        report_template: str = "next-tests",
        start_date: str = "",
        end_date: str = "",
        cpa_target: float | None = None,
        roas_target: float | None = None,
        minimum_spend: float | None = None,
        learning_spend: float | None = None,
        fatigue_minimum_calendar_days: int = 0,
        limit: int = 10,
        watch_group_by: str = "",
        watch_metric: str = "",
        watch_signal_focus: str = "all",
        watch_trajectory_focus: str = "all",
        watch_coverage_focus: str = "all",
        watch_minimum_points: int = 2,
        watch_minimum_calendar_days: int | None = None,
        watch_maximum_gap_days: int = 0,
        watch_limit: int = 5,
    ) -> ApiResponse:
        """Get the creative strategy matrix report for a workspace."""
        return self._api_data(
            "GET",
            "/reports/creative-strategy",
            params={
                "brand_name": brand_name,
                "date_preset": date_preset,
                "rows": rows,
                "columns": columns,
                "metrics": metrics,
                "metric_preset": metric_preset,
                "status_focus": status_focus,
                "report_template": report_template,
                "start_date": start_date,
                "end_date": end_date,
                "cpa_target": cpa_target,
                "roas_target": roas_target,
                "minimum_spend": minimum_spend,
                "learning_spend": learning_spend,
                "fatigue_minimum_calendar_days": fatigue_minimum_calendar_days,
                "limit": limit,
                "watch_group_by": watch_group_by,
                "watch_metric": watch_metric,
                "watch_signal_focus": watch_signal_focus,
                "watch_trajectory_focus": watch_trajectory_focus,
                "watch_coverage_focus": watch_coverage_focus,
                "watch_minimum_points": watch_minimum_points,
                "watch_minimum_calendar_days": watch_minimum_calendar_days,
                "watch_maximum_gap_days": watch_maximum_gap_days,
                "watch_limit": watch_limit,
            },
        )

    def weekly_digest_report(
        self,
        *,
        brand_name: str = "",
        week_ending: str = "",
        format: str = "json",
    ) -> ApiResponse:
        """Get the weekly creative performance digest."""
        return self._api_data(
            "GET",
            "/reports/weekly-digest",
            params={
                "brand_name": brand_name,
                "week_ending": week_ending,
                "format": format,
            },
        )

    def performance_by_taxonomy(
        self,
        *,
        brand_name: str = "",
        dimension: str = "",
        spend_threshold: float = 500.0,
        date_preset: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> ApiResponse:
        """Get tag-level performance by taxonomy dimension."""
        return self._api_data(
            "GET",
            "/performance/by-taxonomy",
            params={
                "brand_name": brand_name,
                "dimension": dimension,
                "spend_threshold": spend_threshold,
                "date_preset": date_preset,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def performance_demographics(
        self,
        *,
        brand_name: str = "",
        date_preset: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> ApiResponse:
        """Get age-by-gender performance breakdowns for a workspace."""
        return self._api_data(
            "GET",
            "/performance/demographics",
            params={
                "brand_name": brand_name,
                "date_preset": date_preset,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    def get_hooks(
        self,
        *,
        brand_name: str = "",
        hook_type: str = "",
        sort: str = "spend",
        limit: int = 100,
        format: str = "json",
    ) -> ApiResponse:
        """Get the workspace hook library."""
        return self._api_data(
            "GET",
            "/hooks",
            params={
                "brand_name": brand_name,
                "hook_type": hook_type,
                "sort": sort,
                "limit": limit,
                "format": format,
            },
        )

    def get_lineage(
        self,
        *,
        brand_name: str = "",
        include_suggestions: bool = True,
    ) -> ApiResponse:
        """Get concept-family and iteration lineage for a workspace."""
        return self._api_data(
            "GET",
            "/lineage",
            params={
                "brand_name": brand_name,
                "include_suggestions": include_suggestions,
            },
        )

    def set_lineage_parent(
        self,
        analysis_id: int,
        *,
        parent_analysis_id: int | None = None,
        iteration_type: str = "",
    ) -> ApiResponse:
        """Set or clear an analysis parent link in iteration lineage."""
        return self._api_data(
            "POST",
            "/lineage/parent",
            json={
                "analysis_id": analysis_id,
                "parent_analysis_id": parent_analysis_id,
                "iteration_type": iteration_type,
            },
        )

    def preflight(
        self,
        brand_name: str,
        *,
        file_paths: Sequence[str] | None = None,
        file_urls: Sequence[str] | str | None = None,
        version: int = 1,
        rows: str = "",
        columns: str = "",
    ) -> ApiResponse:
        """Pre-flight check unlaunched draft creatives before spend."""
        file_url_value = ""
        if isinstance(file_urls, str):
            file_url_value = file_urls
        elif file_urls is not None:
            file_url_value = " ".join(file_urls)

        data = {
            "brand_name": brand_name,
            "version": str(version),
            "file_urls": file_url_value,
            "rows": rows,
            "columns": columns,
        }

        paths = [Path(fp).expanduser().resolve() for fp in (file_paths or [])]
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

        handles = []
        try:
            files = []
            for path in paths:
                handle = open(path, "rb")
                handles.append(handle)
                files.append(("files", (path.name, handle)))
            return self._api_data(
                "POST",
                "/preflight",
                data=data,
                files=files or None,
            )
        finally:
            for handle in handles:
                handle.close()

    def generate_creative_brief(
        self,
        analyses: Sequence[Mapping[str, Any]] | str,
        *,
        brand_name: str = "",
        notes: str = "",
    ) -> ApiResponse:
        """Generate legacy creative briefs from previous analysis results."""
        analyses_value = analyses if isinstance(analyses, str) else json.dumps(list(analyses))
        return self._api_data(
            "POST",
            "/brief/generate",
            data={
                "analyses": analyses_value,
                "brand_name": brand_name,
                "notes": notes,
            },
        )

    def generate_brief(
        self,
        *,
        brand_name: str = "",
        brief_type: str = "net_new",
        objective: str = "",
        placement: str = "",
        parent_analysis_id: int | None = None,
        iteration_type: str = "",
    ) -> ApiResponse:
        """Generate and store a schema-v2 creative brief."""
        payload: dict[str, Any] = {
            "brand_name": brand_name,
            "brief_type": brief_type,
            "objective": objective,
            "placement": placement,
            "iteration_type": iteration_type,
        }
        if parent_analysis_id is not None:
            payload["parent_analysis_id"] = parent_analysis_id
        return self._api_data("POST", "/briefs", json=payload)

    def get_brief(self, brief_id: int) -> ApiResponse:
        """Fetch a stored schema-v2 creative brief."""
        return self._api_data("GET", f"/briefs/{brief_id}")

    def diff_brief(self, brief_id: int, analysis_id: int) -> ApiResponse:
        """Compare a delivered analysis against a stored brief."""
        return self._api_data("GET", f"/briefs/{brief_id}/diff/{analysis_id}")

    def render_brief(self, brief_id: int) -> ApiResponse:
        """Render a stored brief as shareable HTML."""
        return self._api_data("GET", f"/briefs/{brief_id}/render")

    def add_voc_quotes(
        self,
        *,
        quotes: Sequence[str] | None = None,
        text: str = "",
        brand_name: str = "",
        source: str = "pasted",
    ) -> ApiResponse:
        """Add verbatim customer-language quotes to the VoC bank."""
        payload: dict[str, Any] = {
            "text": text,
            "brand_name": brand_name,
            "source": source,
        }
        if quotes is not None:
            payload["quotes"] = list(quotes)
        return self._api_data("POST", "/voc/quotes", json=payload)

    def get_voc_bank(
        self,
        *,
        brand_name: str = "",
        angle_type: str = "",
        limit: int = 100,
    ) -> ApiResponse:
        """Get ranked verbatim customer-language quotes and VoC angle types."""
        return self._api_data(
            "GET",
            "/voc/bank",
            params={
                "brand_name": brand_name,
                "angle_type": angle_type,
                "limit": limit,
            },
        )

    def _api_data(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Mapping[str, Any] | None = None,
        files: Any | None = None,
    ) -> ApiResponse:
        resp = self._request(method, path, params=params, json=json, data=data, files=files)
        return self._response_data(resp)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Mapping[str, Any] | None = None,
        files: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        with httpx.Client(timeout=self.timeout if timeout is None else timeout, transport=self._transport) as client:
            resp = client.request(
                method,
                f"{self.base_url}{path}",
                params=self._clean_params(params),
                json=json,
                data=data,
                files=files,
                headers=self._headers,
            )
        self._raise_for_status(resp)
        return resp

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Mapping[str, Any] | None = None,
        files: Any | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            resp = await client.request(
                method,
                f"{self.base_url}{path}",
                params=self._clean_params(params),
                json=json,
                data=data,
                files=files,
                headers=self._headers,
            )
        self._raise_for_status(resp)
        return resp

    @staticmethod
    def _clean_params(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if params is None:
            return None
        return {key: value for key, value in params.items() if value is not None}

    @staticmethod
    def _response_data(resp: httpx.Response) -> ApiResponse:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if 200 <= resp.status_code < 300:
            return

        detail = CreativeTagger._error_detail(resp)
        message = f"{resp.status_code} {resp.reason_phrase}: {detail}"
        raise httpx.HTTPStatusError(message, request=resp.request, response=resp)

    @staticmethod
    def _error_detail(resp: httpx.Response) -> str:
        try:
            payload = resp.json()
        except ValueError:
            return resp.text.strip() or resp.reason_phrase

        if isinstance(payload, dict):
            detail = payload.get("detail", payload.get("message", payload))
        else:
            detail = payload

        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(part) for part in item.get("loc", []))
                    msg = item.get("msg") or item.get("message") or json.dumps(item, sort_keys=True)
                    parts.append(f"{loc}: {msg}" if loc else str(msg))
                else:
                    parts.append(str(item))
            return "; ".join(parts)
        if isinstance(detail, dict):
            return json.dumps(detail, sort_keys=True)
        return str(detail)


class AnalyzeResult:
    """Wrapper around the API response with attribute access.

    Taxonomy v2 splits three dimensions the old model mixed together:
    Media Type (`result.format` — the auto-detected creative format, never
    AI-classified), Asset Type (`result.attributes.asset_type` — production
    class), and Visual Format (`result.attributes.visual_format` — execution
    style; "Static Image" and "Carousel" are media types, no longer valid
    values here). `messaging_angle` is the canonical angle key.

    Access any field as an attribute:
        result.format                     -> "video"
        result.attributes.asset_type      -> "UGC"
        result.attributes.visual_format   -> "Talking Head"
        result.attributes.hook_type       -> "Curiosity Gap"
        result.attributes.messaging_angle -> "Pain Point"
        result.naming.standard            -> "BRAND_UGC_TalkingHead_..."
    """

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = self._data.get(name)
        if isinstance(value, dict):
            return AnalyzeResult(value)
        return value

    def __repr__(self):
        fmt = self._data.get("format", "?")
        hook = (self._data.get("attributes") or {}).get("hook_type", "?")
        naming = (self._data.get("naming") or {}).get("standard", "?")
        return f"<AnalyzeResult format={fmt} hook={hook} naming={naming}>"

    def to_dict(self) -> dict:
        """Return the raw API response as a dict."""
        return self._data

    def to_row(self) -> dict:
        """Flatten to a single-level dict suitable for CSV/DataFrame.

        Column names follow the taxonomy v2 canonical dimension keys:
        `media_type` (the auto-detected top-level `format`, duplicated under
        both keys), `asset_type` (production class, previously exported as
        `production_type`), `visual_format` (execution style, previously
        exported as `creative_type`), and `messaging_angle`.
        """
        a = self._data.get("attributes") or {}
        n = self._data.get("naming") or {}
        return {
            "format": self._data.get("format"),
            "media_type": self._data.get("format"),
            "asset_type": a.get("asset_type"),
            "visual_format": a.get("visual_format"),
            "visual_style": a.get("visual_style"),
            "talent": a.get("talent"),
            "talent_age_group": a.get("talent_age_group"),
            "talent_gender": a.get("talent_gender"),
            "audience": a.get("audience"),
            "messaging_angle": a.get("messaging_angle"),
            "seasonality": a.get("seasonality"),
            "offer_type": a.get("offer_type"),
            "hook_type": a.get("hook_type"),
            "hook_text": a.get("hook_text"),
            "cta": a.get("cta"),
            "audio_type": a.get("audio_type"),
            "voiceover_tone": a.get("voiceover_tone"),
            "emotion": a.get("emotion"),
            "aspect_ratio": a.get("aspect_ratio"),
            "duration": a.get("duration"),
            "duration_seconds": a.get("duration_seconds"),
            "analysis_id": self._data.get("analysis_id"),
            "naming_standard": n.get("standard"),
            "naming_compact": n.get("compact"),
            "model_used": self._data.get("model_used"),
            "processing_time_ms": self._data.get("processing_time_ms"),
        }
