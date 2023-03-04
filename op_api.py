#!/usr/bin/env python3

import json
import logging
import os
import pickle
import sys

from functools import cached_property
from urllib.parse import urlparse

MULTIPROFILE_TAG = "multiprofile"


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


class ItemList:
    """A list of 1Password items."""

    def __init__(self, item_details_list):
        self.items = item_details_list

    def __iter__(self):
        for i in self.items:
            yield i

    @classmethod
    def from_json(cls, serialized_json):
        raw_items = json.loads(serialized_json)
        item_details_list = []
        for raw_item in raw_items:
            item_details_list.append(ItemDetails.from_list(raw_item))
        return cls(item_details_list)


class ItemDetails:
    """A single 1Password item."""

    SERIALIZED_SOURCE = "serialized"
    JSON_SOURCE = "json"
    JSON_LIST_SOURCE = "list_skeleton"

    def __init__(self, item_id, fields=(), source=None,
            serialized=None, domains=frozenset([])):
        self.item_id = item_id
        self.serialized = serialized
        self.source = source
        self.fields = fields
        self.domains = domains

    def __str__(self):
        return str(sorted(self.fields.items()))

    def is_duplicate(self, other):
        return bool(self.get_shared_domains(other))

    def get_shared_domains(self, other):
        return self.domains & other.domains

    def has_full_details(self):
        return ItemDetails.JSON_SOURCE == self.source

    @classmethod
    def from_json(cls, serialized_json):
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
        domains = {get_domain_from_url(url) for url in fields["urls"]}
        return cls(item_id, fields=fields, source=cls.JSON_SOURCE,
            serialized=serialized_json, domains=domains)

    @classmethod
    def from_list(cls, details):
        item_id = details["id"]
        fields = {
            "title": details.get("title", "Untitled"),
            "tags": details.get("tags", []),
            "urls": [i["href"] for i in details.get("urls", [])],
            "vault": details["vault"]["name"],
            "category": details["category"],
            "updated_at": details["updated_at"]
        }
        domains = {get_domain_from_url(url) for url in fields["urls"]}
        return cls(item_id, fields=fields, source=cls.JSON_LIST_SOURCE,
            domains=domains)


class OpApi:
    """Connection Manager for the 1Password API."""

    def __init__(self, cache_dir="./.op-cache", vault=None):
        self.vault = vault
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)
        self.items = self.get_item_list()
        self.item_ids = [item.item_id for item in self.items]

    def _get_command_cache_file_name(self, command):
        return f"{self.cache_dir}/.{self.vault}.{command}.cache"

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
        output = os.popen(op_command).read()
        if cacheable:
            with open(cache_file, "wb") as cache:
                pickle.dump(output, cache)
        return output

    def refresh_item_ids(self):
        self.items = self.get_item_list(force_refresh=True)
        self.item_ids = [item.item_id for item in self.items]

    def get_item_list(self, force_refresh=False):
        output = self.run_command("item list --format=json",
            skip_cache=force_refresh)
        item_list = ItemList.from_json(output)
        return item_list

    def get_item_details(self, item_id, force_refresh=False):
        output = self.run_command(f"item get {item_id} --format=json",
            skip_cache=force_refresh)
        try:
            item = ItemDetails.from_json(output)
        except json.decoder.JSONDecodeError:
            logging.error("Error while attempting to read: %s", item_id)
            sys.exit(1)
        return item

    def archive_item(self, item_id):
        logging.warning("Archiving item %s", item_id)
        self.run_command(f"item delete {item_id} --archive", cacheable=False)
        self.refresh_item_ids()

    def add_tag(self, item_details, tag):
        item_id = item_details.item_id
        all_tags = item_details.fields["tags"] + [tag]
        command = f'item edit {item_id} --tags "{all_tags[0]}"'
        for other_tag in all_tags[1:]:
            command += f',"{other_tag}"'
        self.run_command(command, cacheable=False)
        self.get_item_details(item_id, force_refresh=True)

    def update_item(self, item_details, fields):
        item_id = item_details.item_id
        for field_name, values in fields.items():
            if field_name == "urls":
                command = f'item edit {item_id} --url "{values[0]}"'
            elif field_name in ["tags"]:
                logging.warning("Copying %s is currently unimplemented.", field_name)
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
        for i, item_id in enumerate(self.item_ids):
            if item_id in duplicate_ids:
                logging.debug("Skipping %s because we know it's a duplicate.", item_id)
                continue
            logging.debug("Looking for duplicates of %s", item_id)
            details = self.get_item_details(item_id)
            if details:
                matching_items = []
                for j in self.item_ids[i+1:]:
                    if j in duplicate_ids:
                        logging.debug(
                            "Skipping %s (inner loop) because we know it's a duplicate.", j)
                        continue
                    j_details = self.get_item_details(j)
                    if j_details.item_id == details.item_id:
                        continue
                    if not j_details.is_duplicate(details):
                        continue
                    matching_items.append(j_details)
                if matching_items:
                    duplicate_set = DuplicateSet([details] + matching_items)
                    if duplicate_set.is_intentionally_multiprofile():
                        continue
                    duplicates.append(duplicate_set)
                    duplicate_ids.update(
                        [item.item_id for item in duplicate_set.items])

        logging.info("Found %s sets of duplicates.", len(duplicates))
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
            if i.has_full_details():
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
