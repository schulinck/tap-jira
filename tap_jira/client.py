"""REST client handling, including tap-jiraStream base class."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

import requests
from singer_sdk.authenticators import BasicAuthenticator, BearerTokenAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseAPIPaginator
from singer_sdk.streams import RESTStream

_Auth = Callable[[requests.PreparedRequest], requests.PreparedRequest]
SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class JiraStream(RESTStream):
    """tap-jira stream class."""

    next_page_token_jsonpath = (
        "$.paging.start"  # Or override `get_next_page_token`.  # noqa: S105
    )

    records_jsonpath = "$[*]"  # Or override `parse_response`.

    # Set this value or override `get_new_paginator`.
    next_page_token_jsonpath = "$.next_page"

    @property
    def url_base(self) -> str:
        """
        Returns base url
        """
        base_url = "https://ryan-miranda.atlassian.net:443/rest/api/3"
        return base_url

    @property
    def authenticator(self) -> _Auth:
        """Return a new authenticator object.

        Returns:
            An authenticator instance.
        """
        auth_type = self.config.get("auth_type", "")

        if auth_type == "oauth":
            return BearerTokenAuthenticator.create_for_stream(
                self,
                token=self.config.get("access_token", ""),
            )
        else:
            return BasicAuthenticator.create_for_stream(
                self,
                username=self.config.get("username", ""),
                password=self.config.get("password", ""),
            )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        headers = {}
        if "user_agent" in self.config:
            headers["User-Agent"] = self.config.get("user_agent")
        # If not using an authenticator, you may also provide inline auth headers:
        # headers["Private-Token"] = self.config.get("auth_token")  # noqa: ERA001
        return headers

    def get_url_params(
        self,
        context: dict | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization.

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary of URL query parameters.
        """
        params: dict = {}
        if next_page_token:
            params["startAt"] = next_page_token
        if self.replication_key:
            params["sort"] = "asc"
            params["order_by"] = self.replication_key

        return params

    def get_next_page_token(
        self,
        response: requests.Response,
        previous_token: t.Any | None,
    ) -> t.Any | None:
        """Return a token for identifying next page or None if no more pages."""
        # If pagination is required, return a token which can be used to get the
        #       next page. If this is the final page, return "None" to end the
        #       pagination loop.
        resp_json = response.json()
        if previous_token is None:
            previous_token = 0

        total = -1
        _value = None
        if type(resp_json) is dict:
            if resp_json.get("values") is not None:
                _value = resp_json.get("values")
                total = resp_json.get("total")
            elif resp_json.get("issues") is not None:
                _value = resp_json.get("issues")
                total = resp_json.get("total")
            elif resp_json.get("records") is not None:
                _value = resp_json.get("records")
                total = resp_json.get("total")
            elif resp_json.get("dashboard") is not None:
                _value = resp_json.get("dashboard")
                total = resp_json.get("total")

        if total is None:
            total = -1

        if _value is None:
            page = resp_json
            if len(page) == 0 or total <= previous_token + 1:
                return None
        else:
            if len(_value) == 0 or total <= previous_token + 1:
                return None

        return previous_token + 1
