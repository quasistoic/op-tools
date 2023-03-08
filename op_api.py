#!/usr/bin/env python3

import collections
import json
import logging
import os
import pickle
import shutil
import sys
import threading
import time

from functools import cached_property
from urllib.parse import parse_qs, urlparse

MULTIPROFILE_TAG = "ignored_by_op_dedupe"
UNIMPLEMENTED_FIELDS = frozenset(["vault"])


class RateLimiter(collections.Iterator):
    """Iterator that yields a value at most once every 'interval' seconds."""
    # Hat tip: https://stackoverflow.com/a/20644609/757873
    def __init__(self, interval):
        self.lock = threading.Lock()
        self.interval = interval
        self.next_yield = 0

    def __next__(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_yield:
                time.sleep(self.next_yield - now)
                now = time.monotonic()
            self.next_yield = now + self.interval


def get_domain_from_url(url):
    """Return the domain of a URL.

    Args:
        url (str): A string representing the URL.

    Returns:
        str: The domain of the URL.
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def get_domains_from_urls(url_list):
    return {get_domain_from_url(url) for url in url_list if get_domain_from_url(url)}

class ItemList:
    """A list of 1Password items."""

    def __init__(self, item_details_list, op_api=None):
        self.items = item_details_list
        self.op_api = op_api

    def __iter__(self):
        for i in self.items:
            yield i

    def __getitem__(self, i):
        return self.items[i]

    @classmethod
    def from_json(cls, serialized_json, op_api=None):
        raw_items = json.loads(serialized_json)
        item_details_list = []
        for raw_item in raw_items:
            item_details_list.append(ItemDetails.from_list(raw_item, op_api=op_api))
        return cls(item_details_list, op_api=op_api)


class ItemDetails:
    """A single 1Password item."""

    SERIALIZED_SOURCE = "serialized"
    JSON_SOURCE = "json"
    JSON_LIST_SOURCE = "list_skeleton"

    def __init__(self, item_id, fields=(), source=None,
            serialized=None, domains=frozenset([]), op_api=None):
        self.item_id = item_id
        self.serialized = serialized
        self.source = source
        self.fields = fields
        self.domains = domains
        self.op_api = op_api

    def __str__(self):
        return str(sorted(self.fields.items()))

    def is_duplicate(self, other):
        return self.has_domains() and bool(self.get_shared_domains(other))

    def get_shared_domains(self, other):
        return self.domains & other.domains

    def has_domains(self):
        return self.domains and self.domains != frozenset([''])

    def has_full_details(self):
        return ItemDetails.JSON_SOURCE == self.source

    def get_app_deeplink(self):
        # onepassword://open/i?a=ACCOUNT&v=VAULT&i=ITEM&h=HOST
        parsed = urlparse(self.get_deeplink())
        params = parse_qs(parsed.query)
        return 'onepassword://open/i?a={account}&v={vault}&i={item}&h={host}'.format(
            account=params['a'][0], host=params['h'][0], item=params['i'][0],
            vault=params['v'][0])

    def get_deeplink(self):
        return self.op_api.get_item_deeplink(self.item_id)

    @classmethod
    def from_json(cls, serialized_json, op_api=None):
        details = json.loads(serialized_json)
        item_id = details["id"]
        fields = {
            "title": details.get("title", "Untitled"),
            "tags": details.get("tags", []),
            "urls": [i["href"] for i in details.get("urls", [])],
            "vault": details["vault"]["name"],
            "category": details["category"],
            "updated_at": details["updated_at"]
        }
        for field in details["fields"]:
            if field.get("value"):
                if field.get("label"):
                    fields[field["label"]] = field["value"]
                else:
                    fields[field["id"]] = field["value"]
        return cls(item_id, fields=fields, source=cls.JSON_SOURCE,
            serialized=serialized_json, domains=get_domains_from_urls(fields["urls"]),
            op_api=op_api)

    @classmethod
    def from_list(cls, details, op_api=None):
        item_id = details["id"]
        fields = {
            "title": details.get("title", "Untitled"),
            "tags": details.get("tags", []),
            "urls": [i["href"] for i in details.get("urls", [])],
            "vault": details["vault"]["name"],
            "category": details["category"],
            "updated_at": details["updated_at"]
        }
        return cls(item_id, fields=fields, source=cls.JSON_LIST_SOURCE,
            domains=get_domains_from_urls(fields["urls"]), op_api=op_api)


class OpApi:
    """Connection Manager for the 1Password API."""

    def __init__(self, cache_dir="./.op-cache", vault=None,
        call_interval_seconds=0.21):
        self.vault = vault
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.api_rate_limiter = RateLimiter(call_interval_seconds)
        self.items = self.get_item_list()
        self.item_ids = [item.item_id for item in self.items]

    def _get_command_cache_file_name(self, command):
        return f"{self.cache_dir}/{self.vault}.{command}.cache"

    def clear_entire_cache(self):
        logging.info('Clearing cache...')
        shutil.rmtree(self.cache_dir)
        os.mkdir(self.cache_dir)
        logging.info('Cache cleared.')

    def clear_details_cache(self, item_id):
        self.get_item_details(item_id, force_refresh=True)

    def run_command(self, command, skip_cache=False, cacheable=True):
        cache_file = self._get_command_cache_file_name(command)
        if cacheable and not skip_cache:
            if os.path.exists(cache_file):
                logging.debug("Pulling from cache: %s", cache_file)
                with open(cache_file, "rb") as cache:
                    return pickle.load(cache)

        op_command = f"op {command}"
        if not skip_cache:
            op_command += " --cache"
        if self.vault:
            op_command += f" --vault {self.vault}"
        logging.info("Calling API: %s", op_command)
        next(self.api_rate_limiter)
        output = os.popen(op_command).read()
        if output and cacheable:
            with open(cache_file, "wb") as cache:
                pickle.dump(output, cache)
        return output

    def refresh_item_ids(self):
        self.items = self.get_item_list(force_refresh=True)
        self.item_ids = [item.item_id for item in self.items]

    def get_item_list(self, force_refresh=False):
        output = self.run_command("item list --format=json",
            skip_cache=force_refresh)
        item_list = ItemList.from_json(output, op_api=self)
        return item_list

    def get_item_details(self, item_id, force_refresh=False):
        output = self.run_command(f"item get {item_id} --format=json",
            skip_cache=force_refresh)
        try:
            item = ItemDetails.from_json(output, op_api=self)
        except json.decoder.JSONDecodeError:
            logging.error("Error while attempting to read: %s", item_id)
            sys.exit(1)
        return item

    def get_item_deeplink(self, item_id):
        return self.run_command(f"item get {item_id} --share-link")

    def archive_item(self, item_id):
        logging.warning("Archiving item %s", item_id)
        self.run_command(f"item delete {item_id} --archive", cacheable=False)
        self.refresh_item_ids()

    def create_item(self, item_template_path, title='Created by op_dedupe',
        url='https://example.com', generate_password=True):
        command = f'item create --template="{item_template_path}"'
        if generate_password:
            command += ' --generate-password'
        if title:
            command += f' --title "{title}"'
        if url:
            command += f' --url "{url}"'
        return self.run_command(command)

    def add_tag(self, item_details, tag):
        item_id = item_details.item_id
        all_tags = item_details.fields["tags"] + [tag]
        command = f'item edit {item_id} --tags "{all_tags[0]}"'
        for other_tag in all_tags[1:]:
            command += f',"{other_tag}"'
        self.run_command(command, cacheable=False)
        return self.get_item_details(item_id, force_refresh=True)

    def update_item(self, item_details, fields):
        item_id = item_details.item_id
        for field_name, values in fields.items():
            if field_name == "urls":
                logging.warning("Only copying over the first URL: %s", values[0])
                command = f'item edit {item_id} --url "{values[0]}"'
            elif field_name == "tags":
                for value in values:
                    item_details = self.add_tag(item_details, value)
                continue
            elif field_name in UNIMPLEMENTED_FIELDS:
                logging.warning("Copying %s is currently unimplemented. Sorry.", field_name)
                continue
            elif values == "":
                command = f'item edit {item_id} {field_name}[delete]'
            else:
                command = f'item edit {item_id} {field_name}="{values}"'
            self.run_command(command, cacheable=False)
        self.get_item_details(item_id, force_refresh=True)
        self.refresh_item_ids()

    def copy_field_values(self, from_item, to_item, fields):
        field_values = {}
        for field_name in fields:
            if field_name in from_item.fields:
                field_values[field_name] = from_item.fields[field_name]
            else:
                # I guess we're erasing this field. TODO: Prompt to confirm.
                field_values[field_name] = ''
        if field_values:
            self.update_item(to_item, field_values)

    def archive_items(self, items_to_archive):
        for item in items_to_archive:
            self.archive_item(item.item_id)

    def mark_as_multiprofile(self, items):
        for item in items:
            self.add_tag(item, MULTIPROFILE_TAG)

    def find_duplicates(self):
        duplicates = []
        duplicate_ids = set()
        for i, details in enumerate(self.items):
            item_id = details.item_id
            if item_id in duplicate_ids:
                logging.debug("Skipping %s because we know it's a duplicate.", item_id)
                continue
            logging.debug("Looking for duplicates of %s", item_id)
            if details and details.has_domains():
                matching_items = []
                for j_details in self.items[i+1:]:
                    j_item_id = j_details.item_id
                    if j_item_id in duplicate_ids:
                        logging.debug(
                            "Skipping %s (inner loop) because we know it's a duplicate.", j_item_id)
                        continue
                    if j_details.item_id == details.item_id:
                        continue
                    if not j_details.is_duplicate(details):
                        continue
                    matching_items.append(j_details)
                if matching_items:
                    duplicate_set = DuplicateSet([details] + matching_items, op_api=self)
                    if duplicate_set.is_intentionally_multiprofile():
                        continue
                    duplicates.append(duplicate_set)
                    duplicate_ids.update(
                        [item.item_id for item in duplicate_set.items])

        logging.info("Found %s sets of duplicates involving %s items.",
            len(duplicates), len(duplicate_ids))
        return duplicates


class DuplicateSet:
    """Container for a set of 1Password items that are considered duplicates of each other."""

    def __init__(self, items, op_api=None):
        self.op_api = op_api
        self.items = items

    def get_display_name(self):
        return max(self.items[0].get_shared_domains(self.items[1]))

    def has_full_details(self):
        return all(item.has_full_details() for item in self.items)

    def force_full_details(self):
        if self.has_full_details():
            return

        for i, item in enumerate(self.items[:]):
            if item.has_full_details():
                continue
            new_item = self.op_api.get_item_details(item.item_id)
            self.items[i] = new_item

    @cached_property
    def field_names(self):
        self.force_full_details()
        return sorted(set(field_name for item in self.items
                          for field_name in item.fields.keys()))

    @cached_property
    def field_values(self):
        self.force_full_details()
        return [
            [item.fields.get(field_name, '') for field_name in self.field_names]
            for item in self.items
        ]

    def is_intentionally_multiprofile(self):
        return all(
            MULTIPROFILE_TAG in item.fields["tags"] for item in self.items)

    def difference_score(self):
        score = 0
        for field_name in self.field_names:
            existing_values = set()
            for i in range(len(self.items)):
                for k in range(len(self.field_values[i])):
                    item_value = self.field_values[i][k]
                    if hasattr(item_value, '__iter__') and not isinstance(item_value, str):
                        for element in item_value:
                            existing_values.add(element)
                    else:
                        existing_values.add(item_value)

            row_has_diff_values = len(existing_values) > 1
            if row_has_diff_values:
                field_score = len(existing_values)
                if '' not in existing_values:
                    field_score += 1
                if field_name.lower() == "password":
                    field_score *= 10
                elif field_name.lower() == "username":
                    field_score *= 5
                elif field_name.lower in ["vault", "updated_at"]:
                    field_score /= 2
                score += field_score
        return score
