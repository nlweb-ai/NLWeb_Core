# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the code for the ranking stage.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from nlweb_core.utils import trim_json, fill_prompt_variables
from nlweb_core.llm import ask_llm
import asyncio
import json


def log(message):
    """Simple logging function."""
    print(message)


# Schema.org markup trimming utilities
# The schema.org markup on many pages includes a lot of information that is not useful
# for indexing or ranking. Further, many pages are just collections that we don't
# want to index at all. We can also skip things like Breadcrumbs

skip_types = ["ListItem", "ItemList", "Organization", "BreadcrumbList", "Breadcrumb", "WebSite",
              "SearchAction", "SiteNavigationElement", "WebPageElement", "WebPage", "NewsMediaOrganization",
              "MerchantReturnPolicy", "ReturnPolicy", "CollectionPage", "Brand", "Corporation",
              "SiteNavigationElement", "ReadAction"]

skip_properties = ["publisher", "mainEntityOfPage"]

# Ugly hack
leaf_types = ["Recipe", "Product"]


def should_skip_item(site, item):
    """Determine if an item should be skipped based on its type."""
    if item is None:
        return True
    if "@type" in item and item["@type"] in skip_types:
        return True
    # Check if @type is a list and if any value in the list is in skip_types
    elif "@type" in item and isinstance(item["@type"], list):
        for type_value in item["@type"]:
            if type_value in skip_types:
                return True
    elif "@type" not in item:
        print(f"Warning: Item without @type field found for site {site}, keeping item: {str(item)[:100]}...")
        return False
    return False


def trim_schema_json_graph(schema_json, site):
    """Trim a @graph structure in schema.org JSON."""
    trimmed_items = []
    pruned = []
    for item in schema_json:
        if (not should_skip_item(site, item) and "@type" in item):
            item_type = item["@type"]
            if (item_type in leaf_types):
                ss = trim_schema_json_item(item, site)
                return [trim_schema_json_item(item, site)]
    for item in schema_json:
        trimmed_item = trim_schema_json_item(item, site)
        if trimmed_item is not None:
            trimmed_items.append(trimmed_item)
    return trimmed_items or None


def trim_schema_json_item(schema_json, site):
    """
    Trim the markup without losing too much of the information that the LLM can use.
    Go through each property in the schema_json and apply the following rules to construct
    a new json object with only the properties that are useful for indexing and ranking:

    1. If the property is in skip_properties, remove it from the schema_json.
    2. If the property is image and the value is a list of urls, pick the first value
    3. If the property is image and the value is an ImageObject, pick the url of the image
    4. If the value is a json object of type Person, pick the name
    5. If the value is aggregateRating, pick the ratingValue
    6. If the property is review and the value is a list, go through each item in the list
       and pick the reviewBody of up to 3 reviews, with the longest reviews
    """
    if schema_json is None:
        return None
    elif (isinstance(schema_json, dict) and "@graph" in schema_json):
        trimmed_items = trim_schema_json_graph(schema_json["@graph"], site)
        if (len(trimmed_items) > 0):
            return trimmed_items
        else:
            return None
    elif isinstance(schema_json, list):
        trimmed_items = []
        for item in schema_json:
            elt = trim_schema_json_item(item, site)
            if (elt):
                trimmed_items.append(elt)
        if (len(trimmed_items) > 0):
            return trimmed_items
        else:
            return None
    elif isinstance(schema_json, dict):
        if (should_skip_item(site, schema_json)):
            return None
        else:
            retval = {}
            # Rule 1: Skip properties in skip_properties
            for k, v in schema_json.items():
                if k in skip_properties:
                    continue

                # Rule 2: If property is image and value is a list of URLs, pick the first value
                if k == "image" and isinstance(v, list) and len(v) > 0:
                    if all(isinstance(img, str) for img in v):
                        retval[k] = v[0]
                        continue

                # Rule 3: If property is image and value is an ImageObject, pick the URL
                if k == "image" and isinstance(v, dict) and v.get("@type") == "ImageObject" and "url" in v:
                    retval[k] = v["url"]
                    continue

                # Rule 4: If value is a Person object, pick the name
                if isinstance(v, dict) and v.get("@type") == "Person" and "name" in v:
                    retval[k] = v["name"]
                    continue

                # Rule 5: If value is aggregateRating, pick the ratingValue
                if k == "aggregateRating" and isinstance(v, dict) and "ratingValue" in v:
                    retval[k] = v["ratingValue"]
                    continue

                # Rule 6: If property is review and value is a list, pick up to 3 longest reviewBodies
                if k == "review" and isinstance(v, list):
                    reviews = []
                    review_bodies = [(r.get("reviewBody", ""), r) for r in v if isinstance(r, dict) and "reviewBody" in r]
                    # Sort by length of reviewBody in descending order
                    review_bodies.sort(key=lambda x: len(x[0]), reverse=True)
                    # Take up to 3 longest reviews
                    for _, review in review_bodies[:3]:
                        reviews.append(review)
                    if reviews:
                        retval[k] = reviews
                        continue

                # Default: keep the property as is
                retval[k] = v

            # Return early since we've already processed all items
            return retval


