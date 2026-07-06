# Creative Tagger Python SDK

Python client for [Creative Tagger](https://github.com/stephenlavender/creative-tagger) — structured creative intelligence API for performance marketing.

Analyze any ad creative (video, image, carousel, landing page, email) and get back structured classification across 28 taxonomy dimensions.

## Install

```bash
pip install creative-tagger
```

## Quick Start

```python
from creative_tagger import CreativeTagger

ct = CreativeTagger(api_key="ct_...")

# Analyze a video ad
result = ct.analyze("./ad_video.mp4", brand="Brand")
print(result.naming.default)
# → Brand_UGC_Question_Pain Point_Shop Now_9x16_30s

print(result.attributes.hook_type)        # → Question
print(result.attributes.messaging_angle)  # → Pain Point
print(result.creative_type)       # → Testimonial
print(result.attributes.visual_style)    # → Lo-Fi
print(result.offer_type)          # → PctOff

# Analyze a landing page
result = ct.analyze_url("https://example.com/lp", brand="BrandX")
print(result.visual_hierarchy)    # → HeroFocus

# Analyze email HTML
result = ct.analyze_email(html_string, brand="BrandX")
print(result.email_structure)     # → SingleCTA
```

## Batch Analysis

```python
results = ct.analyze_batch(["ad1.mp4", "ad2.jpg", "ad3.png"], brand="Brand")

# Export to CSV-ready rows
import csv
rows = [r.to_row() for r in results]
```

## Async Support

```python
result = await ct.analyze_async("./ad.mp4", brand="Brand")
```

## Local Development

Point to a local Creative Tagger API:

```python
ct = CreativeTagger(base_url="http://localhost:8000")
```

## License

MIT
