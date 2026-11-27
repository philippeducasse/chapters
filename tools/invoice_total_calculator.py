"""
title: Invoice Total Calculator
author: CHAPTERS AI Core Team
description: Deterministically sums the "Gesamtbetrag" (grand total) of every invoice and credit note for a given supplier in the Supplier Invoices knowledge base, instead of relying on the model's own arithmetic over retrieved text. Also includes the default example tools (user info, time, calculator, weather).
version: 0.2.0
"""

import asyncio
import os
import re
from datetime import date, datetime

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        KNOWLEDGE_ID: str = Field(
            default="dcbbe521-d9fc-493e-bbb4-0ebdc6acfc6b",
            description="ID of the 'Supplier Invoices' knowledge collection to search.",
        )
        TOP_K: int = Field(
            default=50,
            description="Max chunks to retrieve. Set high enough to cover the whole knowledge base.",
        )

    def __init__(self):
        self.valves = self.Valves()

    # Add your custom tools using pure Python code here, make sure to add type hints and descriptions

    def get_user_name_and_email_and_id(self, __user__: dict = {}) -> str:
        """
        Get the user name, Email and ID from the user object.
        """

        # Do not include a descrption for __user__ as it should not be shown in the tool's specification
        # The session user object will be passed as a parameter when the function is called

        print(__user__)
        result = ""

        if "name" in __user__:
            result += f"User: {__user__['name']}"
        if "id" in __user__:
            result += f" (ID: {__user__['id']})"
        if "email" in __user__:
            result += f" (Email: {__user__['email']})"

        if result == "":
            result = "User: Unknown"

        return result

    def get_current_time(self) -> str:
        """
        Get the current time in a more human-readable format.
        """

        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        )  # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"

    def calculator(
        self,
        equation: str = Field(
            ..., description="The mathematical equation to calculate."
        ),
    ) -> str:
        """
        Calculate the result of an equation.
        """

        # Avoid using eval in production code
        # https://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html
        try:
            result = eval(equation)
            return f"{equation} = {result}"
        except Exception as e:
            print(e)
            return "Invalid equation"

    def get_current_weather(
        self,
        city: str = Field(
            "New York, NY", description="Get the current weather for a given city."
        ),
    ) -> str:
        """
        Get the current weather for a given city.
        """

        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            return (
                "API key is not set in the environment variable 'OPENWEATHER_API_KEY'."
            )

        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",  # Optional: Use 'imperial' for Fahrenheit
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
            data = response.json()

            if data.get("cod") != 200:
                return f"Error fetching weather data: {data.get('message')}"

            weather_description = data["weather"][0]["description"]
            temperature = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return f"Weather in {city}: {temperature}°C"
        except requests.RequestException as e:
            return f"Error fetching weather data: {str(e)}"

    async def calculate_supplier_total(
        self,
        supplier_name: str,
        date_from: str = "",
        date_to: str = "",
        __request__=None,
    ) -> str:
        """
        Calculate the exact total amount paid to a given supplier by summing the
        'Gesamtbetrag' (grand total) line of every invoice and credit note for
        that supplier found in the knowledge base. Credit notes are stored with
        a negative Gesamtbetrag, so they are automatically subtracted correctly.
        Always call this tool instead of adding the amounts yourself: manual
        arithmetic over several retrieved documents is unreliable. To total a
        specific period (e.g. a quarter), pass date_from/date_to instead of
        filtering or re-summing the result yourself.

        :param supplier_name: The supplier's name exactly as written on the invoices, e.g. "Nordlicht Facility Services GmbH".
        :param date_from: Optional inclusive start date (YYYY-MM-DD). Omit to include all documents from the beginning.
        :param date_to: Optional inclusive end date (YYYY-MM-DD). Omit to include all documents up to the latest.
        :return: A line-by-line breakdown of every matching document and the resulting total.
        """
        if __request__ is None:
            return "Error: no request context available to query the knowledge base."

        from open_webui.retrieval.utils import query_doc

        embedding_function = __request__.app.state.EMBEDDING_FUNCTION
        query_embedding = await embedding_function(supplier_name, prefix=None, user=None)

        result = await asyncio.to_thread(
            query_doc,
            collection_name=self.valves.KNOWLEDGE_ID,
            query_embedding=query_embedding,
            k=self.valves.TOP_K,
            user=None,
        )

        if not result or not result.documents:
            return f"No documents found in the knowledge base for '{supplier_name}'."

        documents = result.documents[0]
        metadatas = result.metadatas[0]

        # The plain-text extractor puts the label and the amount on separate
        # lines, one value per line, e.g. "Gesamtbetrag\n2.701,30 €". Mistral
        # OCR instead renders the same row as a markdown table with bold
        # markers and empty cells in between, e.g. "|  **Gesamtbetrag** |
        # |   |   | **3.058,30 €**  |". Neither format puts the amount
        # immediately adjacent to the label, and the gap differs between
        # them, so just take the first amount-shaped value within a short
        # window after "Gesamtbetrag" rather than anchoring on a fixed gap.
        amount_in_line_re = re.compile(r"(-?[\d.]+,\d{2})\s*€")
        number_re = re.compile(r"Nummer:\s*([A-Za-z0-9\-]+)")
        date_re = re.compile(r"Datum:\s*(\d{2})\.(\d{2})\.(\d{4})")

        def find_amount(text: str):
            idx = text.find("Gesamtbetrag")
            if idx == -1:
                return None
            window = text[idx : idx + 120]
            m = amount_in_line_re.search(window)
            return m.group(1) if m else None

        def parse_bound(value: str, label: str):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid {label} '{value}': expected YYYY-MM-DD.")

        try:
            range_start = parse_bound(date_from, "date_from")
            range_end = parse_bound(date_to, "date_to")
        except ValueError as e:
            return f"Error: {e}"

        # Group retrieved chunks by source file before filtering. A single
        # invoice can be split across multiple chunks (e.g. Mistral OCR's
        # markdown output splits on headers: the company letterhead lands in
        # one chunk, the Nummer/Gesamtbetrag table in another) — filtering
        # chunk-by-chunk would silently drop any document whose name and
        # amount don't happen to share one chunk.
        by_file: dict[str, list[str]] = {}
        for doc, meta in zip(documents, metadatas):
            file_key = (meta or {}).get("name") or (meta or {}).get("file_id") or doc[:40]
            by_file.setdefault(file_key, []).append(doc)

        found = {}
        skipped_unparsed_date = []
        for file_key, chunks in by_file.items():
            combined = "\n".join(chunks)
            if supplier_name.lower() not in combined.lower():
                continue
            amount_str = find_amount(combined)
            if amount_str is None:
                continue
            number_match = number_re.search(combined)
            doc_id = number_match.group(1) if number_match else file_key

            if range_start or range_end:
                date_match = date_re.search(combined)
                if not date_match:
                    skipped_unparsed_date.append(doc_id)
                    continue
                day, month, year = map(int, date_match.groups())
                doc_date = date(year, month, day)
                if range_start and doc_date < range_start:
                    continue
                if range_end and doc_date > range_end:
                    continue

            amount = float(amount_str.replace(".", "").replace(",", "."))
            found[doc_id] = amount

        if not found:
            period = (
                f" between {date_from or 'the start'} and {date_to or 'now'}"
                if (range_start or range_end)
                else ""
            )
            return (
                f"No invoices or credit notes for '{supplier_name}'{period} were found with a "
                f"readable Gesamtbetrag. If this supplier should have invoices, check whether any "
                f"of its files failed text/OCR extraction in the knowledge base."
            )

        def fmt_eur(value: float) -> str:
            return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

        lines = [f"- {doc_id}: {fmt_eur(amt)}" for doc_id, amt in sorted(found.items())]
        total = sum(found.values())

        caveat = ""
        if skipped_unparsed_date:
            caveat = (
                f"\n\nNote: {len(skipped_unparsed_date)} document(s) for this supplier "
                f"({', '.join(sorted(skipped_unparsed_date))}) had no readable Datum and were "
                f"excluded from this date-filtered total — check them manually."
            )

        return (
            f"Documents found for '{supplier_name}' ({len(found)}):\n"
            + "\n".join(lines)
            + f"\n\nTotal: {fmt_eur(total)}"
            + caveat
        )