class Ranking:
     
    EARLY_SEND_THRESHOLD = 59
    NUM_RESULTS_TO_SEND = 10

    # This is the default ranking prompt, in case, for some reason, we can't find the site_type.xml file.
    RANKING_PROMPT = ["""  Assign a score between 0 and 100 to the following {site.itemType}
based on how relevant it is to the user's question. Use your knowledge from other sources, about the item, to make a judgement.
If the score is above 50, provide a short description of the item highlighting the relevance to the user's question, without mentioning the user's question.
Provide an explanation of the relevance of the item to the user's question, without mentioning the user's question or the score or explicitly mentioning the term relevance.
If the score is below 75, in the description, include the reason why it is still relevant.
The user's question is: {request.query}. The item's description is {item.description}""",
    {"score" : "integer between 0 and 100",
 "description" : "short description of the item"}]
 
    RANKING_PROMPT_NAME = "RankingPrompt"
     
    def get_ranking_prompt(self):
        # Use default ranking prompt
        return self.RANKING_PROMPT[0], self.RANKING_PROMPT[1]
        
    def __init__(self, handler, items, level="low"):
        ll = len(items)
        print(f"\n[RANKING] Initializing with {ll} items")
        self.handler = handler
        self.level = level
        self.items = items
        self.num_results_sent = 0
        self.rankedAnswers = []

    async def rankItem(self, url, json_str, name, site):
        try:
            prompt_str, ans_struc = self.get_ranking_prompt()
            description = trim_json(json_str)
            prompt = fill_prompt_variables(prompt_str, self.handler.query_params, {"item.description": description})
            ranking = await ask_llm(prompt, ans_struc, level=self.level, query_params=self.handler.query_params)

            print(f"[RANKING] LLM response for {name}: {ranking}")
            print(f"[RANKING] Item: {name}, Score: {ranking.get('score', 'N/A')}")

            # Handle both string and dictionary inputs for json_str
            schema_object = json_str if isinstance(json_str, dict) else json.loads(json_str)

            # If schema_object is an array, set it to the first item
            if isinstance(schema_object, list) and len(schema_object) > 0:
                schema_object = schema_object[0]

            # Create the final result structure
            # Start with basic fields
            result = {
                "@type": schema_object.get("@type", "Item"),
                "url": url,
                "name": name,
                "site": site,
                "score": ranking["score"],
                "description": ranking["description"],
                "sent": False
            }

            # Add all attributes from schema_object except url
            for key, value in schema_object.items():
                if key != "url":
                    result[key] = value

            # Add grounding with the url or @id from schema_object
            grounding_url = schema_object.get("url") or schema_object.get("@id")
            if grounding_url:
                result["grounding"] = grounding_url

            # Add to ranked answers
            self.rankedAnswers.append(result)

            # Send immediately if score is high enough
            if (result["score"] > self.EARLY_SEND_THRESHOLD):
                try:
                    if not self.handler.connection_alive_event.is_set():
                        return

                    # Wait for pre checks to be done
                    await self.handler.pre_checks_done_event.wait()

                    # Get max_results from handler
                    max_results = self.handler.get_param('max_results', int, self.NUM_RESULTS_TO_SEND)

                    # Check if we can still send more results
                    if self.num_results_sent < max_results:
                        # Create a copy without the 'sent' field for sending
                        result_to_send = {k: v for k, v in result.items() if k != "sent" and k != "score"}
                        await self.handler.send_answer(result_to_send)
                        result["sent"] = True
                        self.num_results_sent += 1

                except (BrokenPipeError, ConnectionResetError):
                    self.handler.connection_alive_event.clear()
                    return

        except Exception as e:
            print(f"[RANKING] Error ranking item {name}: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Import here to avoid circular import
            from nlweb_core.config import CONFIG
            if CONFIG.should_raise_exceptions():
                raise  # Re-raise in testing/development mode


    async def sendRemainingAnswers(self, answers):
        """Send remaining answers that weren't sent early."""
        print(f"[RANKING] sendRemainingAnswers called with {len(answers)} answers")

        if not self.handler.connection_alive_event.is_set():
            print("[RANKING] Connection not alive in sendRemainingAnswers")
            return

        # Wait for pre checks to be done
        await self.handler.pre_checks_done_event.wait()

        # Get max_results from handler
        max_results = self.handler.get_param('max_results', int, self.NUM_RESULTS_TO_SEND)

        # Filter unsent results
        unsent = [r for r in answers if not r["sent"]]
        print(f"[RANKING] Found {len(unsent)} unsent results, already sent: {self.num_results_sent}")

        # Calculate how many more we can send
        remaining_slots = max_results - self.num_results_sent
        print(f"[RANKING] Remaining slots: {remaining_slots}")

        if remaining_slots <= 0:
            print("[RANKING] No remaining slots, returning")
            return

        # Take only what we can send
        to_send = unsent[:remaining_slots]
        print(f"[RANKING] Will send {len(to_send)} results")

        if to_send:
            try:
                # Send each result using send_answer
                for i, result in enumerate(to_send):
                    # Create a copy without the 'sent' field and 'score' for sending
                    result_to_send = {k: v for k, v in result.items() if k != "sent" and k != "score"}
                    print(f"[RANKING] Sending result {i+1}/{len(to_send)}: {result.get('name', 'unknown')}")
                    await self.handler.send_answer(result_to_send)
                    result["sent"] = True
                    self.num_results_sent += 1
                print(f"[RANKING] Successfully sent {len(to_send)} results")
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"[RANKING] Connection error: {e}")
                self.handler.connection_alive_event.clear()
            except Exception as e:
                print(f"[RANKING] Error sending results: {e}")
                import traceback
                traceback.print_exc()
                self.handler.connection_alive_event.clear()

    async def do(self):
        print(f"[RANKING] Starting ranking for {len(self.items)} items")

        tasks = []
        for url, json_str, name, site in self.items:
            if self.handler.connection_alive_event.is_set():  # Only add new tasks if connection is still alive
                tasks.append(asyncio.create_task(self.rankItem(url, json_str, name, site)))

        print(f"[RANKING] Created {len(tasks)} ranking tasks")

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"[RANKING] Error during gather: {e}")
            return

        print(f"[RANKING] Completed all ranking tasks. Total ranked: {len(self.rankedAnswers)}")

        if not self.handler.connection_alive_event.is_set():
            print("[RANKING] Connection not alive, returning")
            return

        # Wait for pre checks using event
        print("[RANKING] Waiting for pre_checks_done_event")
        await self.handler.pre_checks_done_event.wait()
        print("[RANKING] Pre-checks done")

        # Use min_score from handler if available, otherwise default to 51
        min_score_threshold = self.handler.get_param('min_score', int, 51)
        # Use max_results from handler if available, otherwise use NUM_RESULTS_TO_SEND
        max_results = self.handler.get_param('max_results', int, self.NUM_RESULTS_TO_SEND)

        print(f"[RANKING] Min score threshold: {min_score_threshold}, Max results: {max_results}")

        # Filter and sort by score
        filtered = [r for r in self.rankedAnswers if r['score'] > min_score_threshold]
        print(f"[RANKING] Filtered {len(filtered)} items above score {min_score_threshold}")

        ranked = sorted(filtered, key=lambda x: x["score"], reverse=True)
        self.handler.final_ranked_answers = ranked[:max_results]

        print(f"[RANKING] Sending {len(ranked)} remaining answers")

        # Send remaining unsent results
        try:
            await self.sendRemainingAnswers(ranked)
        except (BrokenPipeError, ConnectionResetError):
            self.handler.connection_alive_event.clear()

        print(f"[RANKING] Finished. Total sent: {self.num_results_sent}")
