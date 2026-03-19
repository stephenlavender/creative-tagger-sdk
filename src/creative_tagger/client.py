"""Creative Tagger API client."""

from pathlib import Path

import httpx


class CreativeTagger:
    """Client for the Creative Tagger API.

    Usage:
        from creative_tagger import CreativeTagger

        ct = CreativeTagger(api_key="ct_...")

        # Analyze a local file
        result = ct.analyze("./ad_video.mp4", brand="Brand")

        # Analyze a URL
        result = ct.analyze_url("https://example.com/landing", brand="Brand")

        # Analyze email HTML
        result = ct.analyze_email("<html>...</html>", brand="Brand")

        # Access results
        print(result.naming.default)
        print(result.visual.hook_type)
        print(result.messaging_angle)
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.creativetagger.dev",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {}
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

        with httpx.Client(timeout=self.timeout) as client:
            data = {"brand_name": brand, "version": str(version)}
            if format:
                data["format"] = format

            with open(path, "rb") as f:
                resp = client.post(
                    f"{self.base_url}/analyze",
                    files={"file": (path.name, f)},
                    data=data,
                    headers=self._headers,
                )
            resp.raise_for_status()
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

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/analyze",
                data=data,
                headers=self._headers,
            )
            resp.raise_for_status()
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
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/analyze",
                data=data,
                headers=self._headers,
            )
            resp.raise_for_status()
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = {"brand_name": brand, "version": str(version)}
            if format:
                data["format"] = format

            with open(path, "rb") as f:
                resp = await client.post(
                    f"{self.base_url}/analyze",
                    files={"file": (path.name, f)},
                    data=data,
                    headers=self._headers,
                )
            resp.raise_for_status()
            return AnalyzeResult(resp.json())

    def health(self) -> bool:
        """Check if the API is reachable."""
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


class AnalyzeResult:
    """Wrapper around the API response with attribute access.

    Access any field as an attribute:
        result.format           → "video"
        result.visual.hook_type → "UGC"
        result.naming.default   → "NEMAH_UGC_Creator_LoFi_..."
        result.messaging_angle  → "ProbSol"
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
        hook = self._data.get("visual", {}).get("hook_type", "?")
        naming = self._data.get("naming", {}).get("default", "?")
        return f"<AnalyzeResult format={fmt} hook={hook} naming={naming}>"

    def to_dict(self) -> dict:
        """Return the raw API response as a dict."""
        return self._data

    def to_row(self) -> dict:
        """Flatten to a single-level dict suitable for CSV/DataFrame."""
        v = self._data.get("visual", {})
        n = self._data.get("naming", {})
        a = self._data.get("audio") or {}
        return {
            "format": self._data.get("format"),
            "hook_type": v.get("hook_type"),
            "hook_style": self._data.get("hook_style"),
            "visual_style": v.get("visual_style"),
            "talent_type": v.get("talent_type"),
            "cta_type": v.get("cta_type"),
            "cta_placement": self._data.get("cta_placement"),
            "primary_emotion": v.get("primary_emotion"),
            "messaging_angle": self._data.get("messaging_angle"),
            "creative_type": self._data.get("creative_type"),
            "production_type": self._data.get("production_type"),
            "product_presence": self._data.get("product_presence"),
            "offer_type": self._data.get("offer_type"),
            "offer_detail": self._data.get("offer_detail"),
            "brand_presence": self._data.get("brand_presence"),
            "seasonality": self._data.get("seasonality"),
            "text_overlay_treatment": self._data.get("text_overlay_treatment"),
            "social_proof_elements": self._data.get("social_proof_elements"),
            "aspect_ratio": v.get("aspect_ratio"),
            "duration_seconds": v.get("duration_seconds"),
            "video_length_bucket": self._data.get("video_length_bucket"),
            "audio_type": a.get("audio_type"),
            "audio_shortcode": self._data.get("audio_shortcode"),
            "naming_default": n.get("default"),
            "naming_compact": n.get("compact"),
            "model_used": self._data.get("model_used"),
            "processing_time_ms": self._data.get("processing_time_ms"),
        }
