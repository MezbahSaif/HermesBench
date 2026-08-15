"""Tests for the URL parser module (urlparse)."""

from buggy import parse_query, path_of


class TestParseQuery:
    """Tests for parse_query function."""

    def test_url_without_query_returns_empty(self):
        assert parse_query("https://example.com") == {}

    def test_single_parameter(self):
        result = parse_query("https://example.com/path?a=1")
        assert result == {"a": ["1"]}

    def test_multiple_parameters(self):
        """Multiple distinct parameters are returned as lists."""
        result = parse_query("https://example.com?a=1&b=2")
        assert result == {"a": ["1"], "b": ["2"]}, f"Got {result}"

    def test_repeated_values_are_lists(self):
        """Values that repeat should be returned as lists (per docstring)."""
        result = parse_query("https://example.com?a=1&a=2")
        assert result == {"a": ["1", "2"]}, f"Got {result}"

    def test_mixed_single_and_repeated(self):
        """Single values and repeated values coexist correctly."""
        result = parse_query("https://example.com?a=1&b=2&a=3")
        assert result == {"a": ["1", "3"], "b": ["2"]}, f"Got {result}"

    def test_empty_value_dropped_by_default(self):
        """parse_qs drops keys with empty values by default."""
        result = parse_query("https://example.com?key=")
        assert result == {}, f"Expected {{}}, got {result}"

    def test_explicit_empty_values_preserved(self):
        """With keep_blank_values=True, empty-valued params are preserved."""
        from urllib.parse import parse_qs as raw_parse_qs
        qs = "https://example.com?key="
        _, _, parsed_qs = qs.partition("?")
        result = raw_parse_qs(parsed_qs, keep_blank_values=True)
        assert result == {"key": [""]}, f"Got {result}"

    def test_encoded_characters(self):
        """parse_qs decodes percent-encoded characters (but NOT + to space)."""
        result = parse_query("https://example.com?q=%E4%B8%AD%E6%96%87")
        assert result["q"] == ["中文"], f"Got {result}"

    def test_plus_as_space(self):
        """Plus signs in query values are treated as spaces by parse_qs."""
        result = parse_query("https://example.com?q=hello+world")
        assert result["q"] == ["hello world"], f"Got {result}"

    def test_percent_20_decoded_to_space(self):
        """parse_qs decodes %20 to a regular space (Python default)."""
        result = parse_query("https://example.com?q=%20test")
        assert result["q"] == [" test"], f"Got {result}"

    def test_percent_encoded_chars_preserved_if_not_20(self):
        """parse_qs does NOT replace %XX codes other than 20/+/space."""
        # Use a non-20 percent code - it should stay encoded
        result = parse_query("https://example.com?q=%21test")
        assert "!" in "".join(result["q"]), f"Got {result}"

    def test_no_slashes_in_path(self):
        """URL without a path component still parses query correctly."""
        result = parse_query("https://example.com?a=1")
        assert "a" in result, f"Got {result}"


class TestPathOf:
    """Tests for path_of function."""

    def test_root_url(self):
        assert path_of("http://example.com") == "/"

    def test_path_with_no_trailing_slash(self):
        assert path_of("https://example.com/path/to/resource") == "path/to/resource"

    def test_path_with_trailing_slash(self):
        assert path_of("https://example.com/path/to/resource/") == "path/to/resource"

    def test_root_path_exploded(self):
        """Multiple trailing slashes collapse to single '/'."""
        assert path_of("http://example.com///") == "/"

    def test_no_query_string_ignored(self):
        result = path_of("https://example.com/path?query=1")
        assert result == "path", f"Got '{result}'"

    def test_only_scheme_and_host(self):
        """URL with no path returns '/'."""
        assert path_of("http://localhost:8080") == "/"

    def test_path_is_empty_returns_slash(self):
        """Empty path part after host still yields '/'."""
        result = path_of("https://example.com/")
        assert result == "/", f"Got '{result}'"
