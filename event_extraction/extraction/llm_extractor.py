import json
import os
from typing import Optional

from event_extraction.models import ExecutionEvent


EXTRACTION_PROMPT = """You are an EPC (Engineering, Procurement, Construction) project event extractor for Oil India Limited.

Given a field report text, extract structured execution events. Each event represents one thing that happened or is happening on site.

For EACH event, extract these fields (use null if not stated or uncertain):
- description: normalized description of what happened
- discipline: one of [piping, electrical, civil, instrumentation, mechanical] or null
- activity_type: one of [erection, welding, installation, testing, commissioning, excavation, concreting, backfilling, insulation, hydrotest, cable_pulling, termination, alignment, fabrication, inspection, loop_check, calibration, painting, curing, glanding, equipment_setting, piping_connection] or null
- asset: the specific equipment/line identifier (e.g. "Line 24", "V-301", "P-101") or null
- location: site location (e.g. "Unit 4", "Area B", "Substation") or null
- status: one of [started, in_progress, completed, not_started, delayed, blocked]
- event_date: ISO date if mentioned or inferable, else null
- quantity: numeric quantity if mentioned, else null
- unit: unit of quantity (e.g. "metres", "spools", "joints", "%") or null

CRITICAL RULES:
1. NEVER invent information not present in the text
2. Use null for any field you cannot confidently extract
3. Do NOT match to schedule activity IDs — only extract what the text says
4. Distinguish started vs completed vs in_progress carefully
5. If text says "could not be done" or "faulty" or "pending material", status is "blocked" or "not_started"
6. Extract ALL events if the text describes multiple activities

Return ONLY valid JSON array of event objects. No explanation."""


class LLMExtractor:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set — LLM extraction unavailable")
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    @property
    def available(self) -> bool:
        return bool(self._api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def extract(self, text: str, reference_date: Optional[str] = None) -> list[dict]:
        client = self._get_client()

        user_message = f"Report text:\n{text}"
        if reference_date:
            user_message += f"\n\nReport date: {reference_date}"

        response = client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_response = response.content[0].text.strip()

        if raw_response.startswith("```"):
            lines = raw_response.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_response = "\n".join(lines)

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, dict):
            parsed = [parsed]

        return parsed if isinstance(parsed, list) else []

    def extract_single(self, event: ExecutionEvent) -> ExecutionEvent:
        if not self.available:
            return event

        try:
            results = self.extract(event.raw_text, event.event_date)
        except Exception:
            return event

        if not results:
            return event

        extracted = results[0]

        if not event.discipline and extracted.get("discipline"):
            event.discipline = extracted["discipline"]
        if not event.activity_type and extracted.get("activity_type"):
            event.activity_type = extracted["activity_type"]
        if not event.asset and extracted.get("asset"):
            event.asset = extracted["asset"]
        if not event.location and extracted.get("location"):
            event.location = extracted["location"]
        if event.status == "unknown" and extracted.get("status"):
            event.status = extracted["status"]
        if not event.event_date and extracted.get("event_date"):
            event.event_date = extracted["event_date"]
        if event.quantity is None and extracted.get("quantity") is not None:
            try:
                event.quantity = float(extracted["quantity"])
            except (ValueError, TypeError):
                pass
        if not event.unit and extracted.get("unit"):
            event.unit = extracted["unit"]
        if extracted.get("description"):
            event.description = extracted["description"]

        return event
